"""TaskAdapter — bridge between the unified task contract and ireco internals.

Accepts a ``TaskRequest`` dict and returns a ``TaskResponse`` dict with
the same wire shape as ``ptx-reco-worker``. Error codes come from
:mod:`ptx_ireco.worker.task.errors` (which re-exports the canonical
ptx-reco codes).

Per ADR-0005 the registry is local to ireco — this adapter does NOT
share a registry with ptx-reco's TaskAdapter. ``trace_id`` and
``job_id`` from the request are echoed back verbatim into the response
when present.
"""

from __future__ import annotations

import time
from typing import Any

import ptx_ireco
from ptx_ireco.config.loader import (
    ConfigError,
    InvalidConfigError,
    UnsupportedVersionError,
)
from ptx_ireco.invoice.flexy_engine import FlexyExtractionError
from ptx_ireco.invoice.profile_resolver import ProfileNotFoundError
from ptx_ireco.pipeline.extract import ExtractionError
from ptx_ireco.export.isdoc.api import ValidationFailed
from ptx_ireco.export.isdoc.errors import ExportError
from ptx_ireco.worker.task.errors import (
    CONFIG_ERROR,
    INVALID_INPUT,
    PROCESSING_ERROR,
    UNKNOWN_TASK,
    VALIDATION_ERROR,
    make_error,
)
from ptx_ireco.worker.task.registry import _HandlerInputError, get_handler

_PLUGIN_NAME = "ireco-worker"
_REQUIRED_REQUEST_FIELDS: tuple[str, ...] = ("task", "input")


class TaskAdapter:
    """Single entry point for the ``ireco-worker`` task contract.

    A single instance is reusable across requests; ``execute`` is
    stateless modulo any side effects from the underlying pipeline.
    """

    def __init__(self, default_config: dict[str, Any] | None = None) -> None:
        """Optional CLI-supplied default config merged under each request.

        The request's own ``config`` block always wins on key collision.
        Keeps the worker stateless: the adapter holds no IO state.
        """
        self._default_config = dict(default_config) if default_config else {}

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        """Execute a TaskRequest and return a TaskResponse dict.

        The response always contains a ``meta`` block with
        ``duration_ms``, ``plugin``, and ``plugin_version``. ``trace_id``
        / ``job_id`` from the request are echoed when present.
        """
        trace_id = request.get("trace_id") if isinstance(request, dict) else None
        job_id = request.get("job_id") if isinstance(request, dict) else None
        start_ns = time.monotonic_ns()

        try:
            response = self._do_execute(request)
        except Exception as exc:  # noqa: BLE001 — last-resort error mapping
            response = _error_response(
                make_error(PROCESSING_ERROR, f"{type(exc).__name__}: {exc}"),
            )

        elapsed_ms = (time.monotonic_ns() - start_ns) / 1_000_000
        response["meta"] = {
            "duration_ms": round(elapsed_ms, 2),
            "plugin": _PLUGIN_NAME,
            "plugin_version": ptx_ireco.__version__,
        }
        if trace_id is not None:
            response["trace_id"] = trace_id
        if job_id is not None:
            response["job_id"] = job_id
        return response

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict):
            return _error_response(
                make_error(INVALID_INPUT, "Request must be a JSON object"),
            )
        for field in _REQUIRED_REQUEST_FIELDS:
            if field not in request:
                return _error_response(
                    make_error(INVALID_INPUT, f"Missing required field: '{field}'"),
                )

        task_type = request["task"]
        if not isinstance(task_type, str):
            return _error_response(
                make_error(INVALID_INPUT, "Field 'task' must be a string"),
            )

        input_data = request.get("input") or {}
        if not isinstance(input_data, dict):
            return _error_response(
                make_error(INVALID_INPUT, "Field 'input' must be a JSON object"),
            )

        request_config = request.get("config") or {}
        if not isinstance(request_config, dict):
            return _error_response(
                make_error(INVALID_INPUT, "Field 'config' must be a JSON object"),
            )
        merged_config = {**self._default_config, **request_config}

        handler = get_handler(task_type)
        if handler is None:
            return _error_response(
                make_error(UNKNOWN_TASK, f"Unknown task type: '{task_type}'"),
            )

        try:
            result = handler(input_data, merged_config)
        except _HandlerInputError as exc:
            return _error_response(make_error(INVALID_INPUT, str(exc)))
        except FileNotFoundError as exc:
            return _error_response(make_error(INVALID_INPUT, str(exc)))
        except (InvalidConfigError, UnsupportedVersionError, ConfigError) as exc:
            return _error_response(make_error(CONFIG_ERROR, str(exc)))
        except (ExtractionError, ProfileNotFoundError, FlexyExtractionError) as exc:
            return _error_response(make_error(PROCESSING_ERROR, str(exc)))
        except ValidationFailed as exc:
            error = make_error(
                VALIDATION_ERROR,
                f"ISDOC validation failed: {len(exc.errors)} error(s)",
            )
            error["details"] = [e.to_dict() for e in exc.errors]
            return _error_response(error)
        except ExportError as exc:
            return _error_response(make_error(INVALID_INPUT, str(exc)))
        except NotImplementedError as exc:
            return _error_response(
                make_error(PROCESSING_ERROR, f"Reserved or unimplemented: {exc}"),
            )

        return {"status": "success", "result": result}


def _error_response(error: dict[str, Any]) -> dict[str, Any]:
    return {"status": "error", "error": error}
