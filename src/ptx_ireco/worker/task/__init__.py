"""Unified TaskAdapter contract for ireco-worker.

The adapter accepts a ``TaskRequest`` dict and returns a ``TaskResponse``
dict with the same shape as ``ptx-reco-worker``. Error codes are
re-exported from :mod:`ptx_reco.worker.task.errors` to keep the wire
format aligned across plugins.
"""

from __future__ import annotations

from ptx_ireco.worker.task.adapter import TaskAdapter

__all__ = ["TaskAdapter"]
