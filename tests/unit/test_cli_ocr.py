"""Unit tests for the OCR pieces of the ``ptx-ireco`` CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ptx_ireco.cli.main import (
    _build_ocr_options,
    _build_parser,
    _emit_ocr_discoverability_warn,
)
from ptx_ireco.pipeline.parse import OcrOptions


# ---------------------------------------------------------------------------
# Argparse — flag wiring
# ---------------------------------------------------------------------------


def test_parse_subparser_advertises_ocr_flags(capsys: pytest.CaptureFixture[str]) -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["parse", "--help"])
    out = capsys.readouterr().out
    for flag in ("--ocr", "--no-ocr", "--ocr-language", "--ocr-dpi", "--ocr-min-ink-ratio", "--ocr-mode"):
        assert flag in out, f"{flag} missing from `parse --help`"


def test_run_subparser_advertises_ocr_flags(capsys: pytest.CaptureFixture[str]) -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "--help"])
    out = capsys.readouterr().out
    for flag in ("--ocr", "--no-ocr", "--ocr-language", "--ocr-dpi", "--ocr-min-ink-ratio", "--ocr-mode"):
        assert flag in out, f"{flag} missing from `run --help`"


def test_no_ocr_flags_yields_none_by_default() -> None:
    parser = _build_parser()
    ns = parser.parse_args(["parse", "in.pdf", "-o", "out.vim.json"])
    assert ns.ocr is None
    assert ns.ocr_language is None
    assert ns.ocr_dpi is None
    assert ns.ocr_min_ink_ratio is None
    assert ns.ocr_mode is None


def test_ocr_and_no_ocr_are_mutually_exclusive() -> None:
    parser = _build_parser()
    # argparse's BooleanOptionalAction lets the last one win; the
    # important behavior is that both flags parse without crashing.
    ns = parser.parse_args(["parse", "in.pdf", "-o", "out.vim.json", "--ocr", "--no-ocr"])
    assert ns.ocr is False


# ---------------------------------------------------------------------------
# _build_ocr_options precedence
# ---------------------------------------------------------------------------


def _ns(**kwargs: Any) -> Any:
    parser = _build_parser()
    base_args = ["parse", "in.pdf", "-o", "out.vim.json"]
    for k, v in kwargs.items():
        flag = "--" + k.replace("_", "-")
        if isinstance(v, bool):
            base_args.append(flag if v else f"--no-{k.replace('_', '-')}")
        else:
            base_args.extend([flag, str(v)])
    return parser.parse_args(base_args)


def test_build_ocr_options_no_flag_no_config_returns_none() -> None:
    assert _build_ocr_options(_ns(), None) is None


def test_build_ocr_options_config_alone() -> None:
    cfg = {"parse": {"ocr": {"enabled": True, "language": "eng+ces"}}}
    opts = _build_ocr_options(_ns(), cfg)
    assert opts is not None and opts.enabled and opts.language == "eng+ces"


def test_build_ocr_options_cli_overrides_config() -> None:
    cfg = {"parse": {"ocr": {"enabled": True, "dpi": 200}}}
    opts = _build_ocr_options(_ns(ocr_dpi=600), cfg)
    assert opts is not None and opts.dpi == 600 and opts.enabled


def test_build_ocr_options_no_ocr_overrides_config() -> None:
    cfg = {"parse": {"ocr": {"enabled": True}}}
    opts = _build_ocr_options(_ns(ocr=False), cfg)
    assert opts is not None and opts.enabled is False


def test_build_ocr_options_ocr_flag_alone() -> None:
    """``--ocr`` with no config still produces enabled options at defaults."""
    opts = _build_ocr_options(_ns(ocr=True), None)
    assert opts == OcrOptions(enabled=True)


def test_build_ocr_options_sub_option_implies_options() -> None:
    """Setting ``--ocr-language`` without ``--ocr`` still builds options."""
    opts = _build_ocr_options(_ns(ocr_language="eng+ces"), None)
    assert opts is not None and opts.language == "eng+ces"
    # enabled stays at the dataclass default (False) — caller can still
    # pass --ocr to actually flip it.
    assert opts.enabled is False


# ---------------------------------------------------------------------------
# _emit_ocr_discoverability_warn
# ---------------------------------------------------------------------------


def _write_doc(path: Path, doc: dict[str, Any]) -> None:
    path.write_text(json.dumps(doc), encoding="utf-8")


def test_warn_emitted_when_ocr_off_and_pages_missing_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "x.vim.json"
    _write_doc(
        out,
        {
            "layers": {
                "physical": {"pages": [{"index": 0}, {"index": 1}, {"index": 2}]},
                "structural": {"blocks": [{"page": 2}]},
            }
        },
    )
    _emit_ocr_discoverability_warn(out, ocr=None)
    err = capsys.readouterr().err
    assert "2/3 pages have no extracted text" in err
    assert "--ocr" in err


def test_warn_silent_when_ocr_enabled(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "x.vim.json"
    _write_doc(
        out,
        {
            "layers": {
                "physical": {"pages": [{"index": 0}]},
                "structural": {"blocks": []},
            }
        },
    )
    _emit_ocr_discoverability_warn(out, ocr=OcrOptions(enabled=True))
    assert capsys.readouterr().err == ""


def test_warn_silent_when_all_pages_covered(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "x.vim.json"
    _write_doc(
        out,
        {
            "layers": {
                "physical": {"pages": [{"index": 0}]},
                "structural": {"blocks": [{"page": 1}]},
            }
        },
    )
    _emit_ocr_discoverability_warn(out, ocr=None)
    assert capsys.readouterr().err == ""


def test_warn_silent_when_no_pages(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "x.vim.json"
    _write_doc(out, {"layers": {}})
    _emit_ocr_discoverability_warn(out, ocr=None)
    assert capsys.readouterr().err == ""


def test_warn_silent_when_file_unreadable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "missing.vim.json"
    _emit_ocr_discoverability_warn(out, ocr=None)
    # Helper must never raise, just log debug and return.
    assert capsys.readouterr().err == ""
