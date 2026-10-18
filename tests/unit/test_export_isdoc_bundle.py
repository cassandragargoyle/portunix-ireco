"""Unit tests for ptx_ireco.export.isdoc.bundle."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from ptx_ireco.export.isdoc import bundle
from ptx_ireco.export.isdoc.errors import ExportError


def _write(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def test_write_produces_isdocx_with_three_entries(tmp_path: Path):
    isdoc = _write(tmp_path / "scan.isdoc", b"<Invoice/>")
    pdf = _write(tmp_path / "scan.pdf", b"%PDF-1.5\n%fakefake\n")
    out = tmp_path / "scan.isdocx"
    bundle.write(isdoc_path=isdoc, pdf_path=pdf, out_path=out)
    with zipfile.ZipFile(out) as zf:
        names = sorted(zf.namelist())
    assert names == ["META-INF/manifest.xml", "scan.isdoc", "scan.pdf"]


def test_write_pdf_is_stored_isdoc_is_deflated(tmp_path: Path):
    isdoc = _write(tmp_path / "x.isdoc", b"<Invoice/>")
    pdf = _write(tmp_path / "x.pdf", b"%PDF-1.5\n")
    out = tmp_path / "x.isdocx"
    bundle.write(isdoc_path=isdoc, pdf_path=pdf, out_path=out)
    with zipfile.ZipFile(out) as zf:
        info_pdf = zf.getinfo("x.pdf")
        info_isdoc = zf.getinfo("x.isdoc")
    assert info_pdf.compress_type == zipfile.ZIP_STORED
    assert info_isdoc.compress_type == zipfile.ZIP_DEFLATED


def test_manifest_lists_both_entries(tmp_path: Path):
    isdoc = _write(tmp_path / "x.isdoc", b"<Invoice/>")
    pdf = _write(tmp_path / "x.pdf", b"%PDF-1.5")
    out = tmp_path / "x.isdocx"
    bundle.write(isdoc_path=isdoc, pdf_path=pdf, out_path=out)
    with zipfile.ZipFile(out) as zf:
        manifest = zf.read("META-INF/manifest.xml").decode("utf-8")
    assert 'manifest:full-path="x.isdoc"' in manifest
    assert 'manifest:full-path="x.pdf"' in manifest


def test_write_rejects_missing_pdf(tmp_path: Path):
    isdoc = _write(tmp_path / "x.isdoc", b"<Invoice/>")
    out = tmp_path / "x.isdocx"
    with pytest.raises(ExportError):
        bundle.write(isdoc_path=isdoc, pdf_path=tmp_path / "missing.pdf", out_path=out)
