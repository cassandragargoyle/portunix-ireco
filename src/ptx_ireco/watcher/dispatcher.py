"""Dispatch backends + pool dispatcher for ``ptx-ireco-watcher``.

Three backends per ADR-0005 / issue #004 §"Dispatch backends":

- ``local`` — direct in-process call to
  :func:`ptx_ireco.worker.api.pipeline.run`. Lowest latency, no crash
  isolation.
- ``cli``   — spawn ``ptx-ireco-worker run`` subprocess per file. Per
  file crash isolation, higher latency.
- ``grpc``  — reserved; :class:`DispatchError` (fail-fast at start time,
  enforced by ``ptx-ireco-watcher`` CLI; this module is best-effort).

The pool dispatcher wraps :class:`concurrent.futures.ProcessPoolExecutor`.
``_worker_execute`` is intentionally a **module-level** function so that
it pickles into worker processes.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from ptx_ireco.pipeline.parse import OcrOptions
from ptx_ireco.watcher.config import WatchConfig

logger = logging.getLogger(__name__)


class DispatchError(Exception):
    """Raised when dispatch to a backend fails."""


def dispatch(file_path: Path, config: WatchConfig) -> dict[str, Any]:
    """Dispatch one file through the configured backend.

    Returns a result dict (shape depends on the backend) when successful.

    Raises:
        DispatchError: backend invocation failed.
        ValueError: ``config.backend`` is not a recognized name.
    """
    backend = config.backend
    if backend == "local":
        return _dispatch_local(file_path, config)
    if backend == "cli":
        return _dispatch_cli(file_path, config)
    if backend == "grpc":
        raise DispatchError("gRPC dispatch is reserved and not yet implemented")
    raise ValueError(f"Unknown dispatch backend: {backend!r}")


def _dispatch_local(file_path: Path, config: WatchConfig) -> dict[str, Any]:
    """In-process call to :func:`ptx_ireco.worker.api.pipeline.run`."""
    from ptx_ireco.pipeline.extract import ExtractionError
    from ptx_ireco.worker.api import pipeline as worker_pipeline
    from ptx_ireco.worker.api.pipeline import ExtractionOptions

    out_dir = config.output_dir
    if out_dir is None:
        raise DispatchError("output_dir is required (set io.output_dir or -o)")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{file_path.stem}.vim.json"

    options = _build_extraction_options_from_invoice(
        config.invoice, ExtractionOptions
    )

    try:
        result = worker_pipeline.run(
            file_path,
            out_path,
            models=config.models_path,
            options=options,
            verbose=False,
            ocr=config.parse_ocr,
        )
    except (ExtractionError, FileNotFoundError, RuntimeError) as exc:
        raise DispatchError(f"{type(exc).__name__}: {exc}") from exc

    summary: dict[str, Any] = {
        "vim_path": str(out_path),
        "entities": [e.type for e in result.entities],
    }
    if result.recipient_id is not None:
        summary["recipient_id"] = result.recipient_id
    return summary


def _dispatch_cli(file_path: Path, config: WatchConfig) -> dict[str, Any]:
    """Spawn ``ptx-ireco-worker run --file <pdf> -o <out>`` subprocess."""
    out_dir = config.output_dir
    if out_dir is None:
        raise DispatchError("output_dir is required (set io.output_dir or -o)")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{file_path.stem}.vim.json"

    # NOTE: --models is a *global* flag on ptx-ireco-worker (declared on the
    # top-level parser, not on the `run` subparser). It must precede the
    # subcommand or argparse rejects it as an unrecognized argument. The
    # OCR flags are subparser-scoped, so they go after `run`.
    from ptx_ireco.cli._ocr_args import ocr_options_to_cli_args

    cmd = _resolve_worker_command()
    if config.models_path is not None:
        cmd.extend(["--models", str(config.models_path)])
    cmd.extend(["run", "--file", str(file_path), "-o", str(out_path)])
    cmd.extend(ocr_options_to_cli_args(config.parse_ocr))

    logger.debug("CLI dispatch: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise DispatchError("ptx-ireco-worker not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise DispatchError(
            f"worker process failed (rc={exc.returncode}): {stderr}"
        ) from exc

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"raw_output": proc.stdout, "vim_path": str(out_path)}


def _resolve_worker_command() -> list[str]:
    """Return the argv prefix to invoke ``ptx-ireco-worker``.

    Rule (deterministic and venv-aware):

    1. Prefer the current interpreter via ``sys.executable -m
       ptx_ireco.cli.worker_main``. This guarantees the watcher and the
       worker share the same virtual environment.
    2. Fall back to ``shutil.which("ptx-ireco-worker")`` only when the
       interpreter is not available (rare; mostly frozen builds).
    """
    if sys.executable:
        return [sys.executable, "-m", "ptx_ireco.cli.worker_main"]
    found = shutil.which("ptx-ireco-worker")
    if found:
        return [found]
    raise DispatchError("cannot resolve ptx-ireco-worker command")


def _build_extraction_options_from_invoice(
    invoice: dict[str, Any], options_cls: type
) -> Any:
    """Construct :class:`ExtractionOptions` from the invoice section.

    Mirrors :func:`ptx_ireco.cli.worker_main._build_extraction_options`
    but operates on the dict already snapshotted into the
    :class:`WatchConfig`.
    """
    if invoice.get("tenancy") != "known":
        return None
    recipients = invoice.get("recipients") or []
    return options_cls(recipients=recipients)


# ---------------------------------------------------------------------------
# Pool dispatcher — multiprocess batch
# ---------------------------------------------------------------------------


def _worker_execute(
    file_path: str,
    backend: str,
    output_dir: str | None,
    models_path: str | None,
    invoice: dict[str, Any],
    parse_ocr: OcrOptions | None = None,
) -> dict[str, Any]:
    """Execute one dispatch inside a worker process.

    Module-level on purpose: :class:`ProcessPoolExecutor` requires the
    callable to be importable, otherwise the pickle round-trip fails.

    Returns a dict with ``status`` and either ``result`` or ``error``
    keys, plus the originating ``file`` path.
    """
    try:
        cfg = WatchConfig(
            output_dir=Path(output_dir) if output_dir else None,
            models_path=Path(models_path) if models_path else None,
            backend=backend,
            invoice=dict(invoice),
            parse_ocr=parse_ocr,
        )
        result = dispatch(Path(file_path), cfg)
        return {"file": file_path, "status": "success", "result": result}
    except DispatchError as exc:
        return {
            "file": file_path,
            "status": "error",
            "error": {"code": "DISPATCH_ERROR", "message": str(exc)},
        }
    except Exception as exc:  # pragma: no cover — defensive
        return {
            "file": file_path,
            "status": "error",
            "error": {
                "code": "WORKER_CRASH",
                "message": f"{type(exc).__name__}: {exc}",
            },
        }


class PoolDispatcher:
    """Multiprocess dispatcher using :class:`ProcessPoolExecutor`.

    Configured with ``workers > 1``. Submits one task per detected file
    and streams results through optional ``on_result`` / ``on_error``
    callbacks. ``shutdown(wait=True)`` waits for in-flight tasks so
    a ``Ctrl-C`` does not orphan running children.

    Worker crashes are converted to error results with
    ``error.code = WORKER_CRASH`` and never propagate out of the pool —
    the watcher stays alive.
    """

    def __init__(
        self,
        config: WatchConfig,
        *,
        on_result: Any | None = None,
        on_error: Any | None = None,
        executor_class: type | None = None,
    ) -> None:
        max_workers = config.workers if config.workers > 0 else (os.cpu_count() or 1)
        self._config = config
        factory = executor_class or ProcessPoolExecutor
        self._executor = factory(max_workers=max_workers)
        self._futures: list[Future[dict[str, Any]]] = []
        self._results: list[dict[str, Any]] = []
        self._on_result = on_result
        self._on_error = on_error
        self._max_workers = max_workers
        logger.info("Pool dispatcher started (workers=%d)", max_workers)

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @property
    def results(self) -> list[dict[str, Any]]:
        return list(self._results)

    def submit(self, file_path: Path) -> Future[dict[str, Any]]:
        """Submit ``file_path`` for processing in the pool."""
        future = self._executor.submit(
            _worker_execute,
            str(file_path),
            self._config.backend,
            str(self._config.output_dir) if self._config.output_dir else None,
            str(self._config.models_path) if self._config.models_path else None,
            self._config.invoice,
            self._config.parse_ocr,
        )
        self._futures.append(future)
        if self._on_result or self._on_error:
            future.add_done_callback(self._handle_future_done)
        return future

    def _handle_future_done(self, future: Future[dict[str, Any]]) -> None:
        try:
            result = future.result()
        except Exception as exc:
            result = {
                "file": "<unknown>",
                "status": "error",
                "error": {"code": "FUTURE_ERROR", "message": str(exc)},
            }
        self._results.append(result)
        if result.get("status") == "error" and self._on_error:
            self._on_error(result)
        elif self._on_result:
            self._on_result(result)

    def shutdown(self, wait: bool = True) -> list[dict[str, Any]]:
        """Drain the pool and shut down the executor."""
        if not (self._on_result or self._on_error):
            for future in as_completed(self._futures):
                try:
                    result = future.result()
                except Exception as exc:
                    result = {
                        "file": "<unknown>",
                        "status": "error",
                        "error": {"code": "FUTURE_ERROR", "message": str(exc)},
                    }
                self._results.append(result)
        else:
            for _ in as_completed(self._futures):
                pass
        self._executor.shutdown(wait=wait)
        self._futures.clear()
        logger.info("Pool dispatcher shut down (%d results)", len(self._results))
        return list(self._results)
