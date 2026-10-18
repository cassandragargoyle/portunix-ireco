"""WatchConfig — typed configuration for ``ptx-ireco-watcher``.

The watcher reads its settings from ``ireco.config.json``: it pulls
``io.input_dir`` / ``io.output_dir`` from the existing ``io`` block and
the optional ``watcher`` / ``models`` blocks added in issue #004.

CLI flags layered on top (in :mod:`ptx_ireco.cli.watcher_main`) override
individual fields per ADR-0005 / issue #004's precedence rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ptx_ireco.config.schema import (
    WATCHER_DEFAULT_BACKEND,
    WATCHER_DEFAULT_COOLDOWN_SECONDS,
    WATCHER_DEFAULT_PATTERNS,
    WATCHER_DEFAULT_RECURSIVE,
    WATCHER_DEFAULT_WORKERS,
)
from ptx_ireco.pipeline.parse import OcrOptions


@dataclass
class WatchConfig:
    """Resolved configuration for a single watcher run.

    Defaults match the schema defaults documented in
    ``docs/schemas/ireco-config-1.0.json``.

    Attributes:
        watch_dirs: Directories to monitor. Populated from
            ``io.input_dir`` (and/or ``--watch-dir`` CLI flag).
        output_dir: Destination for ``.vim.json`` results. From
            ``io.output_dir`` or ``-o`` CLI flag.
        models_path: Repo root containing ``models/invoice/`` —
            forwarded to :class:`ptx_ireco.worker.api.pipeline.run`.
        backend: ``local`` | ``cli`` | ``grpc``.
        workers: Pool size for :class:`PoolDispatcher`. ``1`` = sequential.
        cooldown_seconds: Pause between detection and dispatch.
        patterns: Glob patterns matched against detected file names.
        recursive: Whether to watch subdirectories.
        invoice: Snapshot of ``invoice`` block (tenancy, recipients) so
            the worker pipeline can be invoked with the right
            :class:`ExtractionOptions` from a child process.
        events_log: Optional JSONL file for the event stream.
    """

    watch_dirs: list[Path] = field(default_factory=list)
    output_dir: Path | None = None
    models_path: Path | None = None
    backend: str = WATCHER_DEFAULT_BACKEND
    workers: int = WATCHER_DEFAULT_WORKERS
    cooldown_seconds: float = WATCHER_DEFAULT_COOLDOWN_SECONDS
    patterns: list[str] = field(default_factory=lambda: list(WATCHER_DEFAULT_PATTERNS))
    recursive: bool = WATCHER_DEFAULT_RECURSIVE
    invoice: dict[str, Any] = field(default_factory=dict)
    events_log: Path | None = None
    post_process: list[str] = field(default_factory=list)
    post_process_options: dict[str, dict[str, Any]] = field(default_factory=dict)
    # issue 007 — parse.ocr loaded from ireco.config.json; ``None`` keeps the
    # OCR plugin out of the pipeline registration entirely.
    parse_ocr: OcrOptions | None = None

    @classmethod
    def from_dict(
        cls,
        cfg: dict[str, Any] | None,
        *,
        config_path: Path | None = None,
    ) -> WatchConfig:
        """Build a :class:`WatchConfig` from a parsed ``ireco.config.json``.

        ``cfg`` is the validated document (or ``None`` for defaults).
        ``config_path`` is the original file location; when supplied,
        ``models.path`` is resolved relative to its parent directory so
        a relative path like ``"./models"`` works from any cwd.
        """
        cfg = cfg or {}
        io = cfg.get("io") or {}
        watcher = cfg.get("watcher") or {}
        models = cfg.get("models") or {}
        invoice = cfg.get("invoice") or {}

        watch_dirs: list[Path] = []
        if "input_dir" in io:
            watch_dirs.append(Path(io["input_dir"]))

        output_dir = Path(io["output_dir"]) if "output_dir" in io else None

        models_path = cls._resolve_models_path(models.get("path"), config_path)

        patterns_raw = watcher.get("patterns", list(WATCHER_DEFAULT_PATTERNS))
        patterns = list(patterns_raw) if patterns_raw else list(WATCHER_DEFAULT_PATTERNS)

        post_process_raw = watcher.get("post_process") or []
        post_process = list(post_process_raw) if post_process_raw else []
        post_process_options_raw = watcher.get("post_process_options") or {}
        post_process_options = {
            k: dict(v or {}) for k, v in post_process_options_raw.items()
        }

        return cls(
            watch_dirs=watch_dirs,
            output_dir=output_dir,
            models_path=models_path,
            backend=watcher.get("backend", WATCHER_DEFAULT_BACKEND),
            workers=int(watcher.get("workers", WATCHER_DEFAULT_WORKERS)),
            cooldown_seconds=float(
                watcher.get("cooldown_seconds", WATCHER_DEFAULT_COOLDOWN_SECONDS)
            ),
            patterns=patterns,
            recursive=bool(watcher.get("recursive", WATCHER_DEFAULT_RECURSIVE)),
            invoice=dict(invoice),
            post_process=post_process,
            post_process_options=post_process_options,
            parse_ocr=OcrOptions.from_config_dict(cfg),
        )

    @staticmethod
    def _resolve_models_path(raw: str | None, config_path: Path | None) -> Path | None:
        """Return an absolute ``Path`` for ``models.path`` or ``None``.

        A relative path is anchored at the config file's parent
        directory; without a known config location it stays relative
        and is later resolved against cwd by the worker pipeline.
        """
        if not raw:
            return None
        p = Path(raw)
        if p.is_absolute():
            return p
        if config_path is not None:
            return (config_path.parent / p).resolve()
        return p

    def with_overrides(
        self,
        *,
        watch_dirs: list[Path] | None = None,
        output_dir: Path | None = None,
        models_path: Path | None = None,
        backend: str | None = None,
        workers: int | None = None,
        cooldown_seconds: float | None = None,
        patterns: list[str] | None = None,
        recursive: bool | None = None,
        events_log: Path | None = None,
        post_process: list[str] | None = None,
        parse_ocr: OcrOptions | None = None,
    ) -> WatchConfig:
        """Return a copy with the given fields overridden.

        Used by the CLI to layer ``--watch-dir`` / ``-o`` / ``--workers``
        etc. on top of values loaded from ``ireco.config.json``.
        ``None`` means "keep the existing value".
        """
        return WatchConfig(
            watch_dirs=watch_dirs if watch_dirs is not None else list(self.watch_dirs),
            output_dir=output_dir if output_dir is not None else self.output_dir,
            models_path=models_path if models_path is not None else self.models_path,
            backend=backend if backend is not None else self.backend,
            workers=workers if workers is not None else self.workers,
            cooldown_seconds=(
                cooldown_seconds if cooldown_seconds is not None else self.cooldown_seconds
            ),
            patterns=patterns if patterns is not None else list(self.patterns),
            recursive=recursive if recursive is not None else self.recursive,
            invoice=dict(self.invoice),
            events_log=events_log if events_log is not None else self.events_log,
            post_process=(
                post_process if post_process is not None else list(self.post_process)
            ),
            post_process_options=dict(self.post_process_options),
            parse_ocr=parse_ocr if parse_ocr is not None else self.parse_ocr,
        )

