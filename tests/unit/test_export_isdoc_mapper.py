"""Unit tests for ptx_ireco.export.isdoc.mapper."""

from __future__ import annotations

from typing import Any

from lxml import etree  # type: ignore[import-untyped]

from ptx_ireco.export.isdoc.mapper import Mapper
from ptx_ireco.export.isdoc.provenance import ProvenanceAccumulator


def _vim(entities: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "vim_version": "1.5",
        "document": {},
        "layers": {"semantic": {"entities": entities}},
    }


def _provenance() -> ProvenanceAccumulator:
    return ProvenanceAccumulator(isdoc_version="6.0.2", vim_source="x.vim.json")


def _local(elem: etree._Element) -> str:
    return etree.QName(elem).localname


def test_scalar_entry_emits_text_at_xpath():
    field_map = {
        "isdoc_version": "6.0.2",
        "namespace": "http://isdoc.cz/namespace/2013",
        "fields": [
            {
                "bt": "BT-1",
                "entity_type": "invoice_header",
                "field": "invoice_number",
                "isdoc_xpath": "/Invoice/ID",
                "required_in": ["minimal"],
            }
        ],
    }
    vim = _vim([
        {"type": "invoice_header", "source_block": "block_1", "confidence": 0.9,
         "fields": {"invoice_number": "FA_001"}}
    ])
    mapper = Mapper(field_map, profile="minimal", provenance=_provenance())
    root = mapper.build(vim)
    assert _local(root) == "Invoice"
    assert root.get("version") == "6.0.2"
    children = list(root)
    assert any(_local(c) == "ID" and c.text == "FA_001" for c in children)


def test_literal_entry_emits_constant_value():
    field_map = {
        "isdoc_version": "6.0.2",
        "namespace": "http://isdoc.cz/namespace/2013",
        "fields": [
            {"isdoc_xpath": "/Invoice/CurrRate", "value": "1", "required_in": ["minimal"]}
        ],
    }
    mapper = Mapper(field_map, profile="minimal", provenance=_provenance())
    root = mapper.build(_vim([]))
    el = root.find("{http://isdoc.cz/namespace/2013}CurrRate")
    assert el is not None and el.text == "1"


def test_group_entry_iterates_one_per_instance():
    field_map = {
        "isdoc_version": "6.0.2",
        "namespace": "http://isdoc.cz/namespace/2013",
        "fields": [
            {
                "bg": "BG-25",
                "entity_type": "invoice_line",
                "isdoc_xpath": "/Invoice/InvoiceLines/InvoiceLine",
                "required_in": ["standard"],
                "children": [
                    {"isdoc_xpath": "ID", "field": "id"},
                    {"isdoc_xpath": "Note", "field": "description"},
                ],
            }
        ],
    }
    vim = _vim([
        {"type": "invoice_line", "source_block": "b1",
         "fields": {"id": "1", "description": "Item A"}},
        {"type": "invoice_line", "source_block": "b2",
         "fields": {"id": "2", "description": "Item B"}},
    ])
    mapper = Mapper(field_map, profile="standard", provenance=_provenance())
    root = mapper.build(vim)
    ns = "{http://isdoc.cz/namespace/2013}"
    lines = root.findall(f"{ns}InvoiceLines/{ns}InvoiceLine")
    assert len(lines) == 2
    ids = [ln.find(f"{ns}ID").text for ln in lines]
    assert ids == ["1", "2"]


def test_transform_runs_when_specified():
    field_map = {
        "isdoc_version": "6.0.2",
        "namespace": "http://isdoc.cz/namespace/2013",
        "fields": [
            {
                "entity_type": "totals", "field": "total_with_vat",
                "isdoc_xpath": "/Invoice/LegalMonetaryTotal/PayableAmount",
                "transform": "decimal2", "required_in": ["minimal"],
            }
        ],
    }
    vim = _vim([
        {"type": "totals", "source_block": "b3", "fields": {"total_with_vat": "1 234,5"}}
    ])
    mapper = Mapper(field_map, profile="minimal", provenance=_provenance())
    root = mapper.build(vim)
    ns = "{http://isdoc.cz/namespace/2013}"
    el = root.find(f"{ns}LegalMonetaryTotal/{ns}PayableAmount")
    assert el is not None and el.text == "1234.50"


def test_missing_optional_value_skips_emit():
    field_map = {
        "isdoc_version": "6.0.2",
        "namespace": "http://isdoc.cz/namespace/2013",
        "fields": [
            {
                "entity_type": "invoice_header", "field": "tax_point_date",
                "isdoc_xpath": "/Invoice/TaxPointDate",
                "transform": "iso_date",
            }
        ],
    }
    vim = _vim([
        {"type": "invoice_header", "source_block": "b1",
         "fields": {"invoice_number": "FA_001"}}  # tax_point_date missing
    ])
    mapper = Mapper(field_map, profile="standard", provenance=_provenance())
    root = mapper.build(vim)
    assert root.find("{http://isdoc.cz/namespace/2013}TaxPointDate") is None


def test_transform_error_does_not_abort_build():
    """A bad value (e.g. parser produced label-as-value) should not crash
    the entire export — it should be recorded in mapper.transform_errors
    so api.py can fold it into the validation report."""
    field_map = {
        "isdoc_version": "6.0.2",
        "namespace": "http://isdoc.cz/namespace/2013",
        "fields": [
            {"bt": "BT-1", "entity_type": "invoice_header", "field": "invoice_number",
             "isdoc_xpath": "/Invoice/ID"},
            {"bt": "BT-40", "entity_type": "issuer", "field": "country",
             "isdoc_xpath": "/Invoice/AccountingSupplierParty/Party/PostalAddress/Country/IdentificationCode",
             "transform": "country_alpha2"},
        ],
    }
    vim = _vim([
        {"type": "invoice_header", "source_block": "b1",
         "fields": {"invoice_number": "FA_42"}},
        {"type": "issuer", "source_block": "b2",
         "fields": {"country": "Odběratel:"}},  # parser bug: label as value
    ])
    mapper = Mapper(field_map, profile="standard", provenance=_provenance())
    root = mapper.build(vim)  # must NOT raise
    # The good field still emitted
    ns = "{http://isdoc.cz/namespace/2013}"
    assert root.find(f"{ns}ID").text == "FA_42"
    # The bad field skipped
    assert root.find(f"{ns}AccountingSupplierParty/{ns}Party/{ns}PostalAddress/{ns}Country/{ns}IdentificationCode") is None
    # The transform error is recorded for api.py to surface
    assert len(mapper.transform_errors) == 1
    err = mapper.transform_errors[0]
    assert err.rule == "transform"
    assert err.bt == "BT-40"
    assert "Odběratel:" in err.value


def test_provenance_records_each_emit():
    prov = _provenance()
    field_map = {
        "isdoc_version": "6.0.2",
        "namespace": "http://isdoc.cz/namespace/2013",
        "fields": [
            {"bt": "BT-1", "entity_type": "invoice_header", "field": "invoice_number",
             "isdoc_xpath": "/Invoice/ID"},
        ],
    }
    vim = _vim([
        {"type": "invoice_header", "source_block": "block_3", "confidence": 0.97,
         "fields": {"invoice_number": "FA_42"}}
    ])
    Mapper(field_map, profile="standard", provenance=prov).build(vim)
    assert len(prov.entries) == 1
    e = prov.entries[0]
    assert e.bt == "BT-1"
    assert e.value == "FA_42"
    assert e.source_block == "block_3"
    assert e.confidence == 0.97
