"""Unit tests for ``ptx_ireco.worker.task.adapter.TaskAdapter``.

The adapter's contract is exercised here at the unit level — handlers
themselves are patched so the tests stay fast and don't require model
files. End-to-end validation lives in the e2e suite.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

import ptx_ireco
from ptx_ireco.config.loader import InvalidConfigError
from ptx_ireco.invoice.profile_resolver import ProfileNotFoundError
from ptx_ireco.pipeline.extract import ExtractionError
from ptx_ireco.worker.task import TaskAdapter
from ptx_ireco.worker.task.registry import _HandlerInputError


def _stub_handler(result: dict[str, Any]):
    def _h(input_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        return result
    return _h


def _exploding_handler(exc: BaseException):
    def _h(input_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        raise exc
    return _h


# ---------------------------------------------------------------------------
# Required-field validation
# ---------------------------------------------------------------------------


def test_missing_task_field_returns_invalid_input() -> None:
    response = TaskAdapter().execute({"input": {}})
    assert response["status"] == "error"
    assert response["error"]["code"] == "INVALID_INPUT"
    assert "task" in response["error"]["message"]


def test_missing_input_field_returns_invalid_input() -> None:
    response = TaskAdapter().execute({"task": "ireco.invoice.parse"})
    assert response["status"] == "error"
    assert response["error"]["code"] == "INVALID_INPUT"
    assert "input" in response["error"]["message"]


def test_non_dict_request_is_invalid_input() -> None:
    response = TaskAdapter().execute("not a dict")  # type: ignore[arg-type]
    assert response["status"] == "error"
    assert response["error"]["code"] == "INVALID_INPUT"


def test_unknown_task_returns_unknown_task() -> None:
    response = TaskAdapter().execute({"task": "ireco.unknown", "input": {}})
    assert response["status"] == "error"
    assert response["error"]["code"] == "UNKNOWN_TASK"


# ---------------------------------------------------------------------------
# Successful dispatch
# ---------------------------------------------------------------------------


def test_dispatches_to_handler_for_known_task() -> None:
    expected = {"vim_path": "/tmp/x.vim.json"}
    with patch("ptx_ireco.worker.task.adapter.get_handler") as fake:
        fake.return_value = _stub_handler(expected)
        response = TaskAdapter().execute({
            "task": "ireco.invoice.parse",
            "input": {"pdf_path": "x.pdf", "out_path": "x.vim.json"},
        })
    assert response["status"] == "success"
    assert response["result"] == expected


def test_meta_block_always_present() -> None:
    with patch("ptx_ireco.worker.task.adapter.get_handler") as fake:
        fake.return_value = _stub_handler({"vim_path": "/x"})
        response = TaskAdapter().execute({
            "task": "ireco.invoice.parse",
            "input": {"pdf_path": "x.pdf", "out_path": "x.vim.json"},
        })
    meta = response["meta"]
    assert meta["plugin"] == "ireco-worker"
    assert meta["plugin_version"] == ptx_ireco.__version__
    assert isinstance(meta["duration_ms"], float)


def test_meta_present_on_error_responses() -> None:
    response = TaskAdapter().execute({"task": "ireco.unknown", "input": {}})
    assert response["status"] == "error"
    assert response["meta"]["plugin"] == "ireco-worker"
    assert response["meta"]["plugin_version"] == ptx_ireco.__version__


def test_trace_id_and_job_id_echoed_back() -> None:
    with patch("ptx_ireco.worker.task.adapter.get_handler") as fake:
        fake.return_value = _stub_handler({})
        response = TaskAdapter().execute({
            "task": "ireco.invoice.parse",
            "input": {"pdf_path": "x.pdf", "out_path": "x.vim.json"},
            "trace_id": "trace-123",
            "job_id": "job-456",
        })
    assert response["trace_id"] == "trace-123"
    assert response["job_id"] == "job-456"


def test_trace_id_echoed_on_error() -> None:
    response = TaskAdapter().execute({
        "task": "ireco.unknown",
        "input": {},
        "trace_id": "t1",
    })
    assert response["trace_id"] == "t1"


def test_default_config_is_layered_under_request_config() -> None:
    seen: dict[str, Any] = {}

    def _capture(input_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        seen.update(config)
        return {"ok": True}

    with patch("ptx_ireco.worker.task.adapter.get_handler") as fake:
        fake.return_value = _capture
        TaskAdapter(default_config={"models": {"path": "/from-default"}}).execute({
            "task": "ireco.invoice.parse",
            "input": {"pdf_path": "x.pdf", "out_path": "x.vim.json"},
            "config": {"invoice": {"tenancy": "anonymous"}},
        })
    assert seen["models"]["path"] == "/from-default"
    assert seen["invoice"]["tenancy"] == "anonymous"


def test_request_config_overrides_default_config() -> None:
    seen: dict[str, Any] = {}

    def _capture(input_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        seen.update(config)
        return {}

    with patch("ptx_ireco.worker.task.adapter.get_handler") as fake:
        fake.return_value = _capture
        TaskAdapter(default_config={"models": {"path": "/default"}}).execute({
            "task": "ireco.invoice.parse",
            "input": {"pdf_path": "x.pdf", "out_path": "x.vim.json"},
            "config": {"models": {"path": "/override"}},
        })
    assert seen["models"]["path"] == "/override"


# ---------------------------------------------------------------------------
# Error mapping (per issue 003 acceptance criteria table)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc, expected_code",
    [
        (_HandlerInputError("Missing required field: 'input.pdf_path'"), "INVALID_INPUT"),
        (FileNotFoundError("not here"), "INVALID_INPUT"),
        (InvalidConfigError("bad schema"), "CONFIG_ERROR"),
        (ExtractionError("no template"), "PROCESSING_ERROR"),
        (ProfileNotFoundError("no profile for CZE"), "PROCESSING_ERROR"),
        (NotImplementedError("receipt reserved"), "PROCESSING_ERROR"),
        (RuntimeError("something else"), "PROCESSING_ERROR"),
    ],
)
def test_handler_exception_maps_to_error_code(
    exc: BaseException, expected_code: str
) -> None:
    with patch("ptx_ireco.worker.task.adapter.get_handler") as fake:
        fake.return_value = _exploding_handler(exc)
        response = TaskAdapter().execute({
            "task": "ireco.invoice.parse",
            "input": {"pdf_path": "x.pdf", "out_path": "x.vim.json"},
        })
    assert response["status"] == "error"
    assert response["error"]["code"] == expected_code


def test_invalid_input_for_handler_validation() -> None:
    """Real registry: parse without pdf_path → INVALID_INPUT."""
    response = TaskAdapter().execute({
        "task": "ireco.invoice.parse",
        "input": {"out_path": "/tmp/x.vim.json"},
    })
    assert response["status"] == "error"
    assert response["error"]["code"] == "INVALID_INPUT"
    assert "pdf_path" in response["error"]["message"]
