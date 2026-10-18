"""Error code surface for ireco-worker tasks.

Re-exports the canonical reco error codes (so the wire format stays
identical between ``ptx-reco-worker`` and ``ptx-ireco-worker``) and
provides :func:`make_error` shared with reco.

ireco-local extensions live below the re-export block. Currently:

- ``VALIDATION_ERROR`` — added for the ISDOC export task (issue 006).
  Surfaces required-field / XSD / business-rule / round-trip
  failures from :mod:`ptx_ireco.export.isdoc.validator`. The code is
  intentionally **not** pushed upstream into ptx-reco; it is invoice
  domain-specific.
"""

from __future__ import annotations

from ptx_reco.worker.task.errors import (
    BACKEND_UNAVAILABLE,
    CONFIG_ERROR,
    ENGINE_NOT_AVAILABLE,
    INVALID_INPUT,
    PROCESSING_ERROR,
    TIMEOUT,
    UNKNOWN_TASK,
    make_error,
)

# ireco-local error code (issue 006). Keep the literal close to the
# re-exports so a grep finds both.
VALIDATION_ERROR = "VALIDATION_ERROR"

__all__ = [
    "BACKEND_UNAVAILABLE",
    "CONFIG_ERROR",
    "ENGINE_NOT_AVAILABLE",
    "INVALID_INPUT",
    "PROCESSING_ERROR",
    "TIMEOUT",
    "UNKNOWN_TASK",
    "VALIDATION_ERROR",
    "make_error",
]
