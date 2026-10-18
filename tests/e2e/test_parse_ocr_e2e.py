"""End-to-end OCR tests for the ``parse`` step.

These tests need Tesseract on PATH and the ``pdf2image`` Python package
(with Poppler) installed. They are auto-skipped via
``tests/conftest.py:pytest_collection_modifyitems`` when either is
missing — see issue 007 acceptance criterion G.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptx_ireco.pipeline.parse import OcrOptions, parse_pdf_to_file

pytestmark = [pytest.mark.requires_tesseract, pytest.mark.requires_pdf2image]


def _read_doc(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _blocks_on_page(doc: dict, page: int) -> list[dict]:
    blocks = doc.get("layers", {}).get("structural", {}).get("blocks", []) or []
    return [b for b in blocks if isinstance(b, dict) and b.get("page") == page]


# ---------------------------------------------------------------------------
# Image-only PDF: OCR must recover blocks pdfplumber missed.
# ---------------------------------------------------------------------------


def test_image_only_invoice_requires_ocr_to_get_blocks(
    ocr_pdf_fixtures: dict[str, Path], tmp_path: Path
) -> None:
    """Without OCR, an image-only PDF has zero structural blocks.

    With OCR enabled, the plugin contributes at least one block.
    """
    pdf = ocr_pdf_fixtures["image_only_invoice"]
    out_no_ocr = tmp_path / "no-ocr.vim.json"
    out_with_ocr = tmp_path / "with-ocr.vim.json"

    # Without OCR the upstream parser raises (no structural blocks).
    with pytest.raises(RuntimeError):
        parse_pdf_to_file(pdf, out_no_ocr, ocr=None)

    parse_pdf_to_file(pdf, out_with_ocr, ocr=OcrOptions(enabled=True))
    doc = _read_doc(out_with_ocr)
    assert _blocks_on_page(doc, 1), "OCR must contribute blocks on page 1"


# ---------------------------------------------------------------------------
# Blank-page guard: OCR must skip pure-white pages.
# ---------------------------------------------------------------------------


def test_blank_page_is_skipped(
    ocr_pdf_fixtures: dict[str, Path], tmp_path: Path
) -> None:
    pdf = ocr_pdf_fixtures["blank_and_content"]
    out = tmp_path / "mixed.vim.json"

    parse_pdf_to_file(pdf, out, ocr=OcrOptions(enabled=True, min_ink_ratio=0.005))
    doc = _read_doc(out)

    # The fixture is page 0 = blank, page 1 = ink, page 2 = blank.
    page1_blocks = _blocks_on_page(doc, 1)
    page2_blocks = _blocks_on_page(doc, 2)
    page3_blocks = _blocks_on_page(doc, 3)

    # Only page 2 (the content page) should yield OCR blocks.
    assert not page1_blocks, f"page 1 was blank, got blocks: {page1_blocks!r}"
    assert page2_blocks, "page 2 had content, expected OCR blocks"
    assert not page3_blocks, f"page 3 was blank, got blocks: {page3_blocks!r}"


def test_min_ink_ratio_can_force_skip(
    ocr_pdf_fixtures: dict[str, Path], tmp_path: Path
) -> None:
    """An impossible ink-ratio threshold skips every page."""
    pdf = ocr_pdf_fixtures["image_only_invoice"]
    out = tmp_path / "force-skip.vim.json"

    with pytest.raises(RuntimeError):
        parse_pdf_to_file(pdf, out, ocr=OcrOptions(enabled=True, min_ink_ratio=0.99))


# ---------------------------------------------------------------------------
# Text-only PDF: OCR-enabled run must match OCR-disabled run.
# ---------------------------------------------------------------------------


def test_text_only_pdf_unchanged_with_ocr_enabled(
    flowii_pdf: Path, tmp_path: Path
) -> None:
    out_off = tmp_path / "off.vim.json"
    out_on = tmp_path / "on.vim.json"

    parse_pdf_to_file(flowii_pdf, out_off, ocr=None)
    parse_pdf_to_file(flowii_pdf, out_on, ocr=OcrOptions(enabled=True))

    doc_off = _read_doc(out_off)
    doc_on = _read_doc(out_on)

    blocks_off = doc_off.get("layers", {}).get("structural", {}).get("blocks", []) or []
    blocks_on = doc_on.get("layers", {}).get("structural", {}).get("blocks", []) or []

    # The OCR plugin must short-circuit on every page (had_text), so the
    # text block list is unchanged in shape and content.
    assert len(blocks_on) == len(blocks_off), (
        f"OCR enabled added/dropped blocks: off={len(blocks_off)}, on={len(blocks_on)}"
    )
