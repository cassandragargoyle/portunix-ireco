# `ptx-ireco-worker` — invoice/document worker plugin

`ptx-ireco-worker` is the stateless Portunix plugin binary that runs
the parse + extract pipeline. It is the strojovací protějšek of the
driver CLI `ptx-ireco`: both share the same Python façade
(`ptx_ireco.worker.api.pipeline`), so behavior is identical for a
given input.

The worker is registered through `plugin-worker.json` at the repo
root. See [ADR-0005](../adr/0005-ireco-plugin-split.md) for the
design rationale.

## Subcommands

```text
ptx-ireco-worker process --file <pdf> [--config <cfg>] [-o <out.vim.json>] [--ocr|--no-ocr ...]
ptx-ireco-worker run     --file <pdf> [--config <cfg>] [-o <out.vim.json>] [--ocr|--no-ocr ...]
ptx-ireco-worker batch   --dir <input_dir> [--config <cfg>] [-o <output_dir>] [--ocr|--no-ocr ...]
ptx-ireco-worker task execute [--file request.json | < stdin]
ptx-ireco-worker --version
```

`run` is an alias of `process`. Both invoke the full parse + extract
pipeline against a single PDF and emit the same JSON summary on stdout.

`batch` walks every `*.pdf` under `--dir`, writes one `<stem>.vim.json`
per input into `-o`, and prints a JSON array of per-file summary
records. The exit code is `0` iff every file succeeded; otherwise `1`
with a partial summary.

`task execute` is the unified-task entry point — see the contract
section below.

### OCR flags (issue 007)

`process`, `run`, and `batch` accept the same `--ocr*` flags as
`ptx-ireco parse` — `--ocr` / `--no-ocr`, `--ocr-language`,
`--ocr-dpi`, `--ocr-min-ink-ratio`, `--ocr-mode`. Precedence is
identical: explicit flag > `parse.ocr` in `ireco.config.json` >
built-in defaults. See
[`docs/cli/parse.md`](parse.md#ocr-fallback-issue-007) for the full
reference, examples, and prerequisites (Tesseract, `pdf2image`,
Poppler).

The watcher's `cli` dispatch backend uses these flags to forward
`parse.ocr` from `ireco.config.json` to the subprocess — keeping the
`local` and `cli` backends behaviourally equivalent.

## Configuration precedence

For every subcommand, the worker resolves configuration in this order
(highest wins):

1. Explicit CLI flag (`--config`, `--models`, `-o`).
2. `ireco.config.json` in the current working directory (auto-detected
   when `--config` is absent).
3. Built-in defaults: no recipient list, models root = cwd (models in
   `./models/invoice/`).

When no `ireco.config.json` is present **and** no `--config` is passed,
the worker still runs — the output simply has no `recipient_id` and
does not enforce `doc_types` restrictions. This matches the driver
CLI's no-config behavior.

`models.path` in the config is the root that contains `models/invoice/`.
An absolute value is used as is; a relative value is anchored at the
directory of the config file, the same rule as `ptx-ireco-watcher`, so
the worker finds the same models whichever directory it is started from.
`--models <path>` overrides `models.path`; a relative `--models` is
resolved against the current working directory.

## Reserved doc types

When the resolved config declares any `doc_types` not in
`IMPLEMENTED_DOC_TYPES` (i.e. `receipt`, `delivery_note`,
`purchase_order`), the worker exits with code `3` and a clear
message — same policy as `ptx-ireco`'s
`EXIT_RESERVED_DOC_TYPE`.

## Batch with `known` tenancy

When the config declares `invoice.tenancy: "known"` with a
`recipients[]` list and `--dir` contains PDFs addressed to recipients
both inside and outside that list, the worker matches each file
independently: an unmatched PDF gets a summary entry without
`recipient_id` and the run does not error. This matches the
`multitenant` behavior of `ptx-ireco extract` today.

## TaskRequest / TaskResponse contract

`task execute` reads a JSON request (file via `--file` or stdin) and
emits a JSON response. The wire shape mirrors `ptx-reco-worker` so
both plugins can share dispatchers.

### Registered task types

| Task                       | Required input                       | Optional input          | Notes |
|----------------------------|--------------------------------------|-------------------------|-------|
| `ireco.invoice.parse`      | `pdf_path`, `out_path`               | —                       | Step 1 only. Writes `out_path`. |
| `ireco.invoice.extract`    | `vim_path`                           | `out_path`, `in_place`  | Step 2 only. Defaults to in-place. |
| `ireco.invoice.run`        | `pdf_path`, `out_path`               | —                       | Steps 1 + 2. Same target file. |

`out_path` is **mandatory** for `parse` and `run`: the TaskAdapter is a
machine surface, so missing path information is mapped to
`INVALID_INPUT` rather than being silently auto-derived.

### Request example (`ireco.invoice.run`)

```json
{
  "task": "ireco.invoice.run",
  "input": {
    "pdf_path": "/abs/scans/inv-001.pdf",
    "out_path": "/abs/out/inv-001.vim.json"
  },
  "config": {
    "models": { "path": "/abs/repo" },
    "invoice": {
      "tenancy": "known",
      "recipients": [
        {
          "id": "example-buyer",
          "name": "PŘÍKLADOVÁ a.s.",
          "ico": "00000019",
          "dic": "CZ00000019",
          "extraction": { "depth": "items" }
        }
      ]
    }
  },
  "trace_id": "trace-abc",
  "job_id": "job-001"
}
```

### Response (success)

```json
{
  "status": "success",
  "result": {
    "vim_path": "/abs/out/inv-001.vim.json",
    "template_match": "tmpl-uuid-or-null",
    "country": "CZE",
    "profile": "models/invoice/profiles/CZE-default.json",
    "flexylayout": "models/invoice/extraction/CZE-default.json",
    "entities": ["invoice_header", "issuer", "buyer", "totals", "payment"],
    "recipient_id": "example-buyer"
  },
  "meta": {
    "duration_ms": 1234.56,
    "plugin": "ireco-worker",
    "plugin_version": "0.1.0"
  },
  "trace_id": "trace-abc",
  "job_id": "job-001"
}
```

`recipient_id` is only present when the config declares `known` tenancy
**and** the parsed buyer matched a configured recipient.

### Response (error)

```json
{
  "status": "error",
  "error": {
    "code": "INVALID_INPUT",
    "message": "Missing required field: 'input.pdf_path'",
    "retryable": false
  },
  "meta": {
    "duration_ms": 0.42,
    "plugin": "ireco-worker",
    "plugin_version": "0.1.0"
  }
}
```

`trace_id` and `job_id` are echoed back on both success and error
responses when present in the request.

### Error codes

The wire codes are the canonical reco codes
(`ptx_reco.worker.task.errors`); only the codes the ireco worker can
emit are listed:

| Source                                                         | `error.code`        |
|----------------------------------------------------------------|---------------------|
| Missing/invalid `task` or `input` field                        | `INVALID_INPUT`     |
| Missing required handler field (e.g. `pdf_path`)               | `INVALID_INPUT`     |
| Unknown `task` value                                           | `UNKNOWN_TASK`      |
| `FileNotFoundError` for `pdf_path` / `vim_path`                | `INVALID_INPUT`     |
| `ConfigError` / `InvalidConfigError` / `UnsupportedVersionError` | `CONFIG_ERROR`    |
| `ExtractionError`, `ProfileNotFoundError`, `FlexyExtractionError` | `PROCESSING_ERROR` |
| `NotImplementedError` (reserved doc types)                     | `PROCESSING_ERROR`  |
| Anything else                                                  | `PROCESSING_ERROR`  |

Exit code policy for `task execute`: `0` when `status: success`, `1`
when `status: error`. All other subcommands use the driver CLI's
existing exit-code surface.

## Manifest version sync

`plugin-worker.json` declares the plugin version. It must stay aligned
with the package version in `pyproject.toml`. There is currently no
automated check; bump both files together when releasing. A future
Makefile target may stamp the manifest from `pyproject.toml` (mirroring
how reco does it).
