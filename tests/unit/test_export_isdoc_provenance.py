"""Unit tests for ptx_ireco.export.isdoc.provenance."""

from __future__ import annotations

import json
from pathlib import Path

from ptx_ireco.export.isdoc.provenance import ProvenanceAccumulator, ProvenanceEntry


def test_record_then_to_dict_preserves_order(tmp_path: Path):
    acc = ProvenanceAccumulator(isdoc_version="6.0.2", vim_source="x.vim.json")
    acc.record("/Invoice/ID", "FA_001", bt="BT-1", source_block="block_3", confidence=0.9)
    acc.record("/Invoice/IssueDate", "2026-05-12", bt="BT-2", source_block="block_4", confidence=0.95)
    out = acc.to_dict()
    assert out["isdoc_version"] == "6.0.2"
    assert out["vim_source"] == "x.vim.json"
    assert [e["isdoc_xpath"] for e in out["entries"]] == [
        "/Invoice/ID",
        "/Invoice/IssueDate",
    ]
    assert out["entries"][0]["bt"] == "BT-1"
    assert out["entries"][0]["confidence"] == 0.9


def test_write_creates_utf8_indented_json(tmp_path: Path):
    acc = ProvenanceAccumulator(isdoc_version="6.0.2", vim_source="x.vim.json")
    acc.record("/Invoice/ID", "Česká firma s.r.o.", bt="BT-27")
    target = tmp_path / "out.provenance.json"
    written = acc.write(target)
    assert written == target
    text = target.read_text(encoding="utf-8")
    assert "Česká firma" in text  # ensure_ascii=False preserved
    parsed = json.loads(text)
    assert parsed["entries"][0]["value"] == "Česká firma s.r.o."


def test_provenance_entry_to_dict_omits_none_keys():
    e = ProvenanceEntry(isdoc_xpath="/x", value="v")
    d = e.to_dict()
    assert d == {"isdoc_xpath": "/x", "value": "v"}
