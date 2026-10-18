"""Template fingerprint matching (per ADR-0002).

Each template under ``models/invoice/templates/<uuid>.json`` declares a
``country``, a ``match_threshold`` (0.0–1.0), and a list of
``fingerprint_rules``. Each rule contributes a ``weight`` to the total
score when its ``pattern`` matches the document's structural-block text
(or a barcode payload for ``barcode_anchor`` rules).

Supported rule types:

- ``text_anchor`` — substring or regex (``regex`` field) match against
  any structural block's joined content.
- ``tax_id`` — substring match (whole-document scan).
- ``vat_id`` — substring match (whole-document scan).
- ``barcode_anchor`` — substring match against any barcode's
  ``raw_content``.

A template matches when the *normalised* score (sum of matched weights /
sum of all weights) is greater than or equal to ``match_threshold``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ptx_ireco.vim.io import VimDoc, get_structural_barcodes, get_structural_blocks

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TemplateMatch:
    """Result of matching one template against a VIM document.

    Attributes:
        template_id: The template's ``id`` field (or filename stem).
        country: ``country`` declared by the template (ISO-3166 alpha-3).
        score: Normalised score in ``[0.0, 1.0]``.
        threshold: ``match_threshold`` declared by the template.
        flexylayout_id: Optional ``flexylayout_id`` field that points the
            extractor at a specific flexylayout file.
        path: Path to the template JSON file.
    """

    template_id: str
    country: str
    score: float
    threshold: float
    flexylayout_id: str | None
    path: Path

    @property
    def matched(self) -> bool:
        """Whether the score clears the template's threshold."""
        return self.score >= self.threshold


def load_templates(templates_dir: str | Path) -> list[dict[str, Any]]:
    """Load every ``*.json`` under ``templates_dir`` (non-recursive)."""
    base = Path(templates_dir)
    if not base.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(base.glob("*.json")):
        try:
            with p.open(encoding="utf-8") as f:
                data = json.load(f)
            data["__path__"] = str(p)
            out.append(data)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping template %s: %s", p, exc)
    return out


def match_templates(
    vim_doc: VimDoc, templates_dir: str | Path
) -> TemplateMatch | None:
    """Return the highest-scoring matched template, or ``None`` if none match.

    Ties are broken by score (highest first), then by template id (stable).
    """
    templates = load_templates(templates_dir)
    if not templates:
        return None

    haystack = _document_text(vim_doc)
    barcode_payloads = _barcode_payloads(vim_doc)

    candidates: list[TemplateMatch] = []
    for tpl in templates:
        score = _score_template(tpl, haystack, barcode_payloads)
        threshold = float(tpl.get("match_threshold", 0.5))
        candidates.append(
            TemplateMatch(
                template_id=tpl.get("id") or Path(tpl["__path__"]).stem,
                country=tpl.get("country", "UNK"),
                score=score,
                threshold=threshold,
                flexylayout_id=tpl.get("flexylayout_id"),
                path=Path(tpl["__path__"]),
            )
        )

    candidates.sort(key=lambda c: (-c.score, c.template_id))
    best = candidates[0]
    return best if best.matched else None


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _score_template(
    tpl: dict[str, Any], haystack: str, barcode_payloads: list[str]
) -> float:
    rules = tpl.get("fingerprint_rules") or []
    if not rules:
        return 0.0

    total_weight = 0.0
    matched_weight = 0.0
    for rule in rules:
        weight = float(rule.get("weight", 1.0))
        total_weight += weight
        if _rule_matches(rule, haystack, barcode_payloads):
            matched_weight += weight

    if total_weight == 0.0:
        return 0.0
    return matched_weight / total_weight


def _rule_matches(
    rule: dict[str, Any], haystack: str, barcode_payloads: Iterable[str]
) -> bool:
    rule_type = rule.get("type", "text_anchor")
    pattern = rule.get("pattern")
    if not pattern:
        return False

    is_regex = bool(rule.get("regex", False))

    if rule_type == "barcode_anchor":
        for payload in barcode_payloads:
            if _haystack_match(pattern, payload, is_regex):
                return True
        return False

    # text_anchor / tax_id / vat_id all scan the joined document text.
    return _haystack_match(pattern, haystack, is_regex)


def _haystack_match(pattern: str, haystack: str, is_regex: bool) -> bool:
    if is_regex:
        try:
            return re.search(pattern, haystack) is not None
        except re.error as exc:
            logger.warning("Bad regex %r: %s", pattern, exc)
            return False
    return pattern in haystack


def _document_text(vim_doc: VimDoc) -> str:
    """Join header + content lines from every structural block, plus headers.

    The result is a single newline-delimited string used as the haystack
    for ``text_anchor`` / ``tax_id`` / ``vat_id`` rule matching.
    """
    parts: list[str] = []
    for block in get_structural_blocks(vim_doc):
        header = block.get("header")
        if header:
            parts.append(str(header))
        for line in block.get("content") or []:
            parts.append(str(line))
    return "\n".join(parts)


def _barcode_payloads(vim_doc: VimDoc) -> list[str]:
    """Pull ``raw_content`` from every physical barcode."""
    layers = vim_doc.get("layers") or {}
    physical = layers.get("physical") or {}
    barcodes = physical.get("barcodes") or []
    payloads: list[str] = []
    for bc in barcodes:
        raw = bc.get("raw_content")
        if isinstance(raw, str):
            payloads.append(raw)
    # Also include structural barcode IDs in case templates anchor on them.
    for sbc in get_structural_barcodes(vim_doc):
        ct = sbc.get("content_type")
        if isinstance(ct, str):
            payloads.append(ct)
    return payloads
