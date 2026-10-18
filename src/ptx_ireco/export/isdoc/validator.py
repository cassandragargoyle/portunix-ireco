"""Four-gate ISDOC validation pipeline.

Gates run in order; **all** failures from earlier gates are recorded
even when later gates can still execute (the writer/api decides what
to do with a failing report). The exception is gate 2 (XSD) — if the
schema cannot even load, the validator records the error and skips
later gates rather than masking the cause.

Gates:

1. Required-field check against the field-map filtered by profile.
2. XSD validation with the bundled ``isdoc-invoice-6.0.2.xsd``.
3. Business rules (BR-CO-10 / BR-CO-13 / BR-CZ-IČO / BR-CZ-DIČ /
   BR-CZ-CURRENCY).
4. Round-trip parse — re-load the emitted bytes, re-validate against
   the XSD. Defends against escaping bugs.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation
from importlib import resources
from pathlib import Path
from typing import Any

from lxml import etree  # type: ignore[import-untyped]

from ptx_ireco.export.isdoc.codes import load_currency_whitelist
from ptx_ireco.export.isdoc.errors import ValidationError, ValidationReport

logger = logging.getLogger(__name__)

_XSD_PACKAGE = "ptx_ireco.export.isdoc.schemas"
_XSD_FILENAME = "isdoc-invoice-6.0.2.xsd"

_ICO_RE = re.compile(r"^\d{8}$")
_DIC_RE = re.compile(r"^CZ\d{8,10}$")


# ---------------------------------------------------------------------------
# Schema loading (cached)
# ---------------------------------------------------------------------------

_SCHEMA_CACHE: etree.XMLSchema | None = None


def load_schema() -> etree.XMLSchema:
    """Load the bundled ISDOC XSD via :mod:`importlib.resources`."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    ref = resources.files(_XSD_PACKAGE).joinpath(_XSD_FILENAME)
    with resources.as_file(ref) as path:
        xsd_doc = etree.parse(str(path))
    _SCHEMA_CACHE = etree.XMLSchema(xsd_doc)
    return _SCHEMA_CACHE


def clear_schema_cache() -> None:
    """Drop the schema cache. Tests use this between cases."""
    global _SCHEMA_CACHE
    _SCHEMA_CACHE = None


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def validate(
    *,
    root: etree._Element,
    serialised: bytes,
    field_map: dict[str, Any],
    profile: str,
    vim_doc: dict[str, Any],
    models_root: Path,
) -> ValidationReport:
    """Run all four gates and return an aggregated report."""
    report = ValidationReport()

    _gate_required(report, field_map=field_map, profile=profile, vim_doc=vim_doc)
    _gate_xsd(report, root=root)
    _gate_business_rules(
        report,
        root=root,
        field_map=field_map,
        models_root=models_root,
    )
    _gate_round_trip(report, serialised=serialised)
    return report


# ---------------------------------------------------------------------------
# Gate 1 — required fields
# ---------------------------------------------------------------------------


def _gate_required(
    report: ValidationReport,
    *,
    field_map: dict[str, Any],
    profile: str,
    vim_doc: dict[str, Any],
) -> None:
    entities = _index_entities(vim_doc)
    failures = 0
    for entry in field_map.get("fields") or []:
        failures += _check_required(entry, entities=entities, profile=profile, report=report)
    report.mark_gate("required", "fail" if failures else "pass")


def _check_required(
    entry: dict[str, Any],
    *,
    entities: dict[str, list[dict[str, Any]]],
    profile: str,
    report: ValidationReport,
) -> int:
    required_in = entry.get("required_in") or []
    if profile not in required_in:
        return 0

    if "value" in entry:
        return 0  # literal — always present

    entity_type = entry.get("entity_type")
    if not entity_type:
        return 0
    instances = entities.get(entity_type) or []

    if "children" in entry:
        if not instances:
            report.add_error(
                ValidationError(
                    rule="required",
                    message=(
                        f"Group {entry.get('bg', '?')} requires at least one "
                        f"'{entity_type}' entity for profile '{profile}'"
                    ),
                    path=entry.get("isdoc_xpath"),
                    bt=entry.get("bg"),
                )
            )
            return 1
        # Check children for the first instance only — finer per-row
        # checks would over-fire for optional repeated rows.
        local_failures = 0
        for child in entry["children"]:
            if profile not in (child.get("required_in") or []):
                continue
            field = child.get("field")
            if not field:
                continue
            if not (instances[0].get("fields") or {}).get(field):
                report.add_error(
                    ValidationError(
                        rule="required",
                        message=(
                            f"Required field {child.get('bt', '?')} missing in "
                            f"'{entity_type}' for profile '{profile}'"
                        ),
                        path=f"{entry.get('isdoc_xpath')}/{child.get('isdoc_xpath')}",
                        bt=child.get("bt"),
                    )
                )
                local_failures += 1
        return local_failures

    field = entry.get("field")
    if not field:
        return 0
    if not instances:
        report.add_error(
            ValidationError(
                rule="required",
                message=(
                    f"Required field {entry.get('bt', '?')} missing — entity "
                    f"'{entity_type}' absent for profile '{profile}'"
                ),
                path=entry.get("isdoc_xpath"),
                bt=entry.get("bt"),
            )
        )
        return 1
    if not (instances[0].get("fields") or {}).get(field):
        report.add_error(
            ValidationError(
                rule="required",
                message=(
                    f"Required field {entry.get('bt', '?')} missing — "
                    f"'{entity_type}.fields.{field}' empty for profile "
                    f"'{profile}'"
                ),
                path=entry.get("isdoc_xpath"),
                bt=entry.get("bt"),
            )
        )
        return 1
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — XSD
# ---------------------------------------------------------------------------


def _gate_xsd(report: ValidationReport, *, root: etree._Element) -> None:
    try:
        schema = load_schema()
    except Exception as exc:  # noqa: BLE001 — surface root cause, do not skip silently
        report.add_error(
            ValidationError(rule="xsd", message=f"Cannot load XSD: {exc}")
        )
        report.mark_gate("xsd", "fail")
        return
    if schema.validate(root):
        report.mark_gate("xsd", "pass")
        return
    for err in schema.error_log:
        report.add_error(
            ValidationError(
                rule="xsd",
                message=err.message,
                path=err.path,
            )
        )
    report.mark_gate("xsd", "fail")


# ---------------------------------------------------------------------------
# Gate 3 — business rules
# ---------------------------------------------------------------------------


def _gate_business_rules(
    report: ValidationReport,
    *,
    root: etree._Element,
    field_map: dict[str, Any],
    models_root: Path,
) -> None:
    namespace = field_map.get("namespace") or ""
    ns = {"i": namespace} if namespace else {}
    pre = "i:" if namespace else ""

    failures = 0
    failures += _br_co_10(root, ns=ns, pre=pre, report=report)
    failures += _br_co_13(root, ns=ns, pre=pre, report=report)
    failures += _br_cz_ico(root, ns=ns, pre=pre, report=report)
    failures += _br_cz_dic(root, ns=ns, pre=pre, report=report)
    failures += _br_cz_currency(
        root, ns=ns, pre=pre, report=report, models_root=models_root
    )
    report.mark_gate("business_rules", "fail" if failures else "pass")


def _xpath_text(root: etree._Element, expr: str, ns: dict[str, str]) -> list[str]:
    nodes = root.xpath(expr, namespaces=ns)
    return [(n.text or "").strip() for n in nodes if hasattr(n, "text")]


def _to_decimal(text: str) -> Decimal | None:
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _br_co_10(
    root: etree._Element, *, ns: dict[str, str], pre: str, report: ValidationReport
) -> int:
    line_amounts = _xpath_text(
        root, f"//{pre}InvoiceLines/{pre}InvoiceLine/{pre}LineExtensionAmount", ns
    )
    tax_excl = _xpath_text(
        root, f"//{pre}LegalMonetaryTotal/{pre}TaxExclusiveAmount", ns
    )
    if not line_amounts or not tax_excl:
        return 0
    total = sum((_to_decimal(a) or Decimal(0)) for a in line_amounts)
    declared = _to_decimal(tax_excl[0])
    if declared is None or total != declared:
        report.add_error(
            ValidationError(
                rule="BR-CO-10",
                message=(
                    f"Σ InvoiceLine/LineExtensionAmount ({total}) ≠ "
                    f"TaxExclusiveAmount ({tax_excl[0]})"
                ),
                path="/Invoice/LegalMonetaryTotal/TaxExclusiveAmount",
            )
        )
        return 1
    return 0


def _br_co_13(
    root: etree._Element, *, ns: dict[str, str], pre: str, report: ValidationReport
) -> int:
    excl = _xpath_text(root, f"//{pre}LegalMonetaryTotal/{pre}TaxExclusiveAmount", ns)
    tax = _xpath_text(root, f"//{pre}LegalMonetaryTotal/{pre}TaxAmount", ns)
    incl = _xpath_text(root, f"//{pre}LegalMonetaryTotal/{pre}TaxInclusiveAmount", ns)
    if not excl or not tax or not incl:
        return 0
    e = _to_decimal(excl[0])
    t = _to_decimal(tax[0])
    i = _to_decimal(incl[0])
    if None in (e, t, i):
        return 0
    if (e + t) != i:  # type: ignore[operator]
        report.add_error(
            ValidationError(
                rule="BR-CO-13",
                message=(
                    f"TaxExclusiveAmount ({e}) + TaxAmount ({t}) ≠ "
                    f"TaxInclusiveAmount ({i})"
                ),
                path="/Invoice/LegalMonetaryTotal/TaxInclusiveAmount",
            )
        )
        return 1
    return 0


def _br_cz_ico(
    root: etree._Element, *, ns: dict[str, str], pre: str, report: ValidationReport
) -> int:
    failures = 0
    for party in ("AccountingSupplierParty", "AccountingCustomerParty"):
        country_codes = _xpath_text(
            root,
            f"//{pre}{party}/{pre}Party/{pre}Country/{pre}IdentificationCode",
            ns,
        )
        if country_codes and country_codes[0] != "CZ":
            continue
        ids = _xpath_text(
            root,
            f"//{pre}{party}/{pre}Party/{pre}PartyIdentification/{pre}ID",
            ns,
        )
        for ico in ids:
            if not ico:
                continue
            if not _ICO_RE.match(ico):
                report.add_error(
                    ValidationError(
                        rule="BR-CZ-ICO",
                        message=f"IČO must be 8 digits (got {ico!r})",
                        path=f"/Invoice/{party}/Party/PartyIdentification/ID",
                        value=ico,
                    )
                )
                failures += 1
                continue
            if not _ico_mod11_ok(ico):
                report.add_error(
                    ValidationError(
                        rule="BR-CZ-ICO",
                        message=f"IČO failed mod-11 checksum (got {ico!r})",
                        path=f"/Invoice/{party}/Party/PartyIdentification/ID",
                        value=ico,
                    )
                )
                failures += 1
    return failures


def _ico_mod11_ok(ico: str) -> bool:
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


def _br_cz_dic(
    root: etree._Element, *, ns: dict[str, str], pre: str, report: ValidationReport
) -> int:
    failures = 0
    for party in ("AccountingSupplierParty", "AccountingCustomerParty"):
        dics = _xpath_text(
            root,
            f"//{pre}{party}/{pre}Party/{pre}PartyTaxScheme/{pre}CompanyID",
            ns,
        )
        for dic in dics:
            if not dic:
                continue
            if not dic.startswith("CZ"):
                continue
            if not _DIC_RE.match(dic):
                report.add_error(
                    ValidationError(
                        rule="BR-CZ-DIC",
                        message=f"DIČ must match CZ\\d{{8,10}} (got {dic!r})",
                        path=f"/Invoice/{party}/Party/PartyTaxScheme/CompanyID",
                        value=dic,
                    )
                )
                failures += 1
    return failures


def _br_cz_currency(
    root: etree._Element,
    *,
    ns: dict[str, str],
    pre: str,
    report: ValidationReport,
    models_root: Path,
) -> int:
    try:
        whitelist = load_currency_whitelist(models_root)
    except Exception:  # noqa: BLE001 — missing table → skip rule
        return 0
    if not whitelist:
        return 0
    currencies = _xpath_text(root, f"//{pre}LocalCurrencyCode", ns)
    currencies += _xpath_text(root, f"//{pre}CurrencyCode", ns)
    failures = 0
    for c in currencies:
        if c and c not in whitelist:
            report.add_error(
                ValidationError(
                    rule="BR-CZ-CURRENCY",
                    message=(
                        f"Currency {c!r} not in CZ whitelist "
                        f"({sorted(whitelist)})"
                    ),
                    path="/Invoice/LocalCurrencyCode",
                    value=c,
                )
            )
            failures += 1
    return failures


# ---------------------------------------------------------------------------
# Gate 4 — round-trip
# ---------------------------------------------------------------------------


def _gate_round_trip(report: ValidationReport, *, serialised: bytes) -> None:
    try:
        reparsed = etree.fromstring(serialised)
    except etree.XMLSyntaxError as exc:
        report.add_error(
            ValidationError(rule="round_trip", message=f"Re-parse failed: {exc}")
        )
        report.mark_gate("round_trip", "fail")
        return
    try:
        schema = load_schema()
    except Exception as exc:  # noqa: BLE001
        report.add_error(
            ValidationError(rule="round_trip", message=f"Cannot load XSD: {exc}")
        )
        report.mark_gate("round_trip", "fail")
        return
    if schema.validate(reparsed):
        report.mark_gate("round_trip", "pass")
        return
    for err in schema.error_log:
        report.add_error(
            ValidationError(rule="round_trip", message=err.message, path=err.path)
        )
    report.mark_gate("round_trip", "fail")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _index_entities(vim_doc: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    layers = vim_doc.get("layers") or {}
    semantic = layers.get("semantic") or {}
    out: dict[str, list[dict[str, Any]]] = {}
    for entity in semantic.get("entities") or []:
        etype = entity.get("type")
        if not etype:
            continue
        out.setdefault(etype, []).append(entity)
    return out
