"""Step 1: parse a source document (PDF) into a ``.vim.json`` dict.

Delegates to :mod:`ptx_reco.vim` — this package does no PDF parsing of
its own. The output dict contains ``physical`` + ``structural`` (and
optional ``toc``) layers; the ``semantic`` layer is left empty so that
:func:`ptx_ireco.pipeline.extract.extract` can populate it later.

OCR fallback (issue 007) is opt-in via :class:`OcrOptions`. When
enabled, ``ptx_reco.vim.extractors.ocr.OcrExtractorPlugin`` is registered
and contributes blocks only for pages where pdfplumber produced none
and the rendered page passes the ink-ratio gate.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Literal

from ptx_ireco.vim.io import VimDoc, write_vim_json

logger = logging.getLogger(__name__)

OcrMode = Literal["printed"]


@dataclass(frozen=True)
class OcrOptions:
    """Knobs for the per-page OCR fallback in step 1.

    Defaults are tuned so a caller can pass ``OcrOptions()`` and get a
    safe printed-text Tesseract run at 300 DPI with a 0.5 % ink-ratio
    blank-page guard. Passing ``ocr=None`` (the default) keeps parsing
    OCR-free — the plugin is not even imported.
    """

    enabled: bool = False
    language: str = "eng"
    dpi: int = 300
    min_ink_ratio: float = 0.005
    mode: OcrMode = "printed"

    @classmethod
    def from_config_dict(cls, cfg: dict[str, Any] | None) -> "OcrOptions | None":
        """Build options from an ``ireco.config.json`` ``parse.ocr`` block.

        Returns ``None`` when no ``parse.ocr`` is configured so callers
        can preserve "OCR off + plugin not imported" semantics. Any
        missing field falls back to the dataclass default. The caller
        is responsible for validating the input shape (typically via
        :func:`ptx_ireco.config.validate_config`).
        """
        if not cfg:
            return None
        parse_cfg = cfg.get("parse") or {}
        ocr_cfg = parse_cfg.get("ocr")
        if not ocr_cfg:
            return None
        defaults = cls()
        return cls(
            enabled=bool(ocr_cfg.get("enabled", defaults.enabled)),
            language=str(ocr_cfg.get("language", defaults.language)),
            dpi=int(ocr_cfg.get("dpi", defaults.dpi)),
            min_ink_ratio=float(ocr_cfg.get("min_ink_ratio", defaults.min_ink_ratio)),
            mode=ocr_cfg.get("mode", defaults.mode),
        )


def parse_pdf(
    pdf_path: str | Path,
    *,
    verbose: bool = False,
    ocr: OcrOptions | None = None,
) -> VimDoc:
    """Parse a PDF into a VIM dict (step 1).

    Args:
        pdf_path: Path to the source PDF.
        verbose: Forward verbose flag to ``ptx_reco`` extractors.
        ocr: OCR fallback options. ``None`` (default) keeps OCR off and
            does not import the plugin. Pass ``OcrOptions(enabled=True)``
            to register the OCR extractor; it runs only on pages with no
            pdfplumber text blocks that pass the ink-ratio gate.

    Returns:
        VIM dict with populated ``physical`` and ``structural`` layers.
        The ``semantic`` layer is intentionally absent or empty.

    Raises:
        FileNotFoundError: ``pdf_path`` does not exist.
        RuntimeError: ``ptx_reco`` could not produce any blocks.
    """
    pdf = Path(pdf_path)
    if not pdf.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf}")

    pdf_bytes = pdf.read_bytes()
    vim_doc_obj = _run_ptx_reco(pdf_bytes, source_name=pdf.name, verbose=verbose, ocr=ocr)
    doc_dict = _vim_to_dict(vim_doc_obj)

    # Step 1 must NOT pre-populate semantic. Strip whatever ptx_reco's
    # default header detector wrote — that lives in step 2 here.
    layers = doc_dict.setdefault("layers", {})
    layers["semantic"] = {"entities": []}

    blocks = layers.get("structural", {}).get("blocks") or []
    if not blocks:
        raise RuntimeError(
            f"ptx_reco produced no structural blocks for {pdf}. "
            "Check that pdfplumber is installed and the PDF is text-based."
        )

    return doc_dict


def parse_pdf_to_file(
    pdf_path: str | Path,
    out_path: str | Path,
    *,
    verbose: bool = False,
    ocr: OcrOptions | None = None,
) -> Path:
    """Parse a PDF and write the VIM dict to ``out_path``.

    Returns the resolved output path.
    """
    doc = parse_pdf(pdf_path, verbose=verbose, ocr=ocr)
    out = Path(out_path)
    write_vim_json(out, doc)
    return out


def count_pages_without_text(vim_doc: VimDoc) -> tuple[int, int]:
    """Return ``(pages_without_text, total_pages)`` for a parsed VIM dict.

    A page counts as "without text" when no entry in
    ``layers.structural.blocks`` references it via the block's ``page``
    field. OCR-derived blocks are included in the count, so calling this
    after an OCR-enabled parse reflects post-OCR coverage.
    """
    layers = vim_doc.get("layers") or {}
    physical = layers.get("physical") or {}
    pages = physical.get("pages") or []
    structural = layers.get("structural") or {}
    blocks = structural.get("blocks") or []

    total = len(pages)
    if total == 0:
        return 0, 0

    pages_with_blocks: set[int] = set()
    for block in blocks:
        page_num = block.get("page") if isinstance(block, dict) else getattr(block, "page", None)
        if isinstance(page_num, int) and page_num > 0:
            pages_with_blocks.add(page_num)

    expected = {i for i in range(1, total + 1)}
    missing = expected - pages_with_blocks
    return len(missing), total


def _run_ptx_reco(
    pdf_bytes: bytes,
    *,
    source_name: str,
    verbose: bool,
    ocr: OcrOptions | None,
) -> Any:
    """Invoke ptx_reco's execution engine on ``pdf_bytes``.

    Imported lazily so the rest of the package works even if ptx_reco's
    optional dependencies (e.g. pdfplumber) are missing — only ``parse``
    pulls them in.
    """
    from ptx_reco.vim.core.engine.execution_engine import ExecutionEngine
    from ptx_reco.vim.core.plugin_registry import PluginRegistry
    from ptx_reco.vim.extractors.fulltext.text_block_extractor import (
        TextBlockExtractorPlugin,
    )

    registry = PluginRegistry()
    registry.register_extractor(TextBlockExtractorPlugin())

    # Try to register optional extractors; failure to import shouldn't
    # break parsing of a text-only PDF.
    _try_register_optional_extractors(registry, ocr=ocr)

    engine = ExecutionEngine(registry)
    return engine.process(pdf_bytes, source_name=source_name, verbose=verbose)


def _try_register_optional_extractors(registry: Any, *, ocr: OcrOptions | None) -> None:
    """Best-effort registration of barcode / table / graphics / toc / ocr extractors.

    OCR is added only when ``ocr.enabled`` is true; otherwise the
    extractor module is not imported, so callers without Tesseract /
    pdf2image / Poppler installed never see those imports.
    """
    optional: tuple[tuple[str, str, dict[str, Any]], ...] = (
        ("ptx_reco.vim.extractors.barcode.extractor", "BarcodeExtractorPlugin", {}),
        ("ptx_reco.vim.extractors.table.extractor", "TableExtractorPlugin", {}),
        ("ptx_reco.vim.extractors.graphics.extractor", "GraphicsExtractorPlugin", {}),
        ("ptx_reco.vim.extractors.toc.extractor", "TocExtractorPlugin", {}),
        ("ptx_reco.vim.extractors.fulltext.metadata_extractor", "MetadataExtractorPlugin", {}),
    )
    if ocr is not None and ocr.enabled:
        optional = optional + (
            (
                "ptx_reco.vim.extractors.ocr.extractor",
                "OcrExtractorPlugin",
                {
                    "enabled": True,
                    "language": ocr.language,
                    "dpi": ocr.dpi,
                    "min_ink_ratio": ocr.min_ink_ratio,
                    "mode": ocr.mode,
                },
            ),
        )
    for module_path, class_name, kwargs in optional:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            registry.register_extractor(cls(**kwargs) if kwargs else cls())
        except Exception as exc:  # noqa: BLE001 — optional, log and skip
            logger.debug("Optional extractor %s skipped: %s", class_name, exc)


def _vim_to_dict(vim_doc: Any) -> dict[str, Any]:
    """Convert a ptx_reco ``VimDocument`` dataclass tree into a JSON-ready dict.

    Uses ``dataclasses.asdict`` recursively, then prunes ``None`` values
    and empty optional containers to keep the output tidy.
    """
    if not is_dataclass(vim_doc):
        raise TypeError(f"Expected a dataclass, got {type(vim_doc).__name__}")
    raw = asdict(vim_doc)
    return _prune(raw)


def _prune(value: Any) -> Any:
    """Recursively drop ``None`` values and convert nested mappings/lists."""
    if isinstance(value, dict):
        return {k: _prune(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_prune(v) for v in value]
    return value
