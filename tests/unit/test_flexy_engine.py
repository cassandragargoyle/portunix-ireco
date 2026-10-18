"""Unit tests for ptx_ireco.invoice.flexy_engine primitives."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptx_ireco.invoice.flexy_engine import (
    FlexyExtractionError,
    _cz_date_iso,
    _normalize_amount,
    run_flexylayout,
)


def _doc(blocks: list[dict]) -> dict:
    return {
        "vim_version": "1.5",
        "layers": {
            "physical": {"blocks": []},
            "structural": {"blocks": blocks, "barcodes": []},
        },
    }


def test_cz_date_iso() -> None:
    assert _cz_date_iso("9.5.2026") == "2026-05-09"
    assert _cz_date_iso("23. 5. 2026".replace(" ", "")) == "2026-05-23"


def test_cz_date_iso_invalid() -> None:
    with pytest.raises(ValueError):
        _cz_date_iso("not-a-date")


def test_normalize_amount() -> None:
    assert _normalize_amount("1 210 000,00 Kč") == "1210000.00"
    assert _normalize_amount("210 000,00") == "210000.00"
    assert _normalize_amount("0,00 Kč") == "0.00"


def test_anchor_any_block_contains() -> None:
    doc = _doc(
        [
            {"id": "block_1", "header": "", "content": ["foo bar"]},
            {"id": "block_2", "header": "", "content": ["Variabilní symbol: 26050001"]},
        ]
    )
    flexy = {
        "entities": [
            {
                "type": "payment",
                "anchor": {"any_block_contains": "Variabilní symbol"},
                "confidence": 0.9,
                "fields": [
                    {
                        "name": "variable_symbol",
                        "from": "anchor_block",
                        "regex": "Variabilní\\s+symbol:?\\s*(\\d+)",
                    }
                ],
            }
        ]
    }
    entities = run_flexylayout(doc, flexy)
    assert len(entities) == 1
    assert entities[0].source_block == "block_2"
    assert entities[0].fields["variable_symbol"] == "26050001"


def test_anchor_block_after_header() -> None:
    doc = _doc(
        [
            {"id": "block_1", "header": "Odběratel:", "content": []},
            {"id": "block_2", "header": "", "content": ["PŘÍKLADOVÁ a.s.", "Ukázková 1"]},
        ]
    )
    flexy = {
        "entities": [
            {
                "type": "buyer",
                "anchor": {"block_after_header": "Odběratel:"},
                "confidence": 0.9,
                "fields": [
                    {"name": "name", "from": "anchor_block_line", "index": 0}
                ],
            }
        ]
    }
    entities = run_flexylayout(doc, flexy)
    assert len(entities) == 1
    assert entities[0].source_block == "block_2"
    assert entities[0].fields["name"] == "PŘÍKLADOVÁ a.s."


def test_required_entity_raises_when_anchor_missing() -> None:
    doc = _doc([{"id": "block_1", "header": "", "content": ["foo"]}])
    flexy = {
        "entities": [
            {
                "type": "missing",
                "anchor": {"any_block_contains": "NEVER"},
                "required": True,
                "confidence": 0.9,
                "fields": [],
            }
        ]
    }
    with pytest.raises(FlexyExtractionError):
        run_flexylayout(doc, flexy)


def test_optional_entity_silently_skipped(repo_root: Path) -> None:
    doc = _doc([{"id": "block_1", "header": "", "content": ["foo"]}])
    flexy = {
        "entities": [
            {
                "type": "missing",
                "anchor": {"any_block_contains": "NEVER"},
                "confidence": 0.9,
                "fields": [],
            }
        ]
    }
    assert run_flexylayout(doc, flexy) == []


def test_real_flexylayout_loads(repo_root: Path) -> None:
    """The shipped CZE flexylayout must be valid JSON and have entities."""
    p = repo_root / "models" / "invoice" / "extraction" / "cze" / "cze-invoice-generic.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["country"] == "CZE"
    assert isinstance(data["entities"], list)
    assert {e["type"] for e in data["entities"]} >= {
        "invoice_header",
        "issuer",
        "buyer",
        "totals",
        "payment",
    }
