"""``ptx-ireco-watcher`` command-line interface.

Long-running file-system watcher daemon for the ireco invoice
recognition pipeline. Mirrors ``ptx-reco-watcher`` shape (issue #004,
ADR-0005).

Config-loading precedence (highest → lowest):

1. Explicit ``--config <path>``.
2. ``./ireco.config.json`` in cwd.
3. Built-in defaults (then ``--watch-dir`` and ``-o`` are required).

CLI flags override the loaded config, per-flag.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ptx_ireco import __version__
from ptx_ireco.config import (
    InvalidConfigError,
    UnsupportedVersionError,
    find_config,
    load_config_file,
)
from ptx_ireco.config.schema import IMPLEMENTED_DOC_TYPES
from ptx_ireco.watcher import (
    DispatchError,
    FileSystemMonitor,
    WatchConfig,
)

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_RESERVED_DOC_TYPE = 3
EXIT_CONFIG_INVALID = 4


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.backend == "grpc":
        print(
            "ptx-ireco-watcher: --backend grpc is reserved and not yet implemented",
            file=sys.stderr,
        )
        return EXIT_USAGE

    cfg, cfg_path = _resolve_config(args)
    if cfg is not None:
        reserved = [t for t in (cfg.get("doc_types") or []) if t not in IMPLEMENTED_DOC_TYPES]
        if reserved:
            print(
                "ptx-ireco-watcher: doc_types include reserved values that are "
                "not implemented yet: " + ", ".join(reserved),
                file=sys.stderr,
            )
            return EXIT_RESERVED_DOC_TYPE

    watch_cfg = WatchConfig.from_dict(cfg, config_path=cfg_path)
    watch_cfg = _apply_cli_overrides(watch_cfg, args)

    if not watch_cfg.watch_dirs:
        print(
            "ptx-ireco-watcher: no watch directory configured. "
            "Provide --watch-dir or set io.input_dir in ireco.config.json "
            "(authored via portunix-reco-studio).",
            file=sys.stderr,
        )
        return EXIT_USAGE

    if watch_cfg.output_dir is None:
        print(
            "ptx-ireco-watcher: no output directory. "
            "Provide -o or set io.output_dir in ireco.config.json.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    if watch_cfg.backend not in ("local", "cli"):
        # grpc handled above; anything else is a schema bug if we got here.
        print(
            f"ptx-ireco-watcher: backend {watch_cfg.backend!r} is not implemented",
            file=sys.stderr,
        )
        return EXIT_USAGE

    monitor = FileSystemMonitor(watch_cfg)
    try:
        monitor.start()
    except KeyboardInterrupt:
        # Already handled inside start()'s finally; treat as a clean exit.
        pass
    except DispatchError as exc:
        print(f"ptx-ireco-watcher: {exc}", file=sys.stderr)
        return EXIT_USAGE
    return EXIT_OK


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------


def _resolve_config(
    args: argparse.Namespace,
) -> tuple[dict | None, Path | None]:
    explicit: str | None = args.config
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


def _load_or_die(cfg_path: Path) -> dict:
    try:
        return load_config_file(cfg_path)
    except (InvalidConfigError, UnsupportedVersionError) as exc:
        print(f"config: {exc}", file=sys.stderr)
        sys.exit(EXIT_CONFIG_INVALID)


def _apply_cli_overrides(cfg: WatchConfig, args: argparse.Namespace) -> WatchConfig:
    overrides: dict = {}
    if args.watch_dir:
        overrides["watch_dirs"] = [Path(d) for d in args.watch_dir]
    if args.out is not None:
        overrides["output_dir"] = Path(args.out)
    if args.models is not None:
        overrides["models_path"] = Path(args.models)
    if args.backend is not None:
        overrides["backend"] = args.backend
    if args.workers is not None:
        overrides["workers"] = args.workers
    if args.cooldown is not None:
        overrides["cooldown_seconds"] = args.cooldown
    if args.patterns is not None:
        overrides["patterns"] = [p.strip() for p in args.patterns.split(",") if p.strip()]
    if args.no_recursive:
        overrides["recursive"] = False
    if args.events_log is not None:
        overrides["events_log"] = Path(args.events_log)
    if args.post_process is not None:
        # Empty string explicitly disables post-processing even when
        # the config enables it (per issue 006 §E acceptance criteria).
        if args.post_process == "":
            overrides["post_process"] = []
        else:
            overrides["post_process"] = [
                p.strip() for p in args.post_process.split(",") if p.strip()
            ]
    return cfg.with_overrides(**overrides)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ptx-ireco-watcher",
        description="File-system watcher daemon for the ireco pipeline.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ptx-ireco-watcher {__version__}",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to ireco.config.json (default: auto-detect in cwd).",
    )
    parser.add_argument(
        "--watch-dir",
        action="append",
        default=None,
        help="Directory to watch. Repeatable. Overrides io.input_dir.",
    )
    parser.add_argument(
        "-o",
        "--out",
        dest="out",
        default=None,
        help="Output directory for .vim.json results. Overrides io.output_dir.",
    )
    parser.add_argument(
        "--models",
        default=None,
        help="Repo root containing models/invoice/. Overrides models.path.",
    )
    parser.add_argument(
        "--backend",
        choices=("local", "cli", "grpc"),
        default=None,
        help="Dispatch backend (default: from config or 'local'). 'grpc' is reserved.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Pool size (>=1). 1 = sequential.",
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=None,
        help="Seconds between detection and dispatch.",
    )
    parser.add_argument(
        "--patterns",
        default=None,
        help='Comma-separated glob patterns (e.g. "*.pdf,*.PDF").',
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not watch subdirectories.",
    )
    parser.add_argument(
        "--events-log",
        default=None,
        help="Append JSON-lines event records to this file.",
    )
    parser.add_argument(
        "--post-process",
        default=None,
        help=(
            "Comma-separated post-process handlers to chain after "
            "scan.processed (e.g. 'export-isdoc'). Empty string "
            "explicitly disables post-processing. Overrides "
            "watcher.post_process from the config."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging.",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
