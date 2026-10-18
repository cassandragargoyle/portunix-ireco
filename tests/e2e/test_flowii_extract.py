"""End-to-end test: extract step against the Flowii sample (Java-parsed VIM).

Step 1 (PDF → VIM) is exercised separately in ``test_flowii_parse.py``;
this test takes the already-parsed reference file shipped under
``samples/invoice/`` so the assertion focuses on extraction correctness
and is not coupled to the upstream parser's status.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ptx_ireco.pipeline.extract import ModelPaths, extract_file


@pytest.fixture
def working_vim(tmp_path: Path, flowii_vim_java: Path) -> Path:
    """Copy the Java-produced VIM into a temp file we can mutate."""
    target = tmp_path / "flowii.vim.json"
    shutil.copy(flowii_vim_java, target)
    return target


def test_extract_flowii_sample(repo_root: Path, working_vim: Path) -> None:
    paths = ModelPaths.default(repo_root)
    result = extract_file(working_vim, paths)

    assert result.template_match is not None
    assert result.detected_country == "CZE"
    assert result.profile.path.name == "invoice-cze-2025-01-01.json"

    by_type = {e.type: e for e in result.entities}
    assert {"invoice_header", "issuer", "buyer", "totals", "payment"} <= by_type.keys()

    header = by_type["invoice_header"].fields
    assert header.get("invoice_number") == "26050001"
    assert header.get("issue_date") == "2026-05-09"
    assert header.get("tax_point_date") == "2026-05-09"
    assert header.get("due_date") == "2026-05-23"

    issuer = by_type["issuer"].fields
    assert issuer.get("name") == "Dříč s.r.o."
    assert issuer.get("tax_id") == "12345678"
    assert issuer.get("vat_id") == "CZ12345678"

    buyer = by_type["buyer"].fields
    assert buyer.get("name") == "PŘÍKLADOVÁ a.s."
    assert buyer.get("tax_id") == "00000019"
    assert buyer.get("vat_id") == "CZ00000019"

    totals = by_type["totals"].fields
    assert totals.get("total_without_vat") == "1000000.00"
    assert totals.get("total_vat") == "210000.00"
    assert totals.get("total_with_vat") == "1210000.00"
    assert totals.get("currency") == "CZK"

    payment = by_type["payment"].fields
    assert payment.get("variable_symbol") == "26050001"
    assert payment.get("amount_due") == "1210000.00"
    assert "Převodní příkaz" in (payment.get("method") or "")

    # All entities must reference a structural block (provenance).
    for entity in result.entities:
        assert entity.source_block, f"missing source_block on {entity.type}"
        assert 0.0 < entity.confidence <= 1.0


def test_extract_writes_back_into_same_file(repo_root: Path, working_vim: Path) -> None:
    paths = ModelPaths.default(repo_root)
    before = json.loads(working_vim.read_text(encoding="utf-8"))
    physical_before = before["layers"]["physical"]
    structural_before = before["layers"]["structural"]

    extract_file(working_vim, paths)

    after = json.loads(working_vim.read_text(encoding="utf-8"))
    # Other layers must be untouched.
    assert after["layers"]["physical"] == physical_before
    assert after["layers"]["structural"] == structural_before
    # Semantic layer must now have entities.
    entities = after["layers"]["semantic"]["entities"]
    assert len(entities) >= 5


def test_extract_is_idempotent_overwrite(repo_root: Path, working_vim: Path) -> None:
    paths = ModelPaths.default(repo_root)
    extract_file(working_vim, paths)
    first = json.loads(working_vim.read_text(encoding="utf-8"))
    extract_file(working_vim, paths)
    second = json.loads(working_vim.read_text(encoding="utf-8"))
    assert first == second


def test_extract_fails_clearly_on_unknown_country(tmp_path: Path) -> None:
    """If no template matches and no CZ anchors are found, extract errors out."""
    from ptx_ireco.pipeline.extract import ExtractionError

    foreign = {
        "vim_version": "1.5",
        "document": {"source": "x.pdf"},
        "layers": {
            "physical": {"blocks": []},
            "structural": {
                "blocks": [
                    {"id": "block_1", "header": "", "content": ["just some english text"]}
                ],
                "barcodes": [],
            },
            "semantic": {"entities": []},
        },
    }
    p = tmp_path / "foreign.vim.json"
    p.write_text(json.dumps(foreign), encoding="utf-8")

    # Models dir without templates dir → match_templates returns None.
    empty_models = ModelPaths(
        templates=tmp_path / "no-templates",
        profiles=tmp_path / "no-profiles",
        extraction=tmp_path / "no-extraction",
    )
    with pytest.raises(ExtractionError):
        extract_file(p, empty_models)
