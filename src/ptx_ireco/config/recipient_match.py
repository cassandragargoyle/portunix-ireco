"""Match a parsed buyer entity against the configured recipient list.

ADR-0004 prescribes the comparison order: ``dic`` first, then ``ico``,
then ``name`` (case-insensitive equality). Cross-document recipient
learning is explicitly out of scope for v1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RecipientMatch:
    """Result of matching a buyer against ``invoice.recipients``."""

    recipient_id: str
    matched_on: str  # one of: "dic", "ico", "name"


def match_recipient(
    buyer_fields: dict[str, str] | None,
    recipients: list[dict[str, Any]],
) -> RecipientMatch | None:
    """Return the configured recipient matching the parsed ``buyer_fields``.

    ``buyer_fields`` is the ``fields`` dict of the ``buyer`` semantic
    entity emitted by step 2; it typically contains ``vat_id``,
    ``tax_id``, and ``name``. Returns ``None`` when no recipient lines
    up — callers decide what to do (in known mode that is a flag-worthy
    signal; in multitenant we don't call this at all).
    """
    if not buyer_fields or not recipients:
        return None

    buyer_dic = (buyer_fields.get("vat_id") or "").strip().upper()
    buyer_ico = (buyer_fields.get("tax_id") or "").strip()
    buyer_name = (buyer_fields.get("name") or "").strip().casefold()

    if buyer_dic:
        for r in recipients:
            r_dic = (r.get("dic") or "").strip().upper()
            if r_dic and r_dic == buyer_dic:
                return RecipientMatch(recipient_id=r["id"], matched_on="dic")

    if buyer_ico:
        for r in recipients:
            if (r.get("ico") or "").strip() == buyer_ico:
                return RecipientMatch(recipient_id=r["id"], matched_on="ico")

    if buyer_name:
        for r in recipients:
            r_name = (r.get("name") or "").strip().casefold()
            if r_name and r_name == buyer_name:
                return RecipientMatch(recipient_id=r["id"], matched_on="name")

    return None
