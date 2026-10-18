"""End-to-end: a known-tenancy config attaches ``recipient_id`` to VIM output.

Mirrors ``test_flowii_extract`` but exercises the new
``ExtractionOptions`` plumbing with a recipient list whose IČO matches
the parsed buyer in the Flowii sample (``00000019`` → ``example-buyer``).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ptx_ireco.pipeline.extract import ExtractionOptions, ModelPaths, extract_file


@pytest.fixture
def working_vim(tmp_path: Path, flowii_vim_java: Path) -> Path:
    target = tmp_path / "flowii.vim.json"
    shutil.copy(flowii_vim_java, target)
    return target


def _recipients() -> list[dict]:
    return [
        {
            "id": "example-buyer",
            "name": "PŘÍKLADOVÁ a.s.",
            "ico": "00000019",
            "dic": "CZ00000019",
            "extraction": {"depth": "header"},
        },
        {
            "id": "globex",
            "name": "Globex a.s.",
            "ico": "87654321",
            "extraction": {"depth": "header"},
        },
    ]


def test_known_tenancy_attaches_recipient_id(
    repo_root: Path, working_vim: Path
) -> None:
    paths = ModelPaths.default(repo_root)
    opts = ExtractionOptions(recipients=_recipients())
    result = extract_file(working_vim, paths, options=opts)

    assert result.recipient_id == "example-buyer"
    assert result.recipient_match is not None
    assert result.recipient_match.matched_on in ("dic", "ico", "name")

    after = json.loads(working_vim.read_text(encoding="utf-8"))
    assert after["document"]["recipient_id"] == "example-buyer"


def test_no_options_means_no_recipient_id(
    repo_root: Path, working_vim: Path
) -> None:
    """Regression: behavior unchanged when no options are passed."""
    paths = ModelPaths.default(repo_root)
    result = extract_file(working_vim, paths)

    assert result.recipient_id is None
    assert result.recipient_match is None

    after = json.loads(working_vim.read_text(encoding="utf-8"))
    assert "recipient_id" not in (after.get("document") or {})


def test_unmatched_recipient_leaves_id_unset(
    repo_root: Path, working_vim: Path
) -> None:
    paths = ModelPaths.default(repo_root)
    opts = ExtractionOptions(
        recipients=[
            {
                "id": "globex",
                "name": "Globex a.s.",
                "ico": "87654321",
                "extraction": {"depth": "header"},
            }
        ]
    )
    result = extract_file(working_vim, paths, options=opts)
    assert result.recipient_id is None

    after = json.loads(working_vim.read_text(encoding="utf-8"))
    assert "recipient_id" not in (after.get("document") or {})
