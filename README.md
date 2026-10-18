# portunix-ireco

*Other languages: [Čeština](README.cs.md) · [Slovenčina](README.sk.md)*

## Overview

`portunix-ireco` extends [portunix-reco](https://github.com/CassandraGargoyle/portunix-reco) with document
extraction capabilities based on flexible layouts (flexylayouts). It targets processing of semi-structured
documents, primarily machine-printed — including machine-filled forms.

### What is reused from `portunix-reco`

Declared as a dependency on `ptx-reco>=0.3.4` (`pyproject.toml`).

- **VIM parser (PDF → VIM document)** — the `parse` step in
  `src/ptx_ireco/pipeline/parse.py` runs `ptx_reco.vim`'s
  `ExecutionEngine` + `PluginRegistry` with the `TextBlockExtractorPlugin`
  and best-effort barcode / table / graphics / toc / metadata extractors.
  The semantic `extract` step (flexylayouts) is ireco-only.
- **Worker task error codes** — `src/ptx_ireco/worker/task/errors.py`
  re-exports `ptx_reco.worker.task.errors` so the TaskRequest/TaskResponse
  wire format is identical between `ptx-reco-worker` and
  `ptx-ireco-worker`.
- **Worker + watcher plugin split pattern** — manifest layout
  (`plugin-worker.json` / `plugin-watcher.json`) and module structure
  follow the convention established in `portunix-reco` (see
  [ADR-0005](docs/adr/0005-ireco-plugin-split.md)).

## Project Information

- **GitHub Repository**: <https://github.com/cassandragargoyle/portunix-ireco>
- **Issues**: <https://github.com/cassandragargoyle/portunix-ireco/issues>
- **Project Name**: portunix-ireco

## Getting Started

```bash
# Create a virtual environment (uv is the preferred tool — see scripts/setup-venv.sh).
uv venv .venv
uv pip install -e .

# (Optional) declare what this directory processes — see docs/cli/init.md
ptx-ireco init                                      # interactive wizard
ptx-ireco init --from-file candidate.json           # CI / non-interactive

# Run the two-step pipeline against an invoice PDF:
ptx-ireco parse <invoice.pdf> -o <out.vim.json>     # PDF → VIM (physical+structural)
ptx-ireco extract <out.vim.json>                    # populate semantic in place
ptx-ireco run <invoice.pdf> -o <out.vim.json>       # parse + extract in one go
```

The `extract` step needs `models/invoice/{templates,profiles,extraction}/`
to be reachable from the working directory (or pass `--models <repo>`).
When an `ireco.config.json` is present, `parse`/`extract`/`run` use
`io.input_dir` / `io.output_dir` as defaults and (for `known` tenancy)
attach a matched `document.recipient_id` to the VIM output.

Scanned (image-only) PDFs can be recovered with optional per-page OCR:
`ptx-ireco parse scan.pdf -o scan.vim.json --ocr` (needs Tesseract +
`pdf2image`; see [`docs/cli/parse.md`](docs/cli/parse.md)).

`ptx-ireco` is the driver CLI used during development. The same
pipeline is also shipped as the standalone **`ptx-ireco-worker`**
plugin binary (`plugin-worker.json` manifest), which supports
`process` / `run` / `batch` and a unified `task execute` JSON
contract — see [`docs/cli/worker.md`](docs/cli/worker.md). Both
front-ends call the same Python façade
(`ptx_ireco.worker.api.pipeline`); behavior is identical for a given
input.

### Watcher daemon

For unattended operation, **`ptx-ireco-watcher`** monitors
`io.input_dir` for new PDFs and dispatches each one to
`ptx-ireco-worker` via a configurable backend
(`local` in-process, `cli` subprocess, or reserved `grpc`). Multi-worker
pool support enables concurrent batch processing; an event stream
(`scan.detected` / `scan.processed` / `scan.failed`) surfaces lifecycle
information and an optional `--events-log` JSONL feed. The watcher
is registered through `plugin-watcher.json` and documented in
[`docs/cli/watcher.md`](docs/cli/watcher.md).

```bash
# Drive entirely from ireco.config.json (io.input_dir + io.output_dir + watcher.*):
ptx-ireco-watcher

# Or with CLI overrides:
ptx-ireco-watcher --watch-dir ./scans -o ./out --backend cli --workers 4
```

### Export to ISDOC (issue 006 / [ADR-0007](docs/adr/0007-isdoc-export.md))

For Czech ERP integration, ireco can convert a populated
`*.vim.json` to **ISDOC 6.0.2** — either as a plain XML
(`*.isdoc`) or as an `*.isdocx` ZIP container with the original PDF
embedded. A JSON provenance sidecar maps every emitted XPath back
to its source PDF block so the audit trail survives the export.
The export is the optional third pipeline step (parse → extract →
**export**) and is also surfaced as the
`ireco.invoice.export` worker task and an opt-in watcher
post-processor (`watcher.post_process: ["export-isdoc"]`).

```bash
# CLI:
ptx-ireco export samples/invoice/flowii-FA_26050001.pdf.vim.json \
    --format isdoc --profile standard
```

See [`docs/cli/export.md`](docs/cli/export.md) for the full surface,
profiles, and validation gates.

## Documentation

- [Pipeline overview](docs/pipeline/README.md) — two-step flexy pipeline
  (parse → extract) and its CLI.
- [`ptx-ireco init`](docs/cli/init.md) — per-directory configuration
  wizard and the `ireco.config.json` schema.
- [`ptx-ireco-worker`](docs/cli/worker.md) — plugin binary CLI,
  TaskRequest/TaskResponse contract, error code reference.
- [`ptx-ireco-watcher`](docs/cli/watcher.md) — file-system watcher
  daemon, dispatch backends, event stream.
- [`ptx-ireco export`](docs/cli/export.md) — ISDOC 6.0.2 export
  (XML or ISDOCX bundle), validation gates, mapping tables.
- [Invoice extraction layer](models/invoice/extraction/README.md) —
  flexylayout JSON schema and per-country layouts.
- [Invoice model](models/invoice/README.md) — three-layer invoice model
  (templates / core + profiles / extraction).
- [docs/contributing/](docs/contributing/) — development guidelines.

## License

MIT — see [LICENSE](LICENSE).
