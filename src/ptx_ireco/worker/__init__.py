"""ptx_ireco.worker — stateless invoice/document processing engine.

Subpackages:

- :mod:`ptx_ireco.worker.api` — pure-Python pipeline façade
  (``parse`` / ``extract`` / ``run``) shared by both the driver CLI
  (``ptx-ireco``) and the worker CLI (``ptx-ireco-worker``).
- :mod:`ptx_ireco.worker.task` — unified TaskAdapter contract
  (``ireco.invoice.parse|extract|run``) and error code surface.

See ADR-0005 (``docs/adr/0005-ireco-plugin-split.md``) for the
worker/watcher split rationale.
"""
