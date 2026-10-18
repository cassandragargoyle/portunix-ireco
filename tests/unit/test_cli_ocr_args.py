"""Tests for :mod:`ptx_ireco.cli._ocr_args` shared between the driver
and worker CLIs (issue 007 / G2).

The existing `test_cli_ocr.py` covers the driver path via
`cli.main._build_ocr_options` (re-exported from this module); these
tests target the canonical surface and the worker CLI advertising.
"""

from __future__ import annotations

import argparse

import pytest

from ptx_ireco.cli._ocr_args import (
    add_ocr_arguments,
    build_ocr_options,
    ocr_options_to_cli_args,
)
from ptx_ireco.pipeline.parse import OcrOptions


def _make_parser_with_ocr() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    add_ocr_arguments(parser)
    return parser


# ---------------------------------------------------------------------------
# add_ocr_arguments
# ---------------------------------------------------------------------------


def test_add_ocr_arguments_registers_all_flags() -> None:
    parser = _make_parser_with_ocr()
    ns = parser.parse_args([])
    for attr in ("ocr", "ocr_language", "ocr_dpi", "ocr_min_ink_ratio", "ocr_mode"):
        assert getattr(ns, attr) is None, f"{attr} should default to None"


def test_add_ocr_arguments_parses_full_flag_set() -> None:
    parser = _make_parser_with_ocr()
    ns = parser.parse_args(
        [
            "--ocr",
            "--ocr-language",
            "eng+ces",
            "--ocr-dpi",
            "400",
            "--ocr-min-ink-ratio",
            "0.02",
            "--ocr-mode",
            "printed",
        ]
    )
    assert ns.ocr is True
    assert ns.ocr_language == "eng+ces"
    assert ns.ocr_dpi == 400
    assert ns.ocr_min_ink_ratio == 0.02
    assert ns.ocr_mode == "printed"


def test_add_ocr_arguments_rejects_unknown_mode() -> None:
    parser = _make_parser_with_ocr()
    with pytest.raises(SystemExit):
        parser.parse_args(["--ocr-mode", "handwritten"])


# ---------------------------------------------------------------------------
# build_ocr_options — duplicates the cli.main coverage but at the shared
# helper level so refactors keep the contract.
# ---------------------------------------------------------------------------


def test_build_ocr_options_no_flag_no_config() -> None:
    parser = _make_parser_with_ocr()
    ns = parser.parse_args([])
    assert build_ocr_options(ns, None) is None


def test_build_ocr_options_cli_overrides_config_dpi() -> None:
    parser = _make_parser_with_ocr()
    ns = parser.parse_args(["--ocr-dpi", "600"])
    opts = build_ocr_options(ns, {"parse": {"ocr": {"enabled": True, "dpi": 200}}})
    assert opts is not None and opts.dpi == 600 and opts.enabled


# ---------------------------------------------------------------------------
# ocr_options_to_cli_args — used by watcher's cli backend.
# ---------------------------------------------------------------------------


def test_ocr_options_to_cli_args_returns_empty_for_none() -> None:
    assert ocr_options_to_cli_args(None) == []


def test_ocr_options_to_cli_args_emits_no_ocr_when_disabled() -> None:
    args = ocr_options_to_cli_args(OcrOptions(enabled=False))
    assert "--no-ocr" in args
    assert "--ocr" not in args


def test_ocr_options_to_cli_args_round_trips_full_options() -> None:
    opts = OcrOptions(
        enabled=True, language="eng+ces", dpi=450, min_ink_ratio=0.02, mode="printed"
    )
    args = ocr_options_to_cli_args(opts)

    parser = _make_parser_with_ocr()
    ns = parser.parse_args(args)
    rebuilt = build_ocr_options(ns, None)
    assert rebuilt == opts


# ---------------------------------------------------------------------------
# Worker CLI advertises the flags on `process`, `run`, and `batch`.
# ---------------------------------------------------------------------------


def test_worker_parser_advertises_ocr_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from ptx_ireco.cli.worker_main import _build_parser

    parser = _build_parser()
    for verb in ("run", "process", "batch"):
        with pytest.raises(SystemExit):
            parser.parse_args([verb, "--help"])
        out = capsys.readouterr().out
        for flag in (
            "--ocr",
            "--no-ocr",
            "--ocr-language",
            "--ocr-dpi",
            "--ocr-min-ink-ratio",
            "--ocr-mode",
        ):
            assert flag in out, f"{flag} missing from `ptx-ireco-worker {verb} --help`"
