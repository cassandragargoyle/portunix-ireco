"""Unit tests for ptx_ireco.export.isdoc.writer."""

from __future__ import annotations

from pathlib import Path

from lxml import etree  # type: ignore[import-untyped]

from ptx_ireco.export.isdoc import writer


def _sample_root() -> etree._Element:
    nsmap = {None: "http://isdoc.cz/namespace/2013"}
    root = etree.Element("{http://isdoc.cz/namespace/2013}Invoice", nsmap=nsmap)
    root.set("version", "6.0.2")
    child = etree.SubElement(root, "{http://isdoc.cz/namespace/2013}ID")
    child.text = "FA_001"
    return root


def test_serialize_includes_xml_decl_utf8():
    out = writer.serialize(_sample_root())
    assert out.startswith(b"<?xml version='1.0' encoding='utf-8'")


def test_serialize_no_pretty_print():
    out = writer.serialize(_sample_root())
    # Pretty printing would insert newlines + indentation between
    # parent and child elements.
    assert b"\n  <" not in out
    assert b"<ID>FA_001</ID>" in out


def test_serialize_deterministic():
    a = writer.serialize(_sample_root())
    b = writer.serialize(_sample_root())
    assert a == b


def test_write_atomic(tmp_path: Path):
    target = tmp_path / "out.isdoc"
    writer.write(_sample_root(), target)
    assert target.is_file()
    assert b"FA_001" in target.read_bytes()
    # No leftover .tmp file.
    assert list(tmp_path.glob("*.tmp")) == []
