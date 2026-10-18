"""``ptx-ireco-worker`` command-line interface.

Stateless invoice/document worker. Mirrors ``ptx-reco-worker`` shape
(``process`` / ``run`` / ``batch`` / ``task execute``) but is wired to
the ``ireco.invoice.*`` task registry and the ireco extraction
pipeline.

Subcommands:

- ``process``   — single PDF → ``.vim.json`` (alias of ``run``).
- ``run``       — same as ``process``; provided for parity with the
                  driver CLI's verb.
- ``batch``     — every ``*.pdf`` in a directory, one ``.vim.json`` per
                  input. Emits a JSON summary array on stdout. Exit 0
                  iff every file succeeded.
- ``task execute`` — read a TaskRequest JSON (``--file`` or stdin) and
                  print a TaskResponse.

Config / models precedence (highest → lowest):

1. Explicit ``--config`` flag (worker CLI side).
2. ``ireco.config.json`` in cwd (auto-detected when ``--config`` is
   absent).
3. Defaults: no recipient list, models root = cwd (models in
   ``./models/invoice/``).

``--models`` flag overrides ``models.path`` from the config. A relative
``--models`` is resolved against cwd; a relative ``models.path`` is
anchored at the directory of the config file (same rule as the watcher).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from ptx_ireco import __version__
from ptx_ireco.cli._ocr_args import add_ocr_arguments, build_ocr_options
from ptx_ireco.config import (
    InvalidConfigError,
    UnsupportedVersionError,
    find_config,
    load_config_file,
    resolve_models_path,
)
from ptx_ireco.config.schema import IMPLEMENTED_DOC_TYPES
from ptx_ireco.pipeline.extract import ExtractionError
from ptx_ireco.worker.api import pipeline as worker_pipeline
from ptx_ireco.worker.api.pipeline import ExtractionOptions, ModelPaths
from ptx_ireco.worker.task import TaskAdapter

logger = logging.getLogger(__name__)

EXIT_RESERVED_DOC_TYPE = 3
EXIT_CONFIG_INVALID = 4


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.command == "process" or args.command == "run":
        return _cmd_process(args)
    if args.command == "batch":
        return _cmd_batch(args)
    if args.command == "task":
        if args.task_action == "execute":
            return _cmd_task_execute(args)
        parser.parse_args([args.command, "--help"])
        return 1

    parser.print_help()
    return 1


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def _cmd_process(args: argparse.Namespace) -> int:
    cfg, cfg_path = _resolve_config(args)
    if cfg is not None:
        try:
            _check_implemented_doc_types(cfg)
        except _ReservedDocTypeError as exc:
            print(f"{args.command}: {exc}", file=sys.stderr)
            return EXIT_RESERVED_DOC_TYPE

    pdf_path = Path(args.file)
    if not pdf_path.is_file():
        print(f"{args.command}: file not found: {pdf_path}", file=sys.stderr)
        return 2

    out = _resolve_out(args.out, cfg)
    if out is None:
        print(
            f"{args.command}: -o is required (no output_dir in ireco.config.json)",
            file=sys.stderr,
        )
        return 2

    repo_root = _resolve_repo_root(args, cfg, cfg_path)
    model_paths = ModelPaths.default(repo_root)
    options = _build_extraction_options(cfg)
    ocr = build_ocr_options(args, cfg)
    try:
        result = worker_pipeline.run(
            pdf_path,
            out,
            models=repo_root,
            options=options,
            verbose=args.verbose,
            ocr=ocr,
        )
    except ExtractionError as exc:
        print(f"{args.command}: {exc}", file=sys.stderr)
        return 2

    summary: dict[str, Any] = {
        "vim_path": str(out),
        "template_match": result.template_match.template_id if result.template_match else None,
        "country": result.detected_country,
        "profile": str(result.profile.path.relative_to(model_paths.profiles.parent.parent)),
        "flexylayout": str(result.flexylayout_path.relative_to(model_paths.extraction.parent.parent)),
        "entities": [e.type for e in result.entities],
    }
    if result.recipient_id is not None:
        summary["recipient_id"] = result.recipient_id
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    cfg, cfg_path = _resolve_config(args)
    if cfg is not None:
        try:
            _check_implemented_doc_types(cfg)
        except _ReservedDocTypeError as exc:
            print(f"batch: {exc}", file=sys.stderr)
            return EXIT_RESERVED_DOC_TYPE

    input_dir = Path(args.dir)
    if not input_dir.is_dir():
        print(f"batch: directory not found: {input_dir}", file=sys.stderr)
        return 2

    out_dir = Path(args.out) if args.out else _resolve_io_path(None, cfg, "output_dir")
    if out_dir is None:
        print(
            "batch: -o is required (no output_dir in ireco.config.json)",
            file=sys.stderr,
        )
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    repo_root = _resolve_repo_root(args, cfg, cfg_path)
    options = _build_extraction_options(cfg)
    ocr = build_ocr_options(args, cfg)

    pdfs = sorted(input_dir.glob("*.pdf"))
    summaries: list[dict[str, Any]] = []
    any_failed = False
    for pdf in pdfs:
        out_file = out_dir / f"{pdf.stem}.vim.json"
        entry: dict[str, Any] = {"input": str(pdf), "output": str(out_file)}
        try:
            result = worker_pipeline.run(
                pdf,
                out_file,
                models=repo_root,
                options=options,
                verbose=args.verbose,
                ocr=ocr,
            )
        except (ExtractionError, FileNotFoundError, RuntimeError) as exc:
            entry["status"] = "error"
            entry["error"] = f"{type(exc).__name__}: {exc}"
            any_failed = True
        else:
            entry["status"] = "success"
            entry["entities"] = [e.type for e in result.entities]
            if result.recipient_id is not None:
                entry["recipient_id"] = result.recipient_id
        summaries.append(entry)

    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 1 if any_failed else 0


def _cmd_task_execute(args: argparse.Namespace) -> int:
    cfg, _ = _resolve_config(args)
    request = _read_request(args)
    if request is None:
        return 2
    adapter = TaskAdapter(default_config=cfg)
    response = adapter.execute(request)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0 if response.get("status") == "success" else 1


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------


class _ReservedDocTypeError(RuntimeError):
    pass


def _resolve_config(args: argparse.Namespace) -> tuple[dict[str, Any] | None, Path | None]:
    """Explicit ``--config`` wins over cwd auto-detect; returns ``(cfg, path)``."""
    explicit: str | None = getattr(args, "config", None)
    if explicit:
        cfg_path = Path(explicit)
        if not cfg_path.is_file():
            print(f"config: file not found: {cfg_path}", file=sys.stderr)
            sys.exit(EXIT_CONFIG_INVALID)
        return _load_or_die(cfg_path), cfg_path

    cwd_cfg = find_config(Path.cwd())
    if cwd_cfg is None:
        return None, None
    return _load_or_die(cwd_cfg), cwd_cfg


def _load_or_die(cfg_path: Path) -> dict[str, Any]:
    try:
        return load_config_file(cfg_path)
    except (InvalidConfigError, UnsupportedVersionError) as exc:
        print(f"config: {exc}", file=sys.stderr)
        sys.exit(EXIT_CONFIG_INVALID)


def _check_implemented_doc_types(cfg: dict[str, Any]) -> None:
    declared = cfg.get("doc_types") or []
    not_implemented = [t for t in declared if t not in IMPLEMENTED_DOC_TYPES]
    if not_implemented:
        raise _ReservedDocTypeError(
            "doc_types include reserved values that are not implemented yet: "
            + ", ".join(not_implemented)
            + " (only " + ", ".join(IMPLEMENTED_DOC_TYPES) + " is supported in this build)"
        )


def _resolve_out(cli_value: str | None, cfg: dict[str, Any] | None) -> Path | None:
    if cli_value:
        return Path(cli_value)
    if cfg is None:
        return None
    return _resolve_io_path(None, cfg, "output_dir")


def _resolve_io_path(
    cli_value: str | None, cfg: dict[str, Any] | None, key: str
) -> Path | None:
    if cli_value:
        return Path(cli_value)
    if cfg is None:
        return None
    io = cfg.get("io") or {}
    if key in io:
        return Path(io[key])
    return None


def _resolve_repo_root(
    args: argparse.Namespace,
    cfg: dict[str, Any] | None,
    cfg_path: Path | None = None,
) -> Path:
    """Explicit ``--models`` flag → ``models.path`` from config → cwd.

    Returns the repo root that contains ``models/invoice/...``. The caller
    builds :class:`ModelPaths` from this and passes the same value to the
    pipeline façade so the two views agree on layout.

    A relative ``--models`` stays relative to cwd. A relative
    ``models.path`` is anchored at the config file's parent directory,
    the same rule as the watcher (see :func:`resolve_models_path`).
    """
    models = getattr(args, "models", None)
    if models is not None:
        return Path(models)
    if cfg is not None:
        models_section = cfg.get("models") or {}
        resolved = resolve_models_path(models_section.get("path"), cfg_path)
        if resolved is not None:
            return resolved
    return Path.cwd()


def _build_extraction_options(cfg: dict[str, Any] | None) -> ExtractionOptions | None:
    if cfg is None:
        return None
    invoice = cfg.get("invoice") or {}
    if invoice.get("tenancy") != "known":
        return None
    recipients = invoice.get("recipients") or []
    return ExtractionOptions(recipients=recipients)


def _read_request(args: argparse.Namespace) -> dict[str, Any] | None:
    if args.file:
        path = Path(args.file)
        if not path.is_file():
            print(f"task: request file not found: {path}", file=sys.stderr)
            return None
        raw = path.read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
    try:
        request = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"task: invalid JSON request: {exc}", file=sys.stderr)
        return None
    if not isinstance(request, dict):
        print("task: request must be a JSON object", file=sys.stderr)
        return None
    return request


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ptx-ireco-worker",
        description="Stateless invoice/document worker (parse + extract).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ptx-ireco-worker {__version__}",
    )
    parser.add_argument(
        "--models",
        type=Path,
        default=None,
        help="Repo root containing models/invoice/ (overrides config models.path).",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to ireco.config.json (default: auto-detect in cwd).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose logging."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    for verb, help_text in (
        ("process", "Process a single PDF (parse + extract)."),
        ("run", "Alias of 'process'."),
    ):
        p = subparsers.add_parser(verb, help=help_text)
        p.add_argument("--file", required=True, help="Path to source PDF.")
        p.add_argument("-o", "--out", default=None, help="Output .vim.json path.")
        add_ocr_arguments(p)

    p_batch = subparsers.add_parser(
        "batch", help="Process every *.pdf in a directory."
    )
    p_batch.add_argument("--dir", required=True, help="Input directory.")
    p_batch.add_argument(
        "-o", "--out", default=None, help="Output directory for .vim.json files."
    )
    add_ocr_arguments(p_batch)

    p_task = subparsers.add_parser("task", help="Unified task contract operations.")
    task_sub = p_task.add_subparsers(dest="task_action", required=True)
    p_exec = task_sub.add_parser("execute", help="Execute a TaskRequest JSON.")
    p_exec.add_argument(
        "--file",
        default=None,
        help="Path to TaskRequest JSON file (omit to read from stdin).",
    )

    return parser


if __name__ == "__main__":
    raise SystemExit(main())
