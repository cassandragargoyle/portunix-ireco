"""Unit tests for ``ptx_ireco.worker.api.pipeline`` façade.

The façade is a thin layer over the existing ``parse_pdf_to_file`` and
``extract_file`` helpers; full integration coverage lives in the e2e
suite. These tests focus on argument-translation behavior the façade
adds (``in_place`` vs ``out``, ``models`` defaulting).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ptx_ireco.pipeline.extract import ModelPaths
from ptx_ireco.worker.api import pipeline as worker_pipeline


def test_parse_delegates_to_parse_pdf_to_file(tmp_path: Path) -> None:
    out = tmp_path / "scan.vim.json"
    with patch("ptx_ireco.worker.api.pipeline.parse_pdf_to_file") as mocked:
        mocked.return_value = out
        result = worker_pipeline.parse(tmp_path / "scan.pdf", out, verbose=True)
    mocked.assert_called_once()
    assert result == out
    args, kwargs = mocked.call_args
    assert args[0] == tmp_path / "scan.pdf"
    assert args[1] == out
    # issue 007 added ``ocr`` kwarg; default ``None`` preserves the
    # OCR-off behavior of pre-007 callers.
    assert kwargs == {"verbose": True, "ocr": None}


def test_extract_in_place_default_when_out_is_none(tmp_path: Path) -> None:
    vim = tmp_path / "doc.vim.json"
    vim.write_text("{}", encoding="utf-8")
    with patch("ptx_ireco.worker.api.pipeline.extract_file") as mocked:
        worker_pipeline.extract(vim)
    _, kwargs = mocked.call_args
    assert kwargs["out_path"] == vim


def test_extract_writes_to_out_when_provided(tmp_path: Path) -> None:
    vim = tmp_path / "doc.vim.json"
    out = tmp_path / "doc.copy.vim.json"
    vim.write_text("{}", encoding="utf-8")
    with patch("ptx_ireco.worker.api.pipeline.extract_file") as mocked:
        worker_pipeline.extract(vim, out=out)
    _, kwargs = mocked.call_args
    assert kwargs["out_path"] == out


def test_extract_in_place_wins_over_out(tmp_path: Path) -> None:
    vim = tmp_path / "doc.vim.json"
    out = tmp_path / "doc.copy.vim.json"
    vim.write_text("{}", encoding="utf-8")
    with patch("ptx_ireco.worker.api.pipeline.extract_file") as mocked:
        worker_pipeline.extract(vim, out=out, in_place=True)
    _, kwargs = mocked.call_args
    assert kwargs["out_path"] == vim


def test_extract_models_defaults_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    vim = tmp_path / "doc.vim.json"
    vim.write_text("{}", encoding="utf-8")
    with patch("ptx_ireco.worker.api.pipeline.extract_file") as mocked:
        worker_pipeline.extract(vim)
    args, kwargs = mocked.call_args
    model_paths: ModelPaths = args[1]
    assert model_paths.templates == tmp_path / "models" / "invoice" / "templates"


def test_extract_uses_explicit_models(tmp_path: Path) -> None:
    vim = tmp_path / "doc.vim.json"
    vim.write_text("{}", encoding="utf-8")
    custom = tmp_path / "custom-root"
    with patch("ptx_ireco.worker.api.pipeline.extract_file") as mocked:
        worker_pipeline.extract(vim, models=custom)
    args, _ = mocked.call_args
    model_paths: ModelPaths = args[1]
    assert model_paths.templates == custom / "models" / "invoice" / "templates"


def test_run_invokes_parse_then_extract(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"
    out = tmp_path / "scan.vim.json"
    with (
        patch("ptx_ireco.worker.api.pipeline.parse_pdf_to_file") as mocked_parse,
        patch("ptx_ireco.worker.api.pipeline.extract_file") as mocked_extract,
    ):
        mocked_parse.return_value = out
        worker_pipeline.run(pdf, out)
    mocked_parse.assert_called_once()
    mocked_extract.assert_called_once()
    _, ex_kwargs = mocked_extract.call_args
    assert ex_kwargs["out_path"] == out


def test_extract_against_real_sample(repo_root: Path, flowii_vim_java: Path, tmp_path: Path) -> None:
    """Smoke-test the façade end-to-end with the shipped reference VIM."""
    import shutil

    target = tmp_path / "flowii.vim.json"
    shutil.copy(flowii_vim_java, target)

    result = worker_pipeline.extract(target, models=repo_root)

    assert result.detected_country == "CZE"
    assert result.template_match is not None
    types = {e.type for e in result.entities}
    assert {"invoice_header", "issuer", "buyer"} <= types

    # In-place write — reload to confirm side effect.
    after = json.loads(target.read_text(encoding="utf-8"))
    assert len(after["layers"]["semantic"]["entities"]) >= 5
