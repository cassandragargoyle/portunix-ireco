"""Schema constants for ``ireco.config.json`` v1.

The authoritative JSON Schema document lives at
``docs/schemas/ireco-config-1.0.json``. The constants here mirror the
enums and patterns the validator enforces so error messages stay in
sync with the schema file.
"""

from __future__ import annotations

import re
from pathlib import Path

CONFIG_VERSION = 1
CONFIG_SCHEMA_URL = "https://cassandragargoyle.example/ireco/config-1.0.json"

DOC_TYPES = ("invoice", "receipt", "delivery_note", "purchase_order")
IMPLEMENTED_DOC_TYPES = ("invoice",)
RESERVED_DOC_TYPES = tuple(t for t in DOC_TYPES if t not in IMPLEMENTED_DOC_TYPES)

TENANCY_MODES = ("multitenant", "known")
EXTRACTION_DEPTHS = ("header", "items")
ORDERS_SOURCES = ("local",)

WATCHER_BACKENDS = ("local", "cli", "grpc")
WATCHER_DEFAULT_BACKEND = "local"
WATCHER_DEFAULT_WORKERS = 1
WATCHER_DEFAULT_COOLDOWN_SECONDS = 1.0
WATCHER_DEFAULT_PATTERNS = ("*.pdf",)
WATCHER_DEFAULT_RECURSIVE = True
# issue 006 — post-processing handlers chained after scan.processed.
# Enum-of-one for now; future targets (export-xrechnung, …) extend it.
WATCHER_POST_PROCESS_HANDLERS = ("export-isdoc",)
EXPORT_ISDOC_FORMATS = ("isdoc", "isdocx")
EXPORT_ISDOC_PROFILES = ("minimal", "standard", "full")

# issue 007 — per-page OCR fallback in step 1. Defaults must match the
# `OcrOptions` dataclass in `ptx_ireco.pipeline.parse` so a missing
# `parse.ocr` section behaves identically to passing ``ocr=None``.
OCR_MODES = ("printed",)
OCR_DEFAULT_ENABLED = False
OCR_DEFAULT_LANGUAGE = "eng"
OCR_DEFAULT_DPI = 300
OCR_DEFAULT_MIN_INK_RATIO = 0.005
OCR_DEFAULT_MODE = "printed"
OCR_MIN_DPI = 72

ICO_PATTERN = re.compile(r"^[0-9]{8}$")
DIC_PATTERN = re.compile(r"^[A-Z]{2}[0-9A-Z]+$")
RECIPIENT_ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def schema_path() -> Path:
    """Return the absolute path to the bundled JSON Schema file.

    The file is shipped under ``docs/schemas/`` in the repository; this
    helper resolves it relative to the source tree so callers can read
    the schema (e.g. for ``$schema`` round-tripping in tests) without
    knowing the layout.
    """
    return Path(__file__).resolve().parents[3] / "docs" / "schemas" / "ireco-config-1.0.json"
