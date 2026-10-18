"""ptx_ireco — invoice recognition pipeline.

Two explicit steps with a ``.vim.json`` file as the boundary, per ADR-0003:

    source document ──▶ Step 1: PARSE ──▶ *.vim.json
                                              (physical + structural)
                                              │
                                              ▼
                       Step 2: EXTRACT  ──▶ *.vim.json (semantic added)

Step 1 is delegated to :mod:`ptx_reco.vim` (the upstream parser library).
Step 2 lives entirely in this package and is invoice-aware.
"""

__version__ = "0.1.0"
