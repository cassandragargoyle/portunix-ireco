"""End-to-end tests for the ISDOC export pipeline."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from ptx_ireco.export.isdoc import api
from ptx_ireco.export.isdoc.api import ValidationFailed


@pytest.fixture(scope="module")
def fixture_vim() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "export" / "isdoc" / "flowii-FA_26050001.vim.json"


@pytest.fixture(scope="module")
def incomplete_vim() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "export" / "isdoc" / "incomplete-missing-bt-112.vim.json"


def test_export_writes_isdoc_and_provenance(tmp_path: Path, fixture_vim: Path, repo_root: Path):
    target = tmp_path / "out"
    target.mkdir()
    result = api.export(
        fixture_vim,
        out_dir=target,
        format="isdoc",
        profile="standard",
        allow_incomplete=True,  # field_map is intentionally not yet 100% XSD-conformant
        models=repo_root,
    )
    assert result.format == "isdoc"
    assert result.isdoc_path.is_file()
    assert result.isdoc_path.suffix == ".isdoc"
    assert result.provenance_path.is_file()
    assert result.bundle_path is None
    # Required-field gate must pass for the standard profile on this fixture.
    assert result.validations["required"] == "pass"


def test_export_isdocx_bundles_pdf(tmp_path: Path, fixture_vim: Path, repo_root: Path):
    fake_pdf = tmp_path / "flowii-FA_26050001.pdf"
    fake_pdf.write_bytes(b"%PDF-1.5\n%fake\n")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = api.export(
        fixture_vim,
        out_dir=out_dir,
        format="isdocx",
        profile="standard",
        allow_incomplete=True,
        models=repo_root,
        source_pdf=fake_pdf,
    )
    assert result.bundle_path is not None
    assert result.bundle_path.is_file()
    with zipfile.ZipFile(result.bundle_path) as zf:
        names = sorted(zf.namelist())
    assert "META-INF/manifest.xml" in names
    assert "flowii-FA_26050001.isdoc" in names
    assert "flowii-FA_26050001.pdf" in names


def test_export_provenance_contains_bt_entries(tmp_path: Path, fixture_vim: Path, repo_root: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = api.export(
        fixture_vim,
        out_dir=out_dir,
        profile="standard",
        allow_incomplete=True,
        models=repo_root,
    )
    payload = json.loads(result.provenance_path.read_text(encoding="utf-8"))
    bts = {entry.get("bt") for entry in payload["entries"] if entry.get("bt")}
    # A few canonical BTs we know the field map covers.
    assert "BT-1" in bts   # invoice number
    assert "BT-2" in bts   # issue date
    assert "BT-112" in bts  # total with VAT


def test_export_minimal_strips_invoice_lines(tmp_path: Path, fixture_vim: Path, repo_root: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = api.export(
        fixture_vim,
        out_dir=out_dir,
        profile="minimal",
        allow_incomplete=True,
        models=repo_root,
    )
    text = result.isdoc_path.read_text(encoding="utf-8")
    assert "<InvoiceLine>" not in text


def test_export_allow_incomplete_returns_errors(tmp_path: Path, incomplete_vim: Path, repo_root: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = api.export(
        incomplete_vim,
        out_dir=out_dir,
        profile="standard",
        allow_incomplete=True,
        models=repo_root,
    )
    # required gate must fail because BT-112 / line / breakdown are missing.
    assert result.validations.get("required") == "fail"
    assert any(e.rule == "required" for e in result.errors)


def test_export_strict_raises_on_incomplete(tmp_path: Path, incomplete_vim: Path, repo_root: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    with pytest.raises(ValidationFailed) as exc_info:
        api.export(
            incomplete_vim,
            out_dir=out_dir,
            profile="standard",
            allow_incomplete=False,
            models=repo_root,
        )
    assert exc_info.value.errors  # all errors aggregated, not just the first


def test_export_rejects_nonexistent_out_dir(tmp_path: Path, fixture_vim: Path, repo_root: Path):
    bad = tmp_path / "does" / "not" / "exist"
    with pytest.raises(Exception):
        api.export(fixture_vim, out_dir=bad, models=repo_root, allow_incomplete=True)
