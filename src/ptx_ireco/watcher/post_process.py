"""Post-processing handlers chained after a successful ``scan.processed``.

Currently one handler is registered:

- ``export-isdoc`` — runs :func:`ptx_ireco.export.isdoc.api.export`
  against the parser's ``.vim.json`` output.

The watcher invokes :func:`run_post_process` from the main process
after dispatch returns; pool dispatch results report the produced
``vim_path`` back to the main process for the same chaining.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ptx_ireco.export.isdoc import api as isdoc_api
from ptx_ireco.export.isdoc.api import ValidationFailed
from ptx_ireco.export.isdoc.errors import ExportError

logger = logging.getLogger(__name__)


class PostProcessError(RuntimeError):
    """Raised when a post-processing handler fails."""

    def __init__(self, handler: str, message: str) -> None:
        super().__init__(f"[{handler}] {message}")
        self.handler = handler
        self.message = message


_VALID_HANDLERS: set[str] = {"export-isdoc"}


def is_valid_handler(name: str) -> bool:
    return name in _VALID_HANDLERS


def run_post_process(
    *,
    handler: str,
    vim_path: Path,
    options: dict[str, Any],
    models_path: Path | None,
) -> dict[str, Any]:
    """Dispatch one post-processing handler.

    Args:
        handler: Handler name (``"export-isdoc"``).
        vim_path: ``.vim.json`` produced by the parser.
        options: Per-handler options (from
            ``watcher.post_process_options``).
        models_path: Repo root with ``models/`` (forwarded to the
            export API). Falls back to discovery when ``None``.

    Raises:
        PostProcessError: handler unknown or invocation failed.
    """
    if handler == "export-isdoc":
        return _run_export_isdoc(vim_path, options, models_path)
    raise PostProcessError(handler, f"Unknown post-process handler: {handler!r}")


def _run_export_isdoc(
    vim_path: Path,
    options: dict[str, Any],
    models_path: Path | None,
) -> dict[str, Any]:
    out_dir = options.get("output_dir")
    try:
        result = isdoc_api.export(
            vim_path,
            out_dir=Path(out_dir) if out_dir else None,
            format=options.get("format", "isdoc"),
            profile=options.get("profile", "standard"),
            allow_incomplete=bool(options.get("allow_incomplete", False)),
            models=models_path,
            source_pdf=Path(options["source_pdf"]) if options.get("source_pdf") else None,
        )
    except ValidationFailed as exc:
        raise PostProcessError(
            "export-isdoc",
            f"validation failed ({len(exc.errors)} error(s); first: "
            f"{exc.errors[0].message if exc.errors else 'unknown'})",
        ) from exc
    except (ExportError, FileNotFoundError) as exc:
        raise PostProcessError("export-isdoc", str(exc)) from exc

    outputs = [str(result.isdoc_path), str(result.provenance_path)]
    if result.bundle_path is not None:
        outputs.append(str(result.bundle_path))
    logger.info("post-process export-isdoc → %s", outputs)
    return {
        "outputs": outputs,
        "validations": dict(result.validations),
    }
