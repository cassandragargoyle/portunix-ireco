"""Deterministic ISDOC XML serialisation.

The writer produces UTF-8 XML with a stable byte layout so snapshot
tests can byte-compare output across runs. Pretty-print is OFF on
purpose — the snapshot test in §H of issue 006 relies on this.
"""

from __future__ import annotations

import os
from pathlib import Path

from lxml import etree  # type: ignore[import-untyped]


def serialize(root: etree._Element) -> bytes:
    """Return the canonicalised XML bytes for ``root``.

    Always emits an XML declaration with UTF-8 encoding; never
    ``standalone="..."``.
    """
    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="utf-8",
        pretty_print=False,
        standalone=False,
    )


def write(root: etree._Element, path: str | Path) -> Path:
    """Atomically write ``serialize(root)`` to ``path``. Mode 0644."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = serialize(root)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(p)
    try:
        os.chmod(p, 0o644)
    except OSError:
        pass
    return p
