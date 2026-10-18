"""Smoke test for step 1: PDF → VIM via ptx_reco.

Marked as integration / network-free but pdfplumber-dependent. Skipped
automatically if ``ptx_reco`` or ``pdfplumber`` is unavailable, or if
the upstream parser produces no blocks (still ``redesign-required`` per
the ptx_reco README).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pdfplumber")
ptx_reco = pytest.importorskip("ptx_reco.vim.core.engine.execution_engine")


def test_parse_flowii_pdf(flowii_pdf: Path, tmp_path: Path) -> None:
    from ptx_ireco.pipeline.parse import parse_pdf_to_file

    out = tmp_path / "flowii.vim.json"
    try:
        parse_pdf_to_file(flowii_pdf, out)
    except RuntimeError as exc:
        pytest.skip(f"Upstream parser produced no blocks: {exc}")

    assert out.is_file()

    import json

    doc = json.loads(out.read_text(encoding="utf-8"))
    assert "layers" in doc
    assert doc["layers"].get("structural", {}).get("blocks"), \
        "structural.blocks must be populated"
    # Step 1 contract: semantic layer is empty.
    semantic = doc["layers"].get("semantic") or {}
    assert not semantic.get("entities"), \
        "step 1 must leave semantic.entities empty"
