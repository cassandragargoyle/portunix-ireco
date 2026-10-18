"""Worker TaskAdapter tests for the ireco.invoice.export task type."""

from __future__ import annotations

from pathlib import Path

import pytest

from ptx_ireco.worker.task.adapter import TaskAdapter
from ptx_ireco.worker.task.errors import VALIDATION_ERROR


@pytest.fixture
def fixture_vim() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "export" / "isdoc" / "flowii-FA_26050001.vim.json"


@pytest.fixture
def incomplete_vim() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "export" / "isdoc" / "incomplete-missing-bt-112.vim.json"


def test_export_task_success(tmp_path: Path, fixture_vim: Path, repo_root: Path):
    out = tmp_path / "out"
    out.mkdir()
    adapter = TaskAdapter()
    response = adapter.execute({
        "task": "ireco.invoice.export",
        "input": {
            "vim_path": str(fixture_vim),
            "output_dir": str(out),
            "options": {
                "format": "isdoc",
                "profile": "standard",
                "allow_incomplete": True,
                "models": str(repo_root),
            },
        },
    })
    assert response["status"] == "success"
    result = response["result"]
    assert any(p.endswith(".isdoc") for p in result["outputs"])
    assert any(p.endswith(".provenance.json") for p in result["outputs"])
    assert result["metadata"]["isdoc_version"] == "6.0.2"


def test_export_task_strict_validation_error(tmp_path: Path, incomplete_vim: Path, repo_root: Path):
    out = tmp_path / "out"
    out.mkdir()
    adapter = TaskAdapter()
    response = adapter.execute({
        "task": "ireco.invoice.export",
        "input": {
            "vim_path": str(incomplete_vim),
            "output_dir": str(out),
            "options": {
                "format": "isdoc",
                "profile": "standard",
                "allow_incomplete": False,
                "models": str(repo_root),
            },
        },
    })
    assert response["status"] == "error"
    assert response["error"]["code"] == VALIDATION_ERROR
    assert "details" in response["error"]
    assert response["error"]["details"]


def test_export_task_unknown_option_invalid_input(tmp_path: Path, fixture_vim: Path, repo_root: Path):
    adapter = TaskAdapter()
    response = adapter.execute({
        "task": "ireco.invoice.export",
        "input": {
            "vim_path": str(fixture_vim),
            "output_dir": str(tmp_path),
            "options": {"unknown_key": True, "models": str(repo_root)},
        },
    })
    assert response["status"] == "error"
    assert response["error"]["code"] == "INVALID_INPUT"


def test_existing_tasks_still_registered():
    """Regression: issue 003's tasks must remain registered."""
    from ptx_ireco.worker.task.registry import list_task_types

    types = set(list_task_types())
    assert {
        "ireco.invoice.parse",
        "ireco.invoice.extract",
        "ireco.invoice.run",
        "ireco.invoice.export",
    }.issubset(types)
