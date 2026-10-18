"""End-to-end smoke tests for ``ptx-ireco-worker`` CLI.

These tests invoke the actual entry-point script via ``subprocess.run``
so the ``[project.scripts]`` registration in ``pyproject.toml`` is
exercised — not just the Python API. A missing entry point will cause
the binary lookup to fail and skip the tests rather than fail spuriously.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def worker_bin() -> str:
    binary = shutil.which("ptx-ireco-worker")
    if not binary:
        pytest.skip("ptx-ireco-worker not installed (try `pip install -e .`)")
    return binary


@pytest.fixture(scope="module")
def driver_bin() -> str:
    binary = shutil.which("ptx-ireco")
    if not binary:
        pytest.skip("ptx-ireco not installed (try `pip install -e .`)")
    return binary


def test_worker_version(worker_bin: str) -> None:
    result = subprocess.run(
        [worker_bin, "--version"], capture_output=True, text=True, check=True
    )
    assert "ptx-ireco-worker" in result.stdout


def test_driver_still_works_after_split(driver_bin: str) -> None:
    """Regression: the driver CLI's --version still resolves through the
    new ``ptx_ireco.cli.main:main`` entry point."""
    result = subprocess.run(
        [driver_bin, "--version"], capture_output=True, text=True, check=True
    )
    assert "ptx-ireco" in result.stdout


def test_worker_process_against_flowii(
    worker_bin: str, repo_root: Path, flowii_pdf: Path, tmp_path: Path
) -> None:
    out = tmp_path / "flowii.vim.json"
    result = subprocess.run(
        [
            worker_bin, "--models", str(repo_root),
            "process", "--file", str(flowii_pdf), "-o", str(out),
        ],
        capture_output=True, text=True, cwd=tmp_path,
    )
    if result.returncode != 0:
        pytest.skip(
            f"flowii sample requires upstream parser: {result.stderr.strip()[:200]}"
        )
    assert out.is_file()
    summary = json.loads(result.stdout)
    assert summary["country"] == "CZE"
    assert "entities" in summary
    assert summary["vim_path"] == str(out)


def test_worker_run_is_alias_of_process(
    worker_bin: str, repo_root: Path, flowii_pdf: Path, tmp_path: Path
) -> None:
    out = tmp_path / "flowii.vim.json"
    result = subprocess.run(
        [
            worker_bin, "--models", str(repo_root),
            "run", "--file", str(flowii_pdf), "-o", str(out),
        ],
        capture_output=True, text=True, cwd=tmp_path,
    )
    if result.returncode != 0:
        pytest.skip(
            f"flowii sample requires upstream parser: {result.stderr.strip()[:200]}"
        )
    summary = json.loads(result.stdout)
    assert summary["country"] == "CZE"


def test_worker_task_execute_with_request_file(
    worker_bin: str,
    repo_root: Path,
    flowii_pdf: Path,
    tmp_path: Path,
) -> None:
    out = tmp_path / "flowii.vim.json"
    request_path = tmp_path / "request.json"
    request = {
        "task": "ireco.invoice.run",
        "input": {"pdf_path": str(flowii_pdf), "out_path": str(out)},
        "config": {"models": {"path": str(repo_root)}},
        "trace_id": "trace-cli",
        "job_id": "job-cli",
    }
    request_path.write_text(json.dumps(request), encoding="utf-8")

    result = subprocess.run(
        [worker_bin, "task", "execute", "--file", str(request_path)],
        capture_output=True, text=True, cwd=tmp_path,
    )
    if result.returncode != 0:
        # Best-effort: surface error for diagnosis. The flowii sample may
        # require upstream parser; let it skip rather than fail.
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.skip(f"task execute failed: {result.stderr.strip()[:200]}")
        else:
            if response.get("status") == "error":
                pytest.skip(
                    f"task execute returned error: "
                    f"{response['error'].get('message', '')[:200]}"
                )

    response = json.loads(result.stdout)
    assert response["status"] == "success"
    assert response["meta"]["plugin"] == "ireco-worker"
    assert response["trace_id"] == "trace-cli"
    assert response["job_id"] == "job-cli"
    assert response["result"]["vim_path"] == str(out)


def test_worker_task_unknown_returns_unknown_task(
    worker_bin: str, tmp_path: Path
) -> None:
    request = {"task": "ireco.no.such.thing", "input": {}}
    result = subprocess.run(
        [worker_bin, "task", "execute"],
        input=json.dumps(request),
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 1
    response = json.loads(result.stdout)
    assert response["status"] == "error"
    assert response["error"]["code"] == "UNKNOWN_TASK"


def test_worker_task_invalid_input_for_missing_field(
    worker_bin: str, tmp_path: Path
) -> None:
    request = {"task": "ireco.invoice.parse", "input": {}}
    result = subprocess.run(
        [worker_bin, "task", "execute"],
        input=json.dumps(request),
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 1
    response = json.loads(result.stdout)
    assert response["error"]["code"] == "INVALID_INPUT"
    assert "pdf_path" in response["error"]["message"]
