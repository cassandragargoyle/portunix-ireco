"""Unit tests for ptx_ireco.invoice.template_match."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptx_ireco.invoice.template_match import (
    TemplateMatch,
    load_templates,
    match_templates,
)


def _vim_doc_with_lines(*lines: str) -> dict:
    return {
        "vim_version": "1.5",
        "layers": {
            "physical": {"blocks": []},
            "structural": {
                "blocks": [
                    {"id": "block_1", "header": "", "content": list(lines)}
                ],
                "barcodes": [],
            },
        },
    }


def _write_template(dir_: Path, name: str, payload: dict) -> Path:
    p = dir_ / f"{name}.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_match_above_threshold(tmp_path: Path) -> None:
    _write_template(
        tmp_path,
        "tpl",
        {
            "id": "tpl-test",
            "country": "CZE",
            "match_threshold": 0.5,
            "fingerprint_rules": [
                {"type": "text_anchor", "pattern": "ACME s.r.o.", "weight": 1.0},
                {"type": "tax_id", "pattern": "12345678", "weight": 1.0},
            ],
        },
    )
    doc = _vim_doc_with_lines("ACME s.r.o.", "IČO: 12345678")
    match = match_templates(doc, tmp_path)
    assert isinstance(match, TemplateMatch)
    assert match.matched
    assert match.score == pytest.approx(1.0)
    assert match.country == "CZE"


def test_no_match_below_threshold(tmp_path: Path) -> None:
    _write_template(
        tmp_path,
        "tpl",
        {
            "id": "tpl-test",
            "country": "CZE",
            "match_threshold": 0.9,
            "fingerprint_rules": [
                {"type": "text_anchor", "pattern": "ACME s.r.o.", "weight": 1.0},
                {"type": "tax_id", "pattern": "99999999", "weight": 1.0},
            ],
        },
    )
    doc = _vim_doc_with_lines("ACME s.r.o.", "IČO: 12345678")
    assert match_templates(doc, tmp_path) is None


def test_regex_rule(tmp_path: Path) -> None:
    _write_template(
        tmp_path,
        "tpl",
        {
            "id": "tpl-rx",
            "country": "CZE",
            "match_threshold": 0.5,
            "fingerprint_rules": [
                {
                    "type": "text_anchor",
                    "pattern": "Faktura:\\s*\\d+",
                    "regex": True,
                    "weight": 1.0,
                }
            ],
        },
    )
    doc = _vim_doc_with_lines("Faktura: 26050001")
    match = match_templates(doc, tmp_path)
    assert match is not None and match.matched


def test_load_templates_skips_invalid(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "ok.json").write_text(
        json.dumps({"id": "ok", "country": "CZE", "fingerprint_rules": []}),
        encoding="utf-8",
    )
    templates = load_templates(tmp_path)
    assert [t["id"] for t in templates] == ["ok"]


def test_highest_score_wins(tmp_path: Path) -> None:
    _write_template(
        tmp_path,
        "weak",
        {
            "id": "weak",
            "country": "CZE",
            "match_threshold": 0.1,
            "fingerprint_rules": [
                {"type": "text_anchor", "pattern": "MISS", "weight": 1.0},
                {"type": "text_anchor", "pattern": "ACME", "weight": 1.0},
            ],
        },
    )
    _write_template(
        tmp_path,
        "strong",
        {
            "id": "strong",
            "country": "CZE",
            "match_threshold": 0.1,
            "fingerprint_rules": [
                {"type": "text_anchor", "pattern": "ACME", "weight": 1.0},
            ],
        },
    )
    doc = _vim_doc_with_lines("ACME s.r.o.")
    match = match_templates(doc, tmp_path)
    assert match is not None
    assert match.template_id == "strong"


def test_flowii_template_against_java_sample(repo_root: Path, flowii_vim_java: Path) -> None:
    doc = json.loads(flowii_vim_java.read_text(encoding="utf-8"))
    templates_dir = repo_root / "models" / "invoice" / "templates"
    match = match_templates(doc, templates_dir)
    assert match is not None
    assert match.template_id == "11748862-de2c-4845-abcd-4d65870e6da1"
    assert match.country == "CZE"
    assert match.matched
    assert match.flexylayout_id == "cze-invoice-generic"
