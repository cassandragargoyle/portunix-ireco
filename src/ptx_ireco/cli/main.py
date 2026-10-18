"""``ptx-ireco`` command-line interface.

Subcommands:

- ``init`` — **deprecated**. Authoring of ``ireco.config.json`` moved
  to ``portunix-reco-studio`` (see studio INT-037 / issue #005). The
  command is kept as a discoverable breadcrumb that prints a pointer
  at the new location and exits non-zero.
- ``parse <pdf> -o <out.vim.json>`` — step 1.
- ``extract <vim.json> [--in-place | -o <out>]`` — step 2.
- ``run <pdf> -o <out.vim.json>`` — step 1 followed by step 2 (writes
  the same file twice — first with ``physical`` + ``structural``, then
  in-place with ``semantic``).

The ``--models <dir>`` flag overrides where the CLI looks for
``models/invoice/{templates,profiles,extraction}/``. By default it
resolves them relative to the current working directory.

When an ``ireco.config.json`` is present in the current directory, the
``parse``/``extract``/``run`` commands use ``io.input_dir`` /
``io.output_dir`` as defaults (explicit positional/`-o` values still
win) and pass the configured invoice recipients to the extractor so
``known`` tenancy can attach a ``document.recipient_id`` to the VIM
output.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from ptx_ireco import __version__
from ptx_ireco.config import (
    InvalidConfigError,
    UnsupportedVersionError,
    find_config,
    load_config_file,
)
from ptx_ireco.config.schema import IMPLEMENTED_DOC_TYPES, RESERVED_DOC_TYPES
from ptx_ireco.export.isdoc import api as isdoc_api
from ptx_ireco.export.isdoc.api import ValidationFailed
from ptx_ireco.export.isdoc.errors import ExportError
from ptx_ireco.cli._ocr_args import (
    add_ocr_arguments as _add_ocr_arguments,
)
from ptx_ireco.cli._ocr_args import (
    build_ocr_options as _build_ocr_options,
)
from ptx_ireco.pipeline.extract import ExtractionError
from ptx_ireco.pipeline.parse import OcrOptions, count_pages_without_text
from ptx_ireco.vim.io import read_vim_json
from ptx_ireco.worker.api import pipeline as worker_pipeline
from ptx_ireco.worker.api.pipeline import ExtractionOptions, ModelPaths

logger = logging.getLogger(__name__)

EXIT_RESERVED_DOC_TYPE = 3
EXIT_CONFIG_INVALID = 4
EXIT_INIT_MOVED = 2
EXIT_VALIDATION_ERROR = 4

INIT_MOVED_MESSAGE = (
    "ptx-ireco init is no longer available — authoring of ireco.config.json "
    "moved to portunix-reco-studio in INT-037 (2026-05-10).\n"
    "Use: ptx-reco-studio ireco-config init [--from-file <path>]"
)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.command == "init":
        return _cmd_init(args)
    if args.command == "parse":
        return _cmd_parse(args)
    if args.command == "extract":
        return _cmd_extract(args)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "export":
        return _cmd_export(args)

    parser.print_help()
    return 1


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _cmd_init(args: argparse.Namespace) -> int:
    """Deprecation breadcrumb — authoring moved to portunix-reco-studio.

    See issue #005 / studio INT-037. Always prints the pointer message
    on stderr and exits non-zero, regardless of any positional or flag
    arguments the user happened to pass.
    """
    del args  # accepted but ignored — see issue #005
    print(INIT_MOVED_MESSAGE, file=sys.stderr)
    return EXIT_INIT_MOVED


def _cmd_parse(args: argparse.Namespace) -> int:
    cfg = _maybe_load_cwd_config(verbose=args.verbose)
    if cfg is None:
        out = Path(args.out)
    else:
        _check_implemented_doc_types(cfg)
        out = _resolve_io_path(args.out, cfg, "output_dir")
        if out is None:
            print("parse: -o is required (no output_dir in ireco.config.json)", file=sys.stderr)
            return 2
    ocr = _build_ocr_options(args, cfg)
    worker_pipeline.parse(args.input, out, verbose=args.verbose, ocr=ocr)
    _emit_ocr_discoverability_warn(out, ocr)
    print(f"parse: wrote {out}")
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    cfg = _maybe_load_cwd_config(verbose=args.verbose)
    if cfg is not None:
        try:
            _check_implemented_doc_types(cfg)
        except _ReservedDocTypeError as exc:
            print(f"extract: {exc}", file=sys.stderr)
            return EXIT_RESERVED_DOC_TYPE

    in_path = Path(args.input)
    out = in_path if args.in_place or args.out is None else Path(args.out)
    model_paths = _model_paths(args)
    extraction_options = _build_extraction_options(cfg)
    try:
        result = worker_pipeline.extract(
            in_path,
            out=out,
            in_place=args.in_place or args.out is None,
            models=args.models,
            options=extraction_options,
        )
    except ExtractionError as exc:
        print(f"extract: {exc}", file=sys.stderr)
        return 2

    summary: dict[str, Any] = {
        "template_match": result.template_match.template_id if result.template_match else None,
        "country": result.detected_country,
        "profile": str(result.profile.path.relative_to(model_paths.profiles.parent.parent)),
        "flexylayout": str(result.flexylayout_path.relative_to(model_paths.extraction.parent.parent)),
        "entities": [e.type for e in result.entities],
        "out": str(out),
    }
    if result.recipient_id is not None:
        summary["recipient_id"] = result.recipient_id
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    """Step 3: read a populated .vim.json, emit an ISDOC artefact."""
    vim_path = Path(args.input)
    out_dir = Path(args.out) if args.out else None
    models = Path(args.models) if args.models else None
    source_pdf = Path(args.source_pdf) if args.source_pdf else None
    try:
        result = isdoc_api.export(
            vim_path,
            out_dir=out_dir,
            format=args.format,
            profile=args.profile,
            allow_incomplete=args.allow_incomplete,
            models=models,
            source_pdf=source_pdf,
        )
    except ValidationFailed as exc:
        print(f"export: validation failed ({len(exc.errors)} error(s))", file=sys.stderr)
        for err in exc.errors:
            print(f"  - [{err.rule}] {err.message}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR
    except ExportError as exc:
        print(f"export: {exc}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    summary: dict[str, Any] = {
        "format": result.format,
        "profile": result.profile,
        "isdoc": str(result.isdoc_path),
        "provenance": str(result.provenance_path),
        "validations": dict(result.validations),
    }
    if result.bundle_path is not None:
        summary["bundle"] = str(result.bundle_path)
    if result.errors:
        summary["validation_errors"] = [e.to_dict() for e in result.errors]
        print("export: completed with validation warnings (see stderr)", file=sys.stderr)
    if args.verbose or result.errors:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"export: wrote {result.isdoc_path}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    cfg = _maybe_load_cwd_config(verbose=args.verbose)
    if cfg is None:
        out = Path(args.out)
    else:
        try:
            _check_implemented_doc_types(cfg)
        except _ReservedDocTypeError as exc:
            print(f"run: {exc}", file=sys.stderr)
            return EXIT_RESERVED_DOC_TYPE
        out = _resolve_io_path(args.out, cfg, "output_dir")
        if out is None:
            print("run: -o is required (no output_dir in ireco.config.json)", file=sys.stderr)
            return 2
    ocr = _build_ocr_options(args, cfg)
    worker_pipeline.parse(args.input, out, verbose=args.verbose, ocr=ocr)
    _emit_ocr_discoverability_warn(out, ocr)
    extract_args = argparse.Namespace(
        input=str(out),
        in_place=True,
        out=None,
        models=args.models,
        verbose=args.verbose,
    )
    return _cmd_extract(extract_args)


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------


class _ReservedDocTypeError(RuntimeError):
    pass


def _maybe_load_cwd_config(*, verbose: bool) -> dict[str, Any] | None:
    """Return the parsed cwd config or ``None`` when no file is present.

    Surfaces validation errors to the user and re-raises them so the
    caller exits non-zero. We deliberately *do not* swallow validation
    failures — a present but invalid config is a hard error.
    """
    cwd = Path.cwd()
    cfg_path = find_config(cwd)
    if cfg_path is None:
        return None
    try:
        cfg = load_config_file(cfg_path)
    except (InvalidConfigError, UnsupportedVersionError) as exc:
        print(f"config: {exc}", file=sys.stderr)
        sys.exit(EXIT_CONFIG_INVALID)
    if verbose:
        logger.debug("loaded ireco.config.json from %s", cfg_path)
    return cfg


def _check_implemented_doc_types(cfg: dict[str, Any]) -> None:
    declared = cfg.get("doc_types") or []
    not_implemented = [t for t in declared if t not in IMPLEMENTED_DOC_TYPES]
    if not_implemented:
        raise _ReservedDocTypeError(
            "doc_types include reserved values that are not implemented yet: "
            + ", ".join(not_implemented)
            + " (only " + ", ".join(IMPLEMENTED_DOC_TYPES) + " is supported in this build)"
        )


def _resolve_io_path(
    cli_value: str | None, cfg: dict[str, Any], key: str
) -> Path | None:
    """CLI value wins over config; absent from both ⇒ ``None``."""
    if cli_value:
        return Path(cli_value)
    io = cfg.get("io") or {}
    if key in io:
        return Path(io[key])
    return None


def _build_extraction_options(cfg: dict[str, Any] | None) -> ExtractionOptions | None:
    if cfg is None:
        return None
    invoice = cfg.get("invoice") or {}
    if invoice.get("tenancy") != "known":
        return None
    recipients = invoice.get("recipients") or []
    return ExtractionOptions(recipients=recipients)


def _model_paths(args: argparse.Namespace) -> ModelPaths:
    return ModelPaths.default(args.models or Path.cwd())


def _emit_ocr_discoverability_warn(vim_path: Path, ocr: OcrOptions | None) -> None:
    """Stderr hint when parse left zero-text pages and OCR was off.

    Loud enough to be noticed once; quiet enough to ignore — never
    raises, never blocks. When OCR was enabled or the parsed file
    cannot be re-read, the function returns silently.
    """
    if ocr is not None and ocr.enabled:
        return
    try:
        doc = read_vim_json(vim_path)
    except Exception as exc:  # noqa: BLE001 — diagnostic helper, never fail the parse
        logger.debug("OCR discoverability warn skipped: %s", exc)
        return
    no_text, total = count_pages_without_text(doc)
    if no_text <= 0 or total <= 0:
        return
    print(
        f"WARN: {no_text}/{total} pages have no extracted text. "
        f"Re-run with --ocr to recover them.",
        file=sys.stderr,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ptx-ireco",
        description="Two-step invoice pipeline (parse → extract) on top of VIM.",
    )
    parser.add_argument("--version", action="version", version=f"ptx-ireco {__version__}")
    parser.add_argument(
        "--models",
        type=Path,
        default=None,
        help="Repo root containing models/invoice/ (default: cwd).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose logging."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ``init`` is intentionally retained as a deprecation breadcrumb
    # (see issue #005). It accepts no flags and always prints a pointer
    # at the studio replacement on stderr before exiting non-zero.
    subparsers.add_parser(
        "init",
        help=(
            "Deprecated — moved to `ptx-reco-studio ireco-config init` "
            "(see studio INT-037)."
        ),
    )

    p_parse = subparsers.add_parser(
        "parse", help="Step 1: PDF → .vim.json (physical + structural)."
    )
    p_parse.add_argument("input", help="Path to source PDF.")
    p_parse.add_argument("-o", "--out", required=False, help="Output .vim.json path.")
    _add_ocr_arguments(p_parse)

    p_extract = subparsers.add_parser(
        "extract",
        help="Step 2: read .vim.json, populate semantic layer, write back.",
    )
    p_extract.add_argument("input", help="Input .vim.json (output of step 1).")
    group = p_extract.add_mutually_exclusive_group()
    group.add_argument("--in-place", action="store_true", help="Write back into the same file (default).")
    group.add_argument("-o", "--out", help="Write to a different path instead of in-place.")

    p_run = subparsers.add_parser("run", help="Step 1 + step 2 in one go.")
    p_run.add_argument("input", help="Path to source PDF.")
    p_run.add_argument("-o", "--out", required=False, help="Output .vim.json path.")
    _add_ocr_arguments(p_run)

    p_export = subparsers.add_parser(
        "export",
        help="Step 3: .vim.json → ISDOC 6.0.2 (XML or ISDOCX bundle).",
    )
    p_export.add_argument("input", help="Input .vim.json (output of step 2).")
    p_export.add_argument(
        "-o",
        "--out",
        default=None,
        help="Output directory (default: alongside the .vim.json).",
    )
    p_export.add_argument(
        "--format",
        choices=("isdoc", "isdocx"),
        default="isdoc",
        help="Output format. 'isdocx' wraps the XML + source PDF in a ZIP.",
    )
    p_export.add_argument(
        "--profile",
        choices=("minimal", "standard", "full"),
        default="standard",
        help="Completeness profile.",
    )
    p_export.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Write artefacts even when validation fails (failures still surfaced).",
    )
    p_export.add_argument(
        "--source-pdf",
        default=None,
        help="Source PDF for --format isdocx (default: <stem>.pdf next to input).",
    )

    # Reserved-but-not-implemented subcommands could land here; for now
    # keep the parser minimal and only surface what is implemented.
    _ = RESERVED_DOC_TYPES  # silence unused import in lint configurations

    return parser


if __name__ == "__main__":
    raise SystemExit(main())
