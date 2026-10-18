"""Shared OCR argparse helpers for the driver and worker CLIs.

Both ``ptx-ireco`` and ``ptx-ireco-worker`` need to accept the same
``--ocr*`` flags so the watcher's ``cli`` backend can pass them through
in a subprocess. Keeping the argparse + precedence logic here prevents
the two CLIs from drifting apart.

The helpers are intentionally side-effect free:
- :func:`add_ocr_arguments` only mutates the parser it is given.
- :func:`build_ocr_options` is a pure function over an ``argparse.Namespace``
  + an optional config dict.
- :func:`ocr_options_to_cli_args` builds a flag list suitable for
  ``subprocess.run`` (used by the watcher's CLI dispatch backend).
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from typing import Any

from ptx_ireco.pipeline.parse import OcrOptions


def add_ocr_arguments(parser: argparse.ArgumentParser) -> None:
    """Register ``--ocr*`` flags on a subparser (e.g. ``parse`` / ``run``)."""
    parser.add_argument(
        "--ocr",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Enable per-page OCR fallback (Tesseract). "
            "--no-ocr forces OCR off (overrides config). "
            "Default: follow config.parse.ocr.enabled (off if not set)."
        ),
    )
    parser.add_argument(
        "--ocr-language",
        default=None,
        help="Tesseract language code(s), '+'-separated (e.g. 'eng+ces'). Default: 'eng'.",
    )
    parser.add_argument(
        "--ocr-dpi",
        type=int,
        default=None,
        help="Render DPI for the OCR pass. Default: 300.",
    )
    parser.add_argument(
        "--ocr-min-ink-ratio",
        type=float,
        default=None,
        help="Blank-page guard threshold (fraction of non-white pixels). Default: 0.005.",
    )
    parser.add_argument(
        "--ocr-mode",
        choices=("printed",),
        default=None,
        help="OCR mode. Only 'printed' is supported in v1.",
    )


def build_ocr_options(
    args: argparse.Namespace, cfg: dict[str, Any] | None
) -> OcrOptions | None:
    """Resolve OCR options from CLI flags + ``ireco.config.json`` ``parse.ocr``.

    Precedence: explicit CLI flag > config value > dataclass default.
    Returns ``None`` only when neither the config nor any CLI flag asks
    for OCR — preserving the "plugin not imported" semantics from
    :class:`OcrOptions`.
    """
    base = OcrOptions.from_config_dict(cfg)
    any_ocr_flag = any(
        getattr(args, attr, None) is not None
        for attr in ("ocr", "ocr_language", "ocr_dpi", "ocr_min_ink_ratio", "ocr_mode")
    )
    if base is None and not any_ocr_flag:
        return None
    if base is None:
        base = OcrOptions()

    overrides: dict[str, Any] = {}
    if getattr(args, "ocr", None) is True:
        overrides["enabled"] = True
    elif getattr(args, "ocr", None) is False:
        overrides["enabled"] = False
    if getattr(args, "ocr_language", None) is not None:
        overrides["language"] = args.ocr_language
    if getattr(args, "ocr_dpi", None) is not None:
        overrides["dpi"] = args.ocr_dpi
    if getattr(args, "ocr_min_ink_ratio", None) is not None:
        overrides["min_ink_ratio"] = args.ocr_min_ink_ratio
    if getattr(args, "ocr_mode", None) is not None:
        overrides["mode"] = args.ocr_mode

    return base if not overrides else replace(base, **overrides)


def ocr_options_to_cli_args(opts: OcrOptions | None) -> list[str]:
    """Reverse of :func:`build_ocr_options` — emit subprocess flags.

    Used by :mod:`ptx_ireco.watcher.dispatcher`'s ``cli`` backend to
    forward the configured OCR options to a ``ptx-ireco-worker run``
    subprocess. ``None`` returns an empty list (no flags appended; the
    worker will follow its own config / defaults).
    """
    if opts is None:
        return []
    args: list[str] = ["--ocr" if opts.enabled else "--no-ocr"]
    args.extend(["--ocr-language", opts.language])
    args.extend(["--ocr-dpi", str(opts.dpi)])
    args.extend(["--ocr-min-ink-ratio", str(opts.min_ink_ratio)])
    args.extend(["--ocr-mode", opts.mode])
    return args
