"""Pure-Python pipeline façade — single source of truth for parse/extract/run.

Both the driver CLI (``ptx-ireco``) and the worker CLI
(``ptx-ireco-worker``) call into these functions. The façade contains
no argparse, no ``print``, no ``sys.exit``: callers are responsible
for argument parsing, stdout formatting, and exit-code translation.

Function signatures intentionally mirror the existing private helpers
the CLI used to call directly (:func:`ptx_ireco.pipeline.parse.parse_pdf_to_file`
and :func:`ptx_ireco.pipeline.extract.extract_file`) so the diff
against existing code stays minimal.
"""

from __future__ import annotations

from pathlib import Path

from ptx_ireco.pipeline.extract import (
    ExtractionOptions,
    ExtractionResult,
    ModelPaths,
    extract_file,
)
from ptx_ireco.pipeline.parse import OcrOptions, parse_pdf_to_file


def parse(
    pdf_path: str | Path,
    out: str | Path,
    *,
    verbose: bool = False,
    ocr: OcrOptions | None = None,
) -> Path:
    """Step 1: parse a PDF into ``.vim.json`` (physical + structural).

    Args:
        pdf_path: Source PDF file.
        out: Destination ``.vim.json`` path.
        verbose: Forward verbose flag to the underlying parser.
        ocr: Optional OCR fallback knobs (issue 007). ``None`` keeps the
            parser OCR-free.

    Returns:
        Resolved output path (same as ``out`` after :class:`Path`
        normalization).

    Raises:
        FileNotFoundError: ``pdf_path`` does not exist.
        RuntimeError: parser produced no structural blocks.
    """
    return parse_pdf_to_file(pdf_path, out, verbose=verbose, ocr=ocr)


def extract(
    vim_path: str | Path,
    *,
    out: str | Path | None = None,
    in_place: bool = False,
    models: str | Path | None = None,
    options: ExtractionOptions | None = None,
) -> ExtractionResult:
    """Step 2: read a ``.vim.json``, populate semantic layer, write back.

    Args:
        vim_path: Input ``.vim.json`` (output of step 1).
        out: Destination path. Defaults to in-place write.
        in_place: Force in-place write even when ``out`` is provided
            (CLI convenience). When both are given, ``in_place`` wins.
        models: Repo root containing ``models/invoice/{templates,profiles,extraction}/``.
            Defaults to cwd. Resolved through :class:`ModelPaths`.
        options: Optional :class:`ExtractionOptions` (e.g. configured
            recipients for ``known`` tenancy).

    Returns:
        :class:`ExtractionResult` with template match, profile, entities,
        and an optional ``recipient_id``.

    Raises:
        ExtractionError: extraction could not complete (no template,
            no profile, flexylayout failure, …).
    """
    in_path = Path(vim_path)
    target = in_path if in_place or out is None else Path(out)
    model_paths = ModelPaths.default(Path(models) if models is not None else Path.cwd())
    return extract_file(in_path, model_paths, out_path=target, options=options)


def run(
    pdf_path: str | Path,
    out: str | Path,
    *,
    models: str | Path | None = None,
    options: ExtractionOptions | None = None,
    verbose: bool = False,
    ocr: OcrOptions | None = None,
) -> ExtractionResult:
    """Step 1 + step 2 in one call. Writes to ``out`` first (parse), then
    re-writes the same path in place (extract).

    Mirrors today's ``ptx-ireco run`` behavior: the file at ``out`` is
    written twice — first with ``physical`` + ``structural`` only, then
    in-place with ``semantic`` populated.
    """
    parse(pdf_path, out, verbose=verbose, ocr=ocr)
    return extract(out, in_place=True, models=models, options=options)


__all__ = ["ExtractionOptions", "ExtractionResult", "ModelPaths", "OcrOptions", "extract", "parse", "run"]
