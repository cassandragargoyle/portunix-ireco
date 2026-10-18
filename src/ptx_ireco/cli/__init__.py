"""``ptx-ireco`` CLI entry points.

This package replaces the former ``ptx_ireco.cli`` module:

- :mod:`ptx_ireco.cli.main` — driver CLI (`ptx-ireco`); wizard +
  thin ``parse``/``extract``/``run`` shims around the worker façade.
- :mod:`ptx_ireco.cli.worker_main` — plugin CLI (`ptx-ireco-worker`);
  ``process``/``run``/``batch``/``task execute`` against the same
  façade.

The legacy ``from ptx_ireco.cli import main`` import path keeps
working via the re-export below.
"""

from __future__ import annotations

from ptx_ireco.cli.main import main

__all__ = ["main"]
