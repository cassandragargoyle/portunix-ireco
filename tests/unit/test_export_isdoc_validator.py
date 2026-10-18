"""Unit tests for ptx_ireco.export.isdoc.validator (gates 1, 3, 4).

Gate 2 (XSD) is exercised indirectly via the e2e snapshot test —
it requires the bundled XSD which is loaded once per process.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lxml import etree  # type: ignore[import-untyped]

from ptx_ireco.export.isdoc.errors import ValidationReport
from ptx_ireco.export.isdoc.validator import (
    _br_co_10,
    _br_co_13,
    _br_cz_currency,
    _br_cz_dic,
    _br_cz_ico,
    _gate_required,
    _gate_round_trip,
    _ico_mod11_ok,
)

NS = "http://isdoc.cz/namespace/2013"
NS_PRE = "{" + NS + "}"


def _build_invoice(children_xml: str) -> etree._Element:
    xml = (
        f'<Invoice xmlns="{NS}" version="6.0.2">'
        f"{children_xml}"
        f"</Invoice>"
    )
    return etree.fromstring(xml.encode("utf-8"))


# ---------------------------------------------------------------------------
# Gate 1 — required-field check
# ---------------------------------------------------------------------------


def test_gate_required_pass_when_all_present():
    field_map = {
        "fields": [
            {
                "bt": "BT-1", "entity_type": "invoice_header", "field": "invoice_number",
                "isdoc_xpath": "/Invoice/ID", "required_in": ["minimal"],
            }
        ]
    }
    vim = {"layers": {"semantic": {"entities": [
        {"type": "invoice_header", "fields": {"invoice_number": "FA_001"}}
    ]}}}
    report = ValidationReport()
    _gate_required(report, field_map=field_map, profile="minimal", vim_doc=vim)
    assert report.gates["required"] == "pass"
    assert report.errors == []


def test_gate_required_fail_when_entity_missing():
    field_map = {
        "fields": [
            {
                "bt": "BT-1", "entity_type": "invoice_header", "field": "invoice_number",
                "isdoc_xpath": "/Invoice/ID", "required_in": ["minimal"],
            }
        ]
    }
    vim = {"layers": {"semantic": {"entities": []}}}
    report = ValidationReport()
    _gate_required(report, field_map=field_map, profile="minimal", vim_doc=vim)
    assert report.gates["required"] == "fail"
    assert len(report.errors) == 1
    assert report.errors[0].rule == "required"
    assert report.errors[0].bt == "BT-1"


def test_gate_required_aggregates_all_failures():
    field_map = {
        "fields": [
            {
                "bt": "BT-1", "entity_type": "invoice_header", "field": "invoice_number",
                "isdoc_xpath": "/Invoice/ID", "required_in": ["minimal"],
            },
            {
                "bt": "BT-2", "entity_type": "invoice_header", "field": "issue_date",
                "isdoc_xpath": "/Invoice/IssueDate", "required_in": ["minimal"],
            },
        ]
    }
    vim = {"layers": {"semantic": {"entities": [
        {"type": "invoice_header", "fields": {}}
    ]}}}
    report = ValidationReport()
    _gate_required(report, field_map=field_map, profile="minimal", vim_doc=vim)
    assert len(report.errors) == 2  # both, not just first


# ---------------------------------------------------------------------------
# Gate 3 — business rules
# ---------------------------------------------------------------------------


def test_br_co_10_pass():
    inv = _build_invoice(
        "<InvoiceLines>"
        "<InvoiceLine><LineExtensionAmount>500.00</LineExtensionAmount></InvoiceLine>"
        "<InvoiceLine><LineExtensionAmount>500.00</LineExtensionAmount></InvoiceLine>"
        "</InvoiceLines>"
        "<LegalMonetaryTotal><TaxExclusiveAmount>1000.00</TaxExclusiveAmount></LegalMonetaryTotal>"
    )
    report = ValidationReport()
    failures = _br_co_10(inv, ns={"i": NS}, pre="i:", report=report)
    assert failures == 0
    assert report.errors == []


def test_br_co_10_fail():
    inv = _build_invoice(
        "<InvoiceLines>"
        "<InvoiceLine><LineExtensionAmount>500.00</LineExtensionAmount></InvoiceLine>"
        "</InvoiceLines>"
        "<LegalMonetaryTotal><TaxExclusiveAmount>900.00</TaxExclusiveAmount></LegalMonetaryTotal>"
    )
    report = ValidationReport()
    failures = _br_co_10(inv, ns={"i": NS}, pre="i:", report=report)
    assert failures == 1
    assert report.errors[0].rule == "BR-CO-10"


def test_br_co_13_pass():
    inv = _build_invoice(
        "<LegalMonetaryTotal>"
        "<TaxExclusiveAmount>1000.00</TaxExclusiveAmount>"
        "<TaxAmount>210.00</TaxAmount>"
        "<TaxInclusiveAmount>1210.00</TaxInclusiveAmount>"
        "</LegalMonetaryTotal>"
    )
    report = ValidationReport()
    assert _br_co_13(inv, ns={"i": NS}, pre="i:", report=report) == 0


def test_br_co_13_fail():
    inv = _build_invoice(
        "<LegalMonetaryTotal>"
        "<TaxExclusiveAmount>1000.00</TaxExclusiveAmount>"
        "<TaxAmount>210.00</TaxAmount>"
        "<TaxInclusiveAmount>1500.00</TaxInclusiveAmount>"  # wrong
        "</LegalMonetaryTotal>"
    )
    report = ValidationReport()
    assert _br_co_13(inv, ns={"i": NS}, pre="i:", report=report) == 1


def test_br_cz_ico_pass_for_valid_8digit():
    # 27074358 is a real, mod-11-valid CSU IČO.
    inv = _build_invoice(
        "<AccountingSupplierParty><Party>"
        "<PartyIdentification><ID>27074358</ID></PartyIdentification>"
        "<Country><IdentificationCode>CZ</IdentificationCode></Country>"
        "</Party></AccountingSupplierParty>"
    )
    report = ValidationReport()
    assert _br_cz_ico(inv, ns={"i": NS}, pre="i:", report=report) == 0


def test_br_cz_ico_fail_mod11():
    inv = _build_invoice(
        "<AccountingSupplierParty><Party>"
        "<PartyIdentification><ID>12345678</ID></PartyIdentification>"
        "<Country><IdentificationCode>CZ</IdentificationCode></Country>"
        "</Party></AccountingSupplierParty>"
    )
    report = ValidationReport()
    assert _br_cz_ico(inv, ns={"i": NS}, pre="i:", report=report) == 1
    assert report.errors[0].rule == "BR-CZ-ICO"


def test_br_cz_ico_skip_for_non_cz():
    inv = _build_invoice(
        "<AccountingSupplierParty><Party>"
        "<PartyIdentification><ID>BAD</ID></PartyIdentification>"
        "<Country><IdentificationCode>SK</IdentificationCode></Country>"
        "</Party></AccountingSupplierParty>"
    )
    report = ValidationReport()
    assert _br_cz_ico(inv, ns={"i": NS}, pre="i:", report=report) == 0


def test_br_cz_dic_pass():
    inv = _build_invoice(
        "<AccountingSupplierParty><Party>"
        "<PartyTaxScheme><CompanyID>CZ27074358</CompanyID></PartyTaxScheme>"
        "</Party></AccountingSupplierParty>"
    )
    report = ValidationReport()
    assert _br_cz_dic(inv, ns={"i": NS}, pre="i:", report=report) == 0


def test_br_cz_dic_fail_format():
    inv = _build_invoice(
        "<AccountingSupplierParty><Party>"
        "<PartyTaxScheme><CompanyID>CZ123</CompanyID></PartyTaxScheme>"
        "</Party></AccountingSupplierParty>"
    )
    report = ValidationReport()
    assert _br_cz_dic(inv, ns={"i": NS}, pre="i:", report=report) == 1


def test_br_cz_currency_pass(repo_root: Path):
    inv = _build_invoice("<LocalCurrencyCode>CZK</LocalCurrencyCode>")
    report = ValidationReport()
    assert _br_cz_currency(
        inv, ns={"i": NS}, pre="i:", report=report, models_root=repo_root
    ) == 0


def test_br_cz_currency_fail(repo_root: Path):
    inv = _build_invoice("<LocalCurrencyCode>XYZ</LocalCurrencyCode>")
    report = ValidationReport()
    failures = _br_cz_currency(
        inv, ns={"i": NS}, pre="i:", report=report, models_root=repo_root
    )
    assert failures == 1
    assert report.errors[0].rule == "BR-CZ-CURRENCY"


# ---------------------------------------------------------------------------
# Gate 4 — round-trip
# ---------------------------------------------------------------------------


def test_round_trip_fails_on_garbage():
    report = ValidationReport()
    _gate_round_trip(report, serialised=b"<<not valid xml")
    assert report.gates["round_trip"] == "fail"
    assert any(e.rule == "round_trip" for e in report.errors)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def test_ico_mod11_known_good():
    assert _ico_mod11_ok("27074358") is True


def test_ico_mod11_known_bad():
    assert _ico_mod11_ok("27074359") is False
