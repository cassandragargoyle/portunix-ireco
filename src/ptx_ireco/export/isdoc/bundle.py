"""ISDOCX ZIP container — bundles the ISDOC XML with the source PDF.

Layout (per ADR-0007 + issue 006 §"ISDOCX bundle"):

::

    /<stem>.isdoc           — the XML (deflate)
    /<stem>.pdf             — the source PDF (stored, no recompression)
    /META-INF/manifest.xml  — ISDOCX manifest

PDFs are compressed internally; re-deflating wastes CPU on the
importing ERP for negligible size gains. We use ``ZIP_STORED`` for
the PDF and ``ZIP_DEFLATED`` for the XML / manifest.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

from ptx_ireco.export.isdoc.errors import ExportError

_MANIFEST_TEMPLATE = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">\n'
    '  <manifest:file-entry manifest:full-path="{isdoc_name}" manifest:media-type="text/xml"/>\n'
    '  <manifest:file-entry manifest:full-path="{pdf_name}" manifest:media-type="application/pdf"/>\n'
    "</manifest:manifest>\n"
)


def write(
    *,
    isdoc_path: str | Path,
    pdf_path: str | Path,
    out_path: str | Path,
) -> Path:
    """Write an ISDOCX ZIP at ``out_path`` from the given inputs.

    Raises:
        ExportError: ``pdf_path`` does not exist or is not a regular
            file.
    """
    isdoc = Path(isdoc_path)
    pdf = Path(pdf_path)
    out = Path(out_path)

    if not isdoc.is_file():
        raise ExportError(f"ISDOC file not found: {isdoc}")
    if not pdf.is_file():
        raise ExportError(f"Source PDF not found: {pdf}")

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    isdoc_name = isdoc.name
    pdf_name = pdf.name

    with zipfile.ZipFile(tmp, "w") as zf:
        zf.writestr(
            "META-INF/manifest.xml",
            _MANIFEST_TEMPLATE.format(isdoc_name=isdoc_name, pdf_name=pdf_name),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        zf.write(isdoc, arcname=isdoc_name, compress_type=zipfile.ZIP_DEFLATED)
        # PDF stored without recompression — already compressed.
        zf.write(pdf, arcname=pdf_name, compress_type=zipfile.ZIP_STORED)

    tmp.replace(out)
    try:
        os.chmod(out, 0o644)
    except OSError:
        pass
    return out
