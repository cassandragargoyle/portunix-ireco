"""Semantic entity model used by the extract step.

Mirrors ``ptx_reco.vim.model.vim_document.SemanticEntity`` but keeps
this package independent of the upstream dataclass — extract works on
plain dicts so the same code can serialize to ``.vim.json`` without an
intermediate object graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SemanticEntity:
    """One semantic entity to be written into ``layers.semantic.entities``.

    Attributes:
        type: Entity kind, e.g. ``"invoice_header"``, ``"issuer"``,
            ``"buyer"``, ``"totals"``, ``"vat_breakdown"``, ``"payment"``.
        source_block: ID of the structural block this entity was derived
            from (provenance per VIM design principle).
        source_barcode: ID of the structural barcode this entity was
            derived from (alternative provenance).
        fields: Decoded key/value fields.
        confidence: Confidence in the extraction, ``0.0``–``1.0``.
    """

    type: str
    source_block: str | None = None
    source_barcode: str | None = None
    fields: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the dict shape used in ``.vim.json``."""
        out: dict[str, Any] = {"type": self.type}
        if self.source_block is not None:
            out["source_block"] = self.source_block
        if self.source_barcode is not None:
            out["source_barcode"] = self.source_barcode
        out["fields"] = dict(self.fields)
        out["confidence"] = self.confidence
        return out
