"""Country profile resolution by ``issue_date`` (per ADR-0001).

Profile files live under ``models/invoice/profiles/<country>/`` (lowercase
ISO-3166 alpha-3 directory, e.g. ``cze``). Each profile declares
``valid_from`` and an optional ``valid_to`` (``null`` means "still in
effect"). The resolver picks the file where
``valid_from <= issue_date < valid_to`` (or no ``valid_to``).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedProfile:
    """Profile selected for a given country + ``issue_date``."""

    country: str
    valid_from: date
    valid_to: date | None
    path: Path
    data: dict[str, Any]


class ProfileNotFoundError(LookupError):
    """No profile valid for the requested country + date combination."""


def resolve_profile(
    country: str,
    issue_date: date | str,
    profiles_root: str | Path,
) -> ResolvedProfile:
    """Pick the profile whose validity window contains ``issue_date``.

    Args:
        country: ISO-3166 alpha-3 code (case-insensitive); ``"CZE"``.
        issue_date: ISO-8601 date or :class:`datetime.date`.
        profiles_root: Path to ``models/invoice/profiles/``.

    Returns:
        :class:`ResolvedProfile` for the chosen file.

    Raises:
        ProfileNotFoundError: country directory missing or no file applies.
    """
    iso = country.lower()
    target_date = _coerce_date(issue_date)
    base = Path(profiles_root) / iso
    if not base.is_dir():
        raise ProfileNotFoundError(
            f"No profiles directory for country {country!r} at {base}"
        )

    candidates: list[ResolvedProfile] = []
    for path in sorted(base.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping profile %s: %s", path, exc)
            continue

        valid_from_raw = data.get("valid_from")
        if not valid_from_raw:
            logger.warning("Profile %s missing valid_from", path)
            continue

        try:
            valid_from = _coerce_date(valid_from_raw)
        except ValueError:
            logger.warning("Profile %s has bad valid_from=%r", path, valid_from_raw)
            continue

        valid_to_raw = data.get("valid_to")
        valid_to = _coerce_date(valid_to_raw) if valid_to_raw else None

        if target_date < valid_from:
            continue
        if valid_to is not None and target_date >= valid_to:
            continue

        candidates.append(
            ResolvedProfile(
                country=country.upper(),
                valid_from=valid_from,
                valid_to=valid_to,
                path=path,
                data=data,
            )
        )

    if not candidates:
        raise ProfileNotFoundError(
            f"No profile for country={country!r} valid on {target_date.isoformat()}"
        )

    # Highest valid_from wins (most recent profile that still applies).
    candidates.sort(key=lambda c: c.valid_from, reverse=True)
    return candidates[0]


def _coerce_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)
