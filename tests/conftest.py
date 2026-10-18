"""Pytest fixtures shared across the suite."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip OCR tests when their hard prerequisites are absent.

    The ``requires_tesseract`` and ``requires_pdf2image`` markers are
    registered in ``pyproject.toml``. Tests carrying them only run when
    both the Tesseract binary and the ``pdf2image`` Python package are
    available locally; otherwise they are skipped (not failed) per
    issue 007 acceptance criterion G.
    """
    has_tesseract = shutil.which("tesseract") is not None
    try:
        import pdf2image  # noqa: F401

        has_pdf2image = True
    except ImportError:
        has_pdf2image = False

    skip_tesseract = pytest.mark.skip(reason="tesseract binary not available on PATH")
    skip_pdf2image = pytest.mark.skip(reason="pdf2image (with Poppler) not installed")
    for item in items:
        if "requires_tesseract" in item.keywords and not has_tesseract:
            item.add_marker(skip_tesseract)
        if "requires_pdf2image" in item.keywords and not has_pdf2image:
            item.add_marker(skip_pdf2image)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the project root (parent of ``tests/``)."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def models_dir(repo_root: Path) -> Path:
    return repo_root / "models" / "invoice"


@pytest.fixture(scope="session")
def samples_dir(repo_root: Path) -> Path:
    return repo_root / "samples" / "invoice"


@pytest.fixture(scope="session")
def flowii_pdf(samples_dir: Path) -> Path:
    pdf = samples_dir / "flowii-FA_26050001.pdf"
    if not pdf.is_file():
        pytest.skip(f"Sample PDF missing: {pdf}")
    return pdf


@pytest.fixture(scope="session")
def flowii_vim_java(samples_dir: Path) -> Path:
    """Java-produced reference VIM file shipped in samples/.

    Used by step-2-only tests so they don't depend on the (still
    redesign-required) Python text_block_extractor.
    """
    vim = samples_dir / "flowii-FA_26050001.pdf.vim.java.json"
    if not vim.is_file():
        pytest.skip(f"Reference VIM missing: {vim}")
    return vim


# ---------------------------------------------------------------------------
# Issue 007 — synthetic OCR fixtures generated lazily via PIL.
#
# Keeping the binary blobs out of git: each session re-renders a tiny
# image-only PDF set into a temp directory. Pillow can write multi-page
# PDFs directly, which is enough for the per-page guard tests.
# ---------------------------------------------------------------------------


_OCR_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Medium.ttf",
    "/Library/Fonts/Arial.ttf",  # macOS
    "C:\\Windows\\Fonts\\arial.ttf",  # Windows
)


def _load_ocr_test_font() -> "object | None":  # type: ignore[type-arg]
    """Return a PIL TrueType font usable for OCR fixtures, or ``None``.

    Tests skip when no candidate font is found. Size 48 keeps the
    rendered ink well above the default ``min_ink_ratio`` of 0.005 and
    is large enough for Tesseract to read on a 75 DPI probe.
    """
    from PIL import ImageFont

    for path in _OCR_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size=48)
        except (OSError, IOError):
            continue
    return None


@pytest.fixture(scope="session")
def ocr_pdf_fixtures(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Generate synthetic image-only PDFs for OCR tests.

    Returns a mapping with the following entries:

    - ``blank``: single-page all-white PDF (ink ratio ≈ 0).
    - ``image_only_invoice``: single-page rasterized invoice (ink > 0).
    - ``blank_and_content``: 3-page PDF (blank / invoice / blank).

    All files live under a session-scoped tmp dir so they survive across
    tests within one run and are cleaned up afterwards. Image-only PDFs
    have no text layer, so pdfplumber returns zero blocks for them; this
    is exactly the condition the OCR plugin is meant to recover from.
    """
    out_dir = tmp_path_factory.mktemp("ocr_fixtures")
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:  # pragma: no cover - PIL is a transitive dep
        pytest.skip("PIL/Pillow not installed; OCR fixtures cannot be generated")

    # Tesseract needs a font at a readable size. PIL's default bitmap font
    # renders too small (≈ 0.2 % ink ratio at 75 DPI), which falls below
    # the production default ``min_ink_ratio=0.005`` and triggers a
    # false "blank_page" skip in fixture pages we want OCR to process.
    # Pick the first TTF available; skip the OCR fixture set entirely
    # when no usable font is found.
    font = _load_ocr_test_font()
    if font is None:
        pytest.skip(
            "no TrueType font available for OCR test fixtures "
            "(install fonts-liberation, fonts-dejavu-core or similar)"
        )

    size = (612, 792)  # Letter @ 72 DPI

    blank = Image.new("RGB", size, "white")
    invoice = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(invoice)
    # Render synthetic invoice text large enough for Tesseract to pick
    # up reliably and for the rendered page to clear the ink-ratio gate.
    lines = [
        "INVOICE 26050001",
        "Vendor: Test s.r.o.",
        "Total: 1234.56 CZK",
    ]
    for i, line in enumerate(lines):
        draw.text((40, 80 + i * 100), line, fill="black", font=font)

    blank_pdf = out_dir / "blank.pdf"
    invoice_pdf = out_dir / "image-only-invoice.pdf"
    multi_pdf = out_dir / "blank-and-content.pdf"

    blank.save(blank_pdf, "PDF", resolution=72.0)
    invoice.save(invoice_pdf, "PDF", resolution=72.0)
    blank.save(
        multi_pdf,
        "PDF",
        resolution=72.0,
        save_all=True,
        append_images=[invoice, blank],
    )

    return {
        "blank": blank_pdf,
        "image_only_invoice": invoice_pdf,
        "blank_and_content": multi_pdf,
    }
