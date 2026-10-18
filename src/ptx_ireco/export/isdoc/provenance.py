"""Provenance sidecar emitter — tracks ISDOC element → source block.

The mapper instantiates one :class:`ProvenanceAccumulator`, calls
:meth:`record` for every value it writes into the ISDOC tree, and the
api façade calls :meth:`write` after the XML has been emitted to
produce ``<stem>.isdoc.provenance.json`` next to it.

The sidecar is **never** embedded into the conformant XML — see
ADR-0007 § "Provenance sidecar".
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProvenanceEntry:
    """One ISDOC element ↔ source-block mapping."""

    isdoc_xpath: str
    value: str
    bt: str | None = None
    bg: str | None = None
    source_block: str | None = None
    source_barcode: str | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"isdoc_xpath": self.isdoc_xpath, "value": self.value}
        if self.bt is not None:
            out["bt"] = self.bt
        if self.bg is not None:
            out["bg"] = self.bg
        if self.source_block is not None:
            out["source_block"] = self.source_block
        if self.source_barcode is not None:
            out["source_barcode"] = self.source_barcode
        if self.confidence is not None:
            out["confidence"] = self.confidence
        return out


@dataclass
class ProvenanceAccumulator:
    """Collects provenance entries during mapping.

    Insertion order is preserved on :meth:`write` so re-runs produce
    byte-identical output (the sidecar is part of the audit trail and
    must be diffable).
    """

    isdoc_version: str
    vim_source: str
    vim_version: str | None = None
    entries: list[ProvenanceEntry] = field(default_factory=list)

    def record(
        self,
        isdoc_xpath: str,
        value: str,
        *,
        bt: str | None = None,
        bg: str | None = None,
        source_block: str | None = None,
        source_barcode: str | None = None,
        confidence: float | None = None,
    ) -> None:
        self.entries.append(
            ProvenanceEntry(
                isdoc_xpath=isdoc_xpath,
                value=value,
                bt=bt,
                bg=bg,
                source_block=source_block,
                source_barcode=source_barcode,
                confidence=confidence,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "isdoc_version": self.isdoc_version,
            "vim_source": self.vim_source,
        }
        if self.vim_version is not None:
            out["vim_version"] = self.vim_version
        out["entries"] = [e.to_dict() for e in self.entries]
        return out

    def write(self, path: str | Path) -> Path:
        """Serialise to ``path``. Creates parent dir; mode 0644."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
        tmp = p.with_suffix(p.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            f.write(text)
            f.write("\n")
        tmp.replace(p)
        try:
            os.chmod(p, 0o644)
        except OSError:
            pass
        return p
