"""Flexylayout interpreter — turn structural blocks into semantic entities.

A *flexylayout* is a JSON file under
``models/invoice/extraction/<country>/<id>.json`` describing how to map
structural-block evidence onto :class:`SemanticEntity` records. See
:mod:`ptx_ireco.invoice` README for the schema.

The interpreter is intentionally small. Each entity declaration has:

- ``type`` — entity kind written into the output.
- ``anchor`` — strategy for finding the *source block* whose ID becomes
  the entity's ``source_block``. Anchor failure means the entity is
  skipped (no partial entities are emitted).
- ``fields`` — list of field rules that pull values from the document.
- ``confidence`` — written verbatim into the entity.
- ``required`` (optional, default ``False``) — when ``True``, missing
  the entity is treated as a hard error by the caller.

Anchor strategies:

- ``{"any_block_contains": "<substring>"}`` — first structural block
  whose joined header+content contains the substring.
- ``{"block_with_header": "<substring>"}`` — first block whose
  ``header`` contains the substring.
- ``{"block_after_header": "<substring>"}`` — block immediately
  *after* (in document order) the block whose header matches.
- ``{"any_block_regex": "<regex>"}`` — first block whose joined
  header+content matches the regex.
- ``{"block_after_header_matching": {"header_pattern": "<sub>",
  "block_regex": "<rx>"}}`` — first block *after* the header-bearing
  block (in document order) whose joined text matches ``block_regex``.
  Useful when a section header (e.g. ``Odběratel:``) precedes several
  unrelated blocks before the one carrying the actual content.

Field ``from`` strategies:

- ``"global"`` — search the whole document text.
- ``"anchor_block"`` — search the anchor block's joined header+content.
- ``"anchor_block_line"`` — pull a specific 0-based line from the
  anchor block's content (use ``"index"``).
- ``"block_after_header"`` — like the anchor strategy of the same name,
  but resolved per field (use ``"header_pattern"`` and either ``regex``
  or ``index``).

Field value transforms:

- ``"cz_date_iso"`` — ``9.5.2026`` → ``2026-05-09``.
- ``"normalize_amount"`` — ``"1 210 000,00 Kč"`` → ``"1210000.00"``.
- ``"strip"`` — trim whitespace.
- ``"currency_code"`` — map ``"Kč"`` → ``"CZK"``, ``"€"`` → ``"EUR"``,
  ``"$"`` → ``"USD"``, ``"£"`` → ``"GBP"``; ISO codes (``"CZK"``,
  ``"EUR"`` …) pass through unchanged.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ptx_ireco.vim.io import VimDoc, get_structural_blocks
from ptx_ireco.vim.semantic import SemanticEntity

logger = logging.getLogger(__name__)


class FlexyExtractionError(RuntimeError):
    """Raised when a required entity cannot be extracted."""


@dataclass
class _Block:
    """Internal view of a structural block with derived helpers."""

    id: str
    header: str
    content: list[str]
    index: int

    @property
    def joined(self) -> str:
        """Header + content joined with newlines (for regex/contains scans)."""
        parts: list[str] = []
        if self.header:
            parts.append(self.header)
        parts.extend(self.content)
        return "\n".join(parts)


def load_flexylayout(path: str | Path) -> dict[str, Any]:
    """Load a flexylayout JSON file from disk."""
    p = Path(path)
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def find_flexylayout(
    extraction_root: str | Path,
    country: str,
    flexylayout_id: str | None = None,
) -> Path:
    """Locate the flexylayout file for ``country`` (and optional explicit id).

    Lookup order:

    1. If ``flexylayout_id`` is given, ``<root>/<country>/<id>.json``.
    2. Otherwise pick the lexicographically first ``*.json`` under
       ``<root>/<country>/``.

    Args:
        extraction_root: Path to ``models/invoice/extraction/``.
        country: ISO-3166 alpha-3 (case-insensitive).
        flexylayout_id: Optional explicit flexylayout filename stem.

    Raises:
        FileNotFoundError: no flexylayout matched.
    """
    iso = country.lower()
    base = Path(extraction_root) / iso
    if not base.is_dir():
        raise FileNotFoundError(f"No flexylayout directory for country {country!r}: {base}")

    if flexylayout_id:
        candidate = base / f"{flexylayout_id}.json"
        if not candidate.is_file():
            raise FileNotFoundError(f"Flexylayout not found: {candidate}")
        return candidate

    candidates = sorted(base.glob("*.json"))
    if not candidates:
        raise FileNotFoundError(f"No flexylayouts under {base}")
    return candidates[0]


def run_flexylayout(
    vim_doc: VimDoc, flexylayout: dict[str, Any]
) -> list[SemanticEntity]:
    """Apply ``flexylayout`` to ``vim_doc`` and return semantic entities.

    Args:
        vim_doc: Parsed VIM dict (output of step 1).
        flexylayout: Loaded flexylayout JSON.

    Returns:
        Ordered list of :class:`SemanticEntity` instances. Empty if no
        anchors matched. Caller writes them into ``layers.semantic.entities``.

    Raises:
        FlexyExtractionError: a ``required`` entity could not be anchored.
    """
    blocks = _wrap_blocks(vim_doc)
    if not blocks:
        return []

    document_text = "\n".join(b.joined for b in blocks)
    entities: list[SemanticEntity] = []

    for entity_def in flexylayout.get("entities") or []:
        entity = _extract_entity(entity_def, blocks, document_text)
        if entity is not None:
            entities.append(entity)
        elif entity_def.get("required"):
            raise FlexyExtractionError(
                f"Required entity {entity_def.get('type')!r} could not be anchored"
            )

    return entities


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------


def _extract_entity(
    entity_def: dict[str, Any],
    blocks: list[_Block],
    document_text: str,
) -> SemanticEntity | None:
    entity_type = entity_def.get("type")
    if not entity_type:
        logger.warning("Skipping entity with no type: %r", entity_def)
        return None

    anchor_block = _resolve_anchor(entity_def.get("anchor") or {}, blocks)
    if anchor_block is None and entity_def.get("anchor"):
        # Anchor was requested but not found → entity is not extractable.
        return None

    entity = SemanticEntity(
        type=str(entity_type),
        source_block=anchor_block.id if anchor_block else None,
        confidence=float(entity_def.get("confidence", 0.0)),
    )

    for field_def in entity_def.get("fields") or []:
        name = field_def.get("name")
        if not name:
            continue
        value = _resolve_field(field_def, anchor_block, blocks, document_text)
        if value is not None:
            entity.fields[name] = value

    # If we asked for fields but extracted nothing, still return the
    # entity as long as we have an anchor — the caller can decide how
    # to interpret a partial match. An entity with no fields and no
    # anchor is meaningless, so drop it.
    if not entity.fields and anchor_block is None:
        return None
    return entity


# ---------------------------------------------------------------------------
# Anchor resolution
# ---------------------------------------------------------------------------


def _resolve_anchor(
    anchor: dict[str, Any], blocks: list[_Block]
) -> _Block | None:
    if not anchor:
        return None

    if "any_block_contains" in anchor:
        needle = str(anchor["any_block_contains"])
        for b in blocks:
            if needle in b.joined:
                return b
        return None

    if "block_with_header" in anchor:
        needle = str(anchor["block_with_header"])
        for b in blocks:
            if b.header and needle in b.header:
                return b
        return None

    if "block_after_header" in anchor:
        needle = str(anchor["block_after_header"])
        for b in blocks:
            if b.header and needle in b.header:
                # First non-empty block strictly after.
                for follower in blocks[b.index + 1 :]:
                    if follower.content or follower.header:
                        return follower
        return None

    if "any_block_regex" in anchor:
        try:
            rx = re.compile(str(anchor["any_block_regex"]))
        except re.error as exc:
            logger.warning("Bad anchor regex %r: %s", anchor["any_block_regex"], exc)
            return None
        for b in blocks:
            if rx.search(b.joined):
                return b
        return None

    if "block_after_header_matching" in anchor:
        spec = anchor["block_after_header_matching"]
        header_pattern = str(spec.get("header_pattern", ""))
        block_regex = spec.get("block_regex")
        if not header_pattern or not block_regex:
            logger.warning(
                "block_after_header_matching needs header_pattern + block_regex: %r",
                spec,
            )
            return None
        try:
            rx = re.compile(str(block_regex))
        except re.error as exc:
            logger.warning("Bad block_regex %r: %s", block_regex, exc)
            return None
        for header_block in blocks:
            if header_block.header and header_pattern in header_block.header:
                for follower in blocks[header_block.index + 1 :]:
                    if rx.search(follower.joined):
                        return follower
        return None

    logger.warning("Unknown anchor strategy: %r", anchor)
    return None


# ---------------------------------------------------------------------------
# Field resolution
# ---------------------------------------------------------------------------


def _resolve_field(
    field_def: dict[str, Any],
    anchor_block: _Block | None,
    blocks: list[_Block],
    document_text: str,
) -> str | None:
    source = field_def.get("from", "global")
    transform_name = field_def.get("transform")
    transform = _TRANSFORMS.get(transform_name) if transform_name else None

    raw: str | None = None

    if source == "global":
        raw = _regex_pick(field_def, document_text)
    elif source == "anchor_block":
        if anchor_block is None:
            return None
        raw = _regex_pick(field_def, anchor_block.joined)
    elif source == "anchor_block_line":
        if anchor_block is None:
            return None
        raw = _line_pick(field_def, anchor_block)
    elif source == "block_after_header":
        target = _block_after_header(field_def, blocks)
        if target is None:
            return None
        if "regex" in field_def or "pattern" in field_def:
            raw = _regex_pick(field_def, target.joined)
        else:
            raw = _line_pick(field_def, target)
    else:
        logger.warning("Unknown field source %r in %r", source, field_def)
        return None

    if raw is None:
        return None

    if transform is not None:
        try:
            return transform(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Transform %s failed on %r: %s", transform_name, raw, exc)
            return None
    return raw.strip()


def _regex_pick(field_def: dict[str, Any], haystack: str) -> str | None:
    pattern = field_def.get("regex") or field_def.get("pattern")
    if not pattern:
        return field_def.get("static")
    try:
        match = re.search(pattern, haystack)
    except re.error as exc:
        logger.warning("Bad field regex %r: %s", pattern, exc)
        return None
    if match is None:
        return None
    group = field_def.get("group", 1) if match.groups() else 0
    try:
        return match.group(group)
    except IndexError:
        logger.warning("Field regex group %s out of range for %r", group, pattern)
        return None


def _line_pick(field_def: dict[str, Any], block: _Block) -> str | None:
    index_raw = field_def.get("index")
    if index_raw is None:
        return None
    try:
        index = int(index_raw)
    except (TypeError, ValueError):
        return None
    lines = block.content
    if not lines or index < 0 or index >= len(lines):
        return None
    return lines[index]


def _block_after_header(
    field_def: dict[str, Any], blocks: list[_Block]
) -> _Block | None:
    header_pattern = field_def.get("header_pattern")
    if not header_pattern:
        return None
    for b in blocks:
        if b.header and header_pattern in b.header:
            for follower in blocks[b.index + 1 :]:
                if follower.content or follower.header:
                    return follower
    return None


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------


def _cz_date_iso(value: str) -> str:
    """Convert ``9.5.2026`` (Czech short date) to ISO ``2026-05-09``."""
    parts = value.strip().rstrip(".").split(".")
    if len(parts) != 3:
        raise ValueError(f"Not a Czech date: {value!r}")
    day, month, year = (int(p) for p in parts)
    return f"{year:04d}-{month:02d}-{day:02d}"


def _normalize_amount(value: str) -> str:
    """Strip currency, spaces, NBSP, convert ``,`` decimal to ``.``."""
    stripped = value.replace(" ", " ").strip()
    # Drop trailing currency tokens (Kč, CZK, EUR, …) and any whitespace
    # leading up to them.
    stripped = re.sub(r"\s*(?:Kč|CZK|EUR|USD|€|\$)\s*$", "", stripped)
    # Remove thousand separators (spaces / NBSP).
    stripped = stripped.replace(" ", "")
    # Czech decimal comma → dot.
    stripped = stripped.replace(",", ".")
    return stripped


def _strip(value: str) -> str:
    return value.strip()


_CURRENCY_MAP: dict[str, str] = {
    "Kč": "CZK",
    "kč": "CZK",
    "CZK": "CZK",
    "€": "EUR",
    "EUR": "EUR",
    "$": "USD",
    "USD": "USD",
    "£": "GBP",
    "GBP": "GBP",
}


def _currency_code(value: str) -> str:
    """Map a currency symbol or label to its ISO 4217 code."""
    token = value.strip()
    return _CURRENCY_MAP.get(token, token)


_TRANSFORMS: dict[str, Callable[[str], str]] = {
    "cz_date_iso": _cz_date_iso,
    "normalize_amount": _normalize_amount,
    "strip": _strip,
    "currency_code": _currency_code,
}


# ---------------------------------------------------------------------------
# Block wrapping
# ---------------------------------------------------------------------------


def _wrap_blocks(vim_doc: VimDoc) -> list[_Block]:
    out: list[_Block] = []
    for idx, raw in enumerate(get_structural_blocks(vim_doc)):
        out.append(
            _Block(
                id=str(raw.get("id") or f"block_{idx + 1}"),
                header=str(raw.get("header") or ""),
                content=[str(line) for line in (raw.get("content") or [])],
                index=idx,
            )
        )
    return out
