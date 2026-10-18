"""FileSystemMonitor — long-running watchdog-based directory observer.

Watches the configured ``watch_dirs`` for new files matching
``patterns``, waits a brief cooldown to let the writer finish, and
dispatches each PDF through :func:`ptx_ireco.watcher.dispatcher.dispatch`
(sequential) or :class:`PoolDispatcher` (when ``workers > 1``).

The monitor blocks in :meth:`start` until :meth:`stop` is called or
``Ctrl-C`` is received; the pool, observer threads and any in-flight
work are shut down cleanly in both paths.
"""

from __future__ import annotations

import fnmatch
import logging
import threading
import time
from pathlib import Path
from typing import Any

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ptx_ireco.watcher.config import WatchConfig
from ptx_ireco.watcher.dispatcher import DispatchError, PoolDispatcher, dispatch
from ptx_ireco.watcher.post_process import PostProcessError, run_post_process
from ptx_ireco.watcher.router import EventRouter

logger = logging.getLogger(__name__)


class _ScanHandler(FileSystemEventHandler):
    """Watchdog handler that filters by pattern and dispatches."""

    def __init__(
        self,
        config: WatchConfig,
        router: EventRouter,
        pool: PoolDispatcher | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._router = router
        self._pool = pool

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if not self._matches_pattern(path):
            return

        logger.info("Detected: %s", path)
        self._router.emit_detected(path)

        time.sleep(self._config.cooldown_seconds)

        if self._pool is not None:
            self._pool.submit(path)
            return

        try:
            result = dispatch(path, self._config)
            metadata = {"result_keys": list(result.keys())}
            self._router.emit_processed(path, metadata=metadata)
            _run_post_processors(
                config=self._config,
                router=self._router,
                vim_path=_extract_vim_path(result),
            )
        except (DispatchError, ValueError) as exc:
            logger.error("Dispatch failed for %s: %s", path, exc)
            self._router.emit_failed(path, str(exc))

    def _matches_pattern(self, path: Path) -> bool:
        return any(fnmatch.fnmatch(path.name, pat) for pat in self._config.patterns)


class FileSystemMonitor:
    """Long-running file system watcher daemon.

    Examples:
        >>> cfg = WatchConfig(watch_dirs=[Path("/scans")], output_dir=Path("/out"))
        >>> monitor = FileSystemMonitor(cfg)
        >>> monitor.start()  # blocks until Ctrl-C
    """

    def __init__(
        self,
        config: WatchConfig,
        router: EventRouter | None = None,
        *,
        on_pool_result: Any | None = None,
        on_pool_error: Any | None = None,
    ) -> None:
        self._config = config
        self._router = router or EventRouter(events_log=config.events_log)
        self._observer = Observer()
        self._running = threading.Event()
        self._pool: PoolDispatcher | None = None
        self._on_pool_result = on_pool_result or self._default_pool_result
        self._on_pool_error = on_pool_error or self._default_pool_error

    @property
    def router(self) -> EventRouter:
        """The event router; register callbacks on it."""
        return self._router

    def start(self) -> None:
        """Start observing and block until stopped.

        Raises:
            ValueError: ``watch_dirs`` is empty.
        """
        if not self._config.watch_dirs:
            raise ValueError("No watch directories configured")

        if self._config.workers > 1:
            self._pool = PoolDispatcher(
                self._config,
                on_result=self._on_pool_result,
                on_error=self._on_pool_error,
            )
            logger.info(
                "Pool mode: %d workers, backend=%s",
                self._config.workers,
                self._config.backend,
            )

        handler = _ScanHandler(self._config, self._router, pool=self._pool)

        scheduled = 0
        for watch_dir in self._config.watch_dirs:
            wd = Path(watch_dir)
            if not wd.is_dir():
                logger.warning("Watch directory does not exist: %s", wd)
                continue
            self._observer.schedule(handler, str(wd), recursive=self._config.recursive)
            logger.info("Watching: %s", wd)
            scheduled += 1

        if scheduled == 0:
            raise ValueError("No existing directory among watch_dirs")

        self._observer.start()
        self._running.set()
        logger.info("Watcher started (backend=%s)", self._config.backend)

        try:
            while self._running.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the observer and shut the pool down cleanly."""
        if not self._running.is_set() and self._pool is None:
            return
        self._running.clear()
        try:
            self._observer.stop()
            self._observer.join()
        except RuntimeError:
            # Observer not started — safe to ignore on early-error paths.
            pass
        if self._pool is not None:
            self._pool.shutdown(wait=True)
            self._pool = None
        logger.info("Watcher stopped")

    def is_running(self) -> bool:
        return self._running.is_set()

    def _default_pool_result(self, result: dict[str, Any]) -> None:
        """Translate a successful pool result into a SCAN_PROCESSED event."""
        source = Path(result.get("file", ""))
        payload = result.get("result") or {}
        metadata = {"result_keys": list(payload.keys())} if isinstance(payload, dict) else {}
        self._router.emit_processed(source, metadata=metadata)
        _run_post_processors(
            config=self._config,
            router=self._router,
            vim_path=_extract_vim_path(payload) if isinstance(payload, dict) else None,
        )

    def _default_pool_error(self, result: dict[str, Any]) -> None:
        """Translate a pool error into a SCAN_FAILED event."""
        source = Path(result.get("file", ""))
        err = result.get("error") or {}
        message = err.get("message", "unknown error") if isinstance(err, dict) else str(err)
        code = err.get("code") if isinstance(err, dict) else None
        self._router.emit_failed(source, message, error_code=code)


def _extract_vim_path(result: Any) -> Path | None:
    """Best-effort: pull ``vim_path`` out of a dispatch result dict."""
    if isinstance(result, dict):
        v = result.get("vim_path")
        if v:
            return Path(v)
    return None


def _run_post_processors(
    *,
    config: WatchConfig,
    router: EventRouter,
    vim_path: Path | None,
) -> None:
    """Invoke each configured post-processor; emit POSTPROCESS_FAILED on failure.

    The parser's ``.vim.json`` is preserved on disk regardless of any
    post-processor failure (the export step is read-only over it).
    """
    if not config.post_process or vim_path is None:
        return
    for handler in config.post_process:
        options = config.post_process_options.get(handler) or {}
        try:
            run_post_process(
                handler=handler,
                vim_path=vim_path,
                options=options,
                models_path=config.models_path,
            )
        except PostProcessError as exc:
            logger.error("Post-process %s failed for %s: %s", handler, vim_path, exc.message)
            router.emit_postprocess_failed(vim_path, handler, exc.message)
