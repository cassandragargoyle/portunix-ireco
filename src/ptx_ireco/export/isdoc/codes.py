"""Value transforms + CZ code-table lookups for ISDOC export.

Transforms are pure functions that normalise a raw semantic value
into the lexical form ISDOC requires (decimals with two places,
ISO-8601 dates, ISO 4217 currency codes, …). Code tables are loaded
from ``models/invoice/exports/isdoc/cze/*.json``; loaders cache the
parsed JSON per ``models_root`` so repeated exports do not re-parse.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from ptx_ireco.export.isdoc.errors import ExportError

# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------

_DECIMAL_CLEAN_RE = re.compile(r"[ \s]+")  # NBSP + regular whitespace
_CZ_DATE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_ICO_RE = re.compile(r"^\d{8}$")
_DIC_RE = re.compile(r"^CZ\d{8,10}$")
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")


def _normalise_amount_text(raw: str) -> str:
    """Strip thousands separators and normalise the decimal mark.

    Accepts inputs like ``"12 345,67"``, ``"12.345,67"`` (CZ),
    ``"12,345.67"`` (US), or already-clean ``"12345.67"``.
    """
    if raw is None:
        raise ExportError("decimal transform got None")
    text = _DECIMAL_CLEAN_RE.sub("", str(raw))
    if "," in text and "." in text:
        # Both separators present → assume the rightmost is the decimal mark.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    return text


def decimal_n(raw: Any, places: int) -> str:
    """Return ``raw`` normalised to ``places``-decimal lexical form.

    Raises:
        ExportError: ``raw`` is not parseable as a number.
    """
    text = _normalise_amount_text(raw)
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ExportError(f"Invalid decimal value: {raw!r}") from exc
    quant = Decimal(10) ** -places
    return str(value.quantize(quant))


def decimal2(raw: Any) -> str:
    return decimal_n(raw, 2)


def decimal3(raw: Any) -> str:
    return decimal_n(raw, 3)


def iso_date(raw: Any) -> str:
    """Normalise to ``YYYY-MM-DD``.

    Accepts CZ ``DD.MM.YYYY`` and ISO ``YYYY-MM-DD`` inputs.
    """
    if raw is None:
        raise ExportError("date transform got None")
    if isinstance(raw, (date, datetime)):
        return raw.date().isoformat() if isinstance(raw, datetime) else raw.isoformat()
    text = str(raw).strip()
    m = _CZ_DATE_RE.match(text)
    if m:
        d, mo, y = (int(g) for g in m.groups())
        try:
            return date(y, mo, d).isoformat()
        except ValueError as exc:
            raise ExportError(f"Invalid CZ date: {raw!r}") from exc
    m = _ISO_DATE_RE.match(text)
    if m:
        y, mo, d = (int(g) for g in m.groups())
        try:
            return date(y, mo, d).isoformat()
        except ValueError as exc:
            raise ExportError(f"Invalid ISO date: {raw!r}") from exc
    raise ExportError(f"Unrecognised date format: {raw!r}")


def iso_currency(raw: Any) -> str:
    """Normalise common CZ currency labels to ISO 4217 codes.

    Maps ``Kč`` → ``CZK`` and the Euro symbol → ``EUR``; otherwise
    upper-cases the input. The whitelist check happens later in
    business-rule validation, not here.
    """
    if raw is None:
        raise ExportError("currency transform got None")
    text = str(raw).strip().upper()
    if text in ("KČ", "KC", "CZK"):
        return "CZK"
    if text in ("€", "EUR"):
        return "EUR"
    if len(text) != 3 or not text.isalpha():
        raise ExportError(f"Unrecognised currency: {raw!r}")
    return text


def country_alpha2(raw: Any) -> str:
    """Return the ISO 3166-1 alpha-2 code for ``raw``.

    Recognises Czech / Slovak country names commonly seen in CZ
    invoices; passes already-correct alpha-2 codes through.
    """
    if raw is None:
        raise ExportError("country transform got None")
    text = str(raw).strip()
    upper = text.upper()
    if _COUNTRY_RE.match(upper):
        return upper
    name_map = {
        "ČESKÁ REPUBLIKA": "CZ",
        "CESKA REPUBLIKA": "CZ",
        "CZECH REPUBLIC": "CZ",
        "CZECHIA": "CZ",
        "SLOVENSKÁ REPUBLIKA": "SK",
        "SLOVENSKA REPUBLIKA": "SK",
        "SLOVAKIA": "SK",
        "DEUTSCHLAND": "DE",
        "GERMANY": "DE",
        "ÖSTERREICH": "AT",
        "OSTERREICH": "AT",
        "AUSTRIA": "AT",
        "POLSKA": "PL",
        "POLAND": "PL",
    }
    code = name_map.get(upper)
    if code is None:
        raise ExportError(f"Unrecognised country: {raw!r}")
    return code


def czech_ico(raw: Any) -> str:
    """Validate and return a normalised 8-digit Czech IČO.

    Raises:
        ExportError: ``raw`` is not 8 digits or fails the mod-11
            checksum.
    """
    if raw is None:
        raise ExportError("IČO transform got None")
    text = re.sub(r"\s+", "", str(raw))
    if not _ICO_RE.match(text):
        raise ExportError(f"IČO must be 8 digits: {raw!r}")
    if not _ico_mod11_ok(text):
        raise ExportError(f"IČO failed mod-11 check: {raw!r}")
    return text


def _ico_mod11_ok(ico: str) -> bool:
    """Return True iff ``ico`` (8 digits) passes the standard mod-11 check.

    Algorithm per the Czech Statistical Office: weights 8,7,6,5,4,3,2
    applied to the first seven digits. Remainder ``mod 11`` mapped:
    ``0 → 1``, ``10 → 0``, otherwise ``11 - r``. Result must equal the
    8th digit.
    """
    weights = (8, 7, 6, 5, 4, 3, 2)
    digits = [int(c) for c in ico]
    weighted = sum(d * w for d, w in zip(digits[:7], weights))
    remainder = weighted % 11
    if remainder == 0:
        check = 1
    elif remainder == 10:
        check = 0
    else:
        check = 11 - remainder
    return check == digits[7]


def czech_dic(raw: Any) -> str:
    """Validate and return a Czech DIČ (``CZ`` + 8–10 digits)."""
    if raw is None:
        raise ExportError("DIČ transform got None")
    text = re.sub(r"\s+", "", str(raw)).upper()
    if not _DIC_RE.match(text):
        raise ExportError(f"DIČ must match CZ\\d{{8,10}}: {raw!r}")
    return text


_TRANSFORMS: dict[str, Callable[[Any], str]] = {
    "decimal2": decimal2,
    "decimal3": decimal3,
    "iso_date": iso_date,
    "iso_currency": iso_currency,
    "country_alpha2": country_alpha2,
    "czech_ico": czech_ico,
    "czech_dic": czech_dic,
}


def get_transform(name: str) -> Callable[[Any], str]:
    """Return the transform function registered under ``name``.

    Raises:
        ExportError: ``name`` is not a known transform.
    """
    fn = _TRANSFORMS.get(name)
    if fn is None:
        raise ExportError(f"Unknown transform: {name!r}")
    return fn


def list_transforms() -> list[str]:
    return sorted(_TRANSFORMS)


# ---------------------------------------------------------------------------
# CZ code-table loaders
# ---------------------------------------------------------------------------


def _models_isdoc_cze(models_root: Path) -> Path:
    return Path(models_root) / "models" / "invoice" / "exports" / "isdoc" / "cze"


@lru_cache(maxsize=8)
def _load_json(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise ExportError(f"ISDOC code table not found: {p}")
    try:
        with p.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ExportError(f"Invalid JSON in {p}: {exc}") from exc


def load_tax_categories(models_root: Path) -> dict[str, str]:
    """EN 16931 BT-118 category code → ISDOC ``ClassifiedTaxCategory``."""
    table = _load_json(str(_models_isdoc_cze(models_root) / "tax_categories.json"))
    return dict(table.get("mapping") or {})


def load_unit_codes(models_root: Path) -> dict[str, str]:
    """UN/ECE Rec.20 → ISDOC ``UnitCode``."""
    table = _load_json(str(_models_isdoc_cze(models_root) / "unit_codes.json"))
    return dict(table.get("mapping") or {})


def load_currency_whitelist(models_root: Path) -> set[str]:
    """ISO 4217 currency codes accepted by CZ ERPs."""
    table = _load_json(str(_models_isdoc_cze(models_root) / "currency_codes.json"))
    return set(table.get("allowed") or [])


def load_field_map(models_root: Path) -> dict[str, Any]:
    """Return the field-map JSON document.

    Shape (validated by the mapper, not here): top-level
    ``{version, isdoc_version, namespace, fields: [...]}``.
    """
    return _load_json(str(_models_isdoc_cze(models_root) / "field_map.json"))


def clear_caches() -> None:
    """Drop the LRU cache. Tests use this between cases."""
    _load_json.cache_clear()
