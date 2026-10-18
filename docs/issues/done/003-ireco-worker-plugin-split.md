# Issue 003 — Extract `ptx-ireco-worker` plugin (worker/driver split)

- **Status**: done
- **GitHub**: [#3](https://github.com/cassandragargoyle/portunix-ireco/issues/3)
- **Closed**: 2026-05-10
- **Priority**: high
- **Area**: cli, plugin, task-adapter
- **Related**: [ADR-0005](../../adr/0005-ireco-plugin-split.md) —
  authoritative architecture for the worker/watcher split;
  [ADR-0004](../../adr/0004-ireco-config-schema.md),
  [ADR-0003](../../adr/0003-flexy-pipeline-two-step.md). Followed by
  [Issue 004](004-ireco-watcher-plugin.md) (depends on this issue).
- **Branch**: `feature/issue-003-ireco-worker-plugin-split`

## Goal

Carve out the stateless invoice/document processing engine into its
own Portunix plugin binary `ptx-ireco-worker`, modeled directly on
`ptx-reco-worker`, while keeping the existing `ptx-ireco` driver CLI
fully working with no behavior change visible to end users.

```text
before:                          after:
                                 ┌──────────────────────┐
                                 │ ptx-ireco            │  driver CLI
                                 │   init / parse /     │  (init wizard
┌──────────────────────┐         │   extract / run      │   + thin facades)
│ ptx-ireco            │         └──────────┬───────────┘
│   init / parse /     │   ───►             │ imports
│   extract / run      │                    ▼
│   (one binary,       │         ┌──────────────────────┐
│    inline business   │         │ ptx_ireco.worker.api │  pure-Python
│    logic)            │         │   .pipeline          │  facade
└──────────────────────┘         └──────────┬───────────┘
                                            │ same module
                                            ▼
                                 ┌──────────────────────┐
                                 │ ptx-ireco-worker     │  plugin binary
                                 │   process / batch /  │  + TaskAdapter
                                 │   run / task         │  (ireco.invoice.*)
                                 └──────────────────────┘
                                 + plugin-worker.json   manifest
```

## Background

`portunix-ireco` today is a single CLI binary that does both wizard
authoring and the parse/extract heavy lifting. The parent project
`portunix-reco` ships its processing engine as a separate plugin
(`ptx-reco-worker`) with a unified `TaskAdapter` contract and a
`plugin-worker.json` manifest, so that `portunix` can install,
register, and route to it uniformly. ADR-0005 records the decision to
mirror that pattern in ireco.

This issue ships the **worker plugin** half. Issue 004 ships the
watcher half and depends on this one.

## Scope

### In scope

1. **CLI entry point** `ptx-ireco-worker` registered in
   `pyproject.toml`.
2. **Module restructure** — convert `src/ptx_ireco/cli.py` into a
   `cli/` package (`main.py`, `worker_main.py`); add a `worker/`
   package containing `api/pipeline.py` (façade) and
   `task/{adapter,registry,errors}.py`.
3. **Pipeline façade** at `ptx_ireco.worker.api.pipeline` with
   pure-Python `parse(...)`, `extract(...)`, `run(...)` entry points
   (no argparse). The existing driver CLI imports from here; the new
   worker CLI imports from here. Single source of truth for the
   business logic.
4. **TaskAdapter** at `ptx_ireco.worker.task.adapter` with a local
   registry of `ireco.invoice.parse|extract|run`. Error codes
   imported from `ptx_reco.worker.task.errors` (`CONFIG_ERROR`,
   `INVALID_INPUT`, `UNKNOWN_TASK`, `PROCESSING_ERROR`, …).
5. **Worker CLI** with subcommands `process`, `run` (alias of
   process), `batch`, `task execute`, plus `--version`. Behavior
   matches `ptx-reco-worker` modulo PDF-vs-image and the
   `ireco.config.json` integration.
6. **Plugin manifest** `plugin-worker.json` at repo root, mirroring
   `portunix-reco/plugin-worker.json`. Manifest version stays in
   sync with `pyproject.toml` (Makefile target or pre-commit hook).
7. **Models path resolution helper** — explicit `--models` flag →
   `models.path` from `ireco.config.json` → cwd `./models`.
   Centralized in one helper so the precedence rule is auditable.
8. **`ptx-reco` floor pin** in `pyproject.toml`
   (`ptx-reco>=0.3.4` — current TaskAdapter / error-code surface).
9. **Documentation** — `docs/cli/worker.md` with subcommand
   reference and the TaskRequest/TaskResponse contract; root
   `README.md` updated; ADR-0005 flipped from `Proposed` to
   `Accepted`.

### Out of scope

- Watcher binary, `plugin-watcher.json`, dispatch backends, pool
  dispatcher → **issue 004**.
- Wizard updates for the `watcher` / `models` config sections →
  **issue 004** (where the watcher makes them useful).
- gRPC server (reserved per ADR-0005).
- Receipts / delivery notes / purchase orders — ADR-0004 already
  reserves them; the worker rejects them with the same
  `EXIT_RESERVED_DOC_TYPE = 3` policy as the driver CLI today.
- Any change to `ireco.config.json` schema — this issue does not
  touch the schema (issue 004 adds the optional `watcher`/`models`
  sections).

## Design

### Module layout (additions and one rename)

```text
src/ptx_ireco/
├── __init__.py                          # unchanged
├── cli/                                 # NEW package (replaces cli.py)
│   ├── __init__.py
│   ├── main.py                          # ← old cli.py — ptx-ireco entry
│   └── worker_main.py                   # NEW — ptx-ireco-worker entry
├── worker/                              # NEW package
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── pipeline.py                  # facade: parse, extract, run
│   └── task/
│       ├── __init__.py
│       ├── adapter.py                   # TaskAdapter (own)
│       ├── registry.py                  # ireco.invoice.* handlers
│       └── errors.py                    # codes + ireco-specific extras
├── pipeline/                            # existing — parse.py, extract.py
├── invoice/                             # existing
├── vim/                                 # existing
└── config/                              # existing
```

The rename `cli.py → cli/main.py` is mechanical. All call sites in
tests / docs that say `from ptx_ireco.cli import main` continue to
work because `cli/__init__.py` re-exports `main` for the transition
period (then drop the re-export after a clean release if desired —
not required for this issue).

### `pyproject.toml` changes

```toml
[project]
dependencies = [
    "ptx-reco>=0.3.4",          # was: "ptx-reco" (unpinned)
]

[project.scripts]
ptx-ireco = "ptx_ireco.cli.main:main"
ptx-ireco-worker = "ptx_ireco.cli.worker_main:main"   # NEW
```

### `worker/api/pipeline.py` façade (sketch)

Three pure-Python functions (no argparse, no `print`, no `sys.exit`).
Both the driver CLI and the worker CLI consume these.

```python
def parse(pdf_path: Path, out: Path, *, verbose: bool = False) -> Path: ...
def extract(
    vim_path: Path,
    *,
    out: Path | None = None,         # None → in-place
    in_place: bool = False,
    models: Path | None = None,
    options: ExtractionOptions | None = None,
) -> ExtractionResult: ...
def run(
    pdf_path: Path,
    out: Path,
    *,
    models: Path | None = None,
    options: ExtractionOptions | None = None,
    verbose: bool = False,
) -> ExtractionResult: ...
```

The existing `_cmd_parse` / `_cmd_extract` / `_cmd_run` in the driver
CLI become ~30-line shims that argparse → call façade → format
stdout. No business logic remains in the CLI module.

### Plugin manifest `plugin-worker.json`

```json
{
  "name": "ireco-worker",
  "version": "<pyproject.toml version>",
  "description": "Invoice and document processing engine on top of ptx-reco / VIM 1.5",
  "author": "CassandraGargoyle",
  "license": "MIT",
  "plugin": {
    "type": "helper",
    "binary": "ptx-ireco-worker",
    "runtime": "python",
    "python_min_version": "3.11",
    "interface": "cli,grpc"
  },
  "dependencies": {
    "portunix_min_version": "2.0.0",
    "os_support": ["linux", "windows", "darwin"],
    "optional_tools": []
  },
  "permissions": {
    "level": "limited",
    "filesystem": ["read", "write"],
    "network": []
  },
  "commands": [
    {
      "name": "ptx-ireco-worker",
      "description": "Invoice/document worker (parse + extract pipeline)",
      "usage": "portunix ireco-worker <subcommand> [options]",
      "subcommands": ["process", "run", "batch", "task"]
    }
  ]
}
```

### TaskAdapter contract

`TaskRequest` (input):

```json
{
  "task": "ireco.invoice.run",
  "input": { "pdf_path": "/abs/scan.pdf", "out_path": "/abs/out/scan.vim.json" },
  "config": {
    "models_path": "/abs/models",
    "io": { "input_dir": "/abs/in", "output_dir": "/abs/out" },
    "invoice": {
      "tenancy": "known",
      "recipients": [
        { "id": "example-buyer", "name": "...", "ico": "00000019", "dic": "CZ00000019",
          "extraction": { "depth": "items" } }
      ]
    }
  },
  "trace_id": "...",
  "job_id": "..."
}
```

`TaskResponse` (success):

```json
{
  "status": "success",
  "result": {
    "vim_path": "/abs/out/scan.vim.json",
    "template_match": "tmpl-uuid-or-null",
    "country": "CZE",
    "profile": "models/invoice/profiles/CZE-default.json",
    "flexylayout": "models/invoice/extraction/...",
    "entities": ["BuyerName", "BuyerICO", "TotalAmount"],
    "recipient_id": "example-buyer"
  },
  "meta": { "duration_ms": 1234.5, "plugin": "ireco-worker", "plugin_version": "0.2.0" },
  "trace_id": "...",
  "job_id": "..."
}
```

`TaskResponse` (error):

```json
{
  "status": "error",
  "error": { "code": "INVALID_INPUT", "message": "Missing required field: 'input.pdf_path'" },
  "meta": { "duration_ms": 0.42, "plugin": "ireco-worker", "plugin_version": "0.2.0" }
}
```

#### Registered task types

- `ireco.invoice.parse` — input `{pdf_path, out_path?}`. Result mirrors
  the dict written to `out_path` (or returned without writing if
  `out_path` is omitted — same precedence as the façade).
- `ireco.invoice.extract` — input `{vim_path, out_path?, in_place?}`,
  config `{models_path?, invoice.recipients?, invoice.tenancy?}` →
  result with semantic entities + optional `recipient_id`.
- `ireco.invoice.run` — input `{pdf_path, out_path}`, config as
  above → end-to-end result.

#### Error mapping

Use the codes from `ptx_reco.worker.task.errors`:

| Source                                                         | Code                |
|----------------------------------------------------------------|---------------------|
| Missing/invalid `task` or `input` field                        | `INVALID_INPUT`     |
| Unknown `task` value                                           | `UNKNOWN_TASK`      |
| `ConfigError`, `InvalidConfigError`, `UnsupportedVersionError` | `CONFIG_ERROR`      |
| `FileNotFoundError` for `pdf_path` / `vim_path`                | `INVALID_INPUT`     |
| `ExtractionError`, `ProfileNotFoundError`, `FlexyExtractionError` | `PROCESSING_ERROR` |
| `NotImplementedError` (reserved doc types)                     | `PROCESSING_ERROR`  |
| Anything else                                                  | `PROCESSING_ERROR`  |

### Driver CLI behavior — explicitly unchanged

Every flag, prompt, exit code, and stdout shape from issues 001 and
002 is preserved. The driver CLI's tests are the regression suite.

### Statelessness contract for the worker

The worker MUST run when:

- No `--config` is passed AND no `ireco.config.json` exists in cwd.
- `--models` is not passed AND no `models.path` is in any config.
  In that case, fall back to cwd `./models` (existing default).

`cwd` config is consulted when neither `--config` nor a TaskRequest
`config` block specifies one. CLI flag wins over config, config wins
over built-in default.

## Acceptance criteria

### A. Module restructure

- [ ] `src/ptx_ireco/cli/` package exists with `main.py`,
      `worker_main.py`, and `__init__.py`.
- [ ] `src/ptx_ireco/worker/api/pipeline.py` exposes `parse(...)`,
      `extract(...)`, `run(...)` as pure Python (no argparse / no
      `sys.exit`).
- [ ] `src/ptx_ireco/worker/task/{adapter,registry,errors}.py` exist
      with the contract described above.
- [ ] `pyproject.toml` registers both `ptx-ireco` and
      `ptx-ireco-worker` entry points; both are installable via
      `pip install -e .`.
- [ ] `pyproject.toml` pins `ptx-reco>=0.3.4`.

### B. `ptx-ireco-worker` CLI

- [ ] `ptx-ireco-worker --version` prints the package version.
- [ ] `ptx-ireco-worker process --file scan.pdf -o out.vim.json`
      produces a fully-extracted `.vim.json` (physical + structural +
      semantic) and exits 0.
- [ ] `ptx-ireco-worker run --file scan.pdf -o out.vim.json` is an
      alias for `process` (same behavior, same output).
- [ ] `ptx-ireco-worker batch --dir scans/ -o out/` writes one
      `.vim.json` per input PDF and prints a JSON summary array on
      stdout. Exit 0 if all succeed; non-zero with a partial summary
      if any fail.
- [ ] Without `--config` and without cwd `ireco.config.json`, the
      worker still runs and produces output without `recipient_id`
      (matches today's `ptx-ireco extract` no-config behavior).
- [ ] When cwd has a valid `ireco.config.json` AND no `--config` is
      passed, the worker uses it for `io` defaults and recipient
      list (same precedence as the driver CLI).
- [ ] Explicit `--config <path>` overrides any cwd config.
- [ ] Explicit `--models <path>` overrides `models.path` from the
      config (issue 004 will populate `models.path`; until then the
      flag is the only way to override the cwd default).
- [ ] Reserved doc types (`receipt`, `delivery_note`,
      `purchase_order`) cause exit code 3 with a clear message
      (matches the driver CLI's `EXIT_RESERVED_DOC_TYPE`).

### C. TaskAdapter contract

- [ ] `ptx-ireco-worker task execute --file request.json` accepts a
      TaskRequest JSON and prints a TaskResponse JSON to stdout.
      Exit 0 on `status: success`, 1 on `status: error`.
- [ ] `ptx-ireco-worker task execute < request.json` (stdin) works
      equivalently to `--file`.
- [ ] All three task types (`ireco.invoice.parse|extract|run`) are
      registered and dispatch correctly against the
      `samples/invoice/flowii-FA_26050001.pdf` fixture.
- [ ] TaskResponse `meta` block includes `plugin: "ireco-worker"`,
      `plugin_version`, `duration_ms` (rounded to 2 decimals).
- [ ] Unknown task type returns `error.code: UNKNOWN_TASK`.
- [ ] Missing required input field returns `error.code: INVALID_INPUT`
      with a message that names the missing field
      (e.g. `Missing required field: 'input.pdf_path'`).
- [ ] `ConfigError` from `ireco.config.json` validation surfaces as
      `error.code: CONFIG_ERROR` with the underlying validator
      message.
- [ ] `trace_id` and `job_id` from the request are echoed back into
      the response when provided.

### D. Plugin manifest

- [ ] `plugin-worker.json` exists at repo root with the shape in the
      design above.
- [ ] `version` field equals the `pyproject.toml` version. Mechanism
      to keep them aligned (Makefile target OR pre-commit hook OR
      generation script) is documented in `docs/cli/worker.md` or in
      the project README.
- [ ] `commands[0].subcommands` matches what the CLI accepts
      (`process`, `run`, `batch`, `task`).

### E. Driver CLI compatibility (regression)

- [ ] All issue 001 acceptance criteria still pass against
      `ptx-ireco parse|extract|run`.
- [ ] All issue 002 acceptance criteria still pass against
      `ptx-ireco init` (wizard create + update + `--from-file`
      flows).
- [ ] No change to `ptx-ireco`'s stdout/stderr formats, exit codes,
      or flag names is observable.

### F. Tests

- [ ] Unit tests for `ptx_ireco.worker.api.pipeline.{parse, extract,
      run}` covering: success path, missing-PDF path, invalid VIM
      path, `ExtractionError` surface, `ProfileNotFoundError`
      surface, reserved-doc-type rejection.
- [ ] Unit tests for the TaskAdapter:
      - Each registered task type with a golden TaskRequest fixture
        and the expected `result` shape (`vim_path`, `entities[]`,
        optional `recipient_id`).
      - Error code mapping for every row in the table above.
      - `trace_id` / `job_id` echo behavior.
      - `meta.plugin` / `meta.plugin_version` populated on success
        AND error responses.
- [ ] CLI smoke tests for `ptx-ireco-worker process|run|batch|task`
      using the existing `samples/invoice/flowii-FA_26050001.pdf`
      fixture. Each invokes the actual entry-point script via
      `subprocess.run` (so the entry-point registration in
      `pyproject.toml` is exercised, not just the Python API).
- [ ] Integration test: `ptx-ireco-worker task execute` with a
      `known`-tenancy config attaches `recipient_id: "example-buyer"`
      (or whatever the fixture defines) to the response.
- [ ] Regression: existing `ptx-ireco` test suite runs unchanged.

### G. Documentation

- [ ] `docs/cli/worker.md` (new) documents `ptx-ireco-worker`
      subcommands, flags, the TaskRequest/TaskResponse contract, and
      the error code table.
- [ ] `docs/adr/0005-ireco-plugin-split.md` is moved from
      `Proposed` to `Accepted` in the ADR file's status field AND in
      `docs/adr/README.md` index.
- [ ] `README.md` (root) gets a short subsection introducing the
      worker binary alongside the existing `ptx-ireco` description.

## Open architectural questions (resolve before / during impl)

1. **Worker `--config` semantics for `batch`.** When the user passes
   `--config foo.json` (with `invoice.tenancy: "known"`,
   `recipients: [A, B]`) and `--dir /scans` containing PDFs addressed
   to A, B, and a third recipient C, what happens for the file
   addressed to C? Suggested: same as `extract` per file — recipient
   match runs against `recipients[]`, no match → no `recipient_id`,
   no error (matches today's `multitenant` behavior for unknown
   recipients). Confirm and document in `docs/cli/worker.md`.
2. **`out_path` defaulting in `task execute`.** When the request
   omits `input.out_path` (parse/run cases), should the worker
   write to `<cwd>/out/<stem>.vim.json` or refuse with
   `INVALID_INPUT`? Suggested: refuse — the TaskAdapter is a
   machine surface; defaulting paths is a CLI concern.

## Implementation hints (non-binding)

- The cleanest mechanical refactor is:
  1. Create `cli/` package with `main.py` = old `cli.py`. Add a
     short re-export in `cli/__init__.py` (`from .main import main`)
     so old import paths still resolve.
  2. Create `worker/api/pipeline.py` re-exporting `parse_pdf_to_file`
     and `extract_file` under simpler façade names. The existing
     `pipeline/parse.py` and `pipeline/extract.py` stay in place.
  3. Write `worker/task/adapter.py` by copying
     `ptx_reco/worker/task/adapter.py` and replacing the registry
     import.
  4. Total diff target: < 800 lines (mostly new files; CLI changes
     are small).
- For the manifest version-sync, follow whatever pattern reco uses
  (look at `portunix-reco/scripts/` and `Makefile`).
- The worker MUST NOT take a code dependency on
  `ptx_reco.watcher.*` — only `ptx_reco.worker.*` and
  `ptx_reco.vim.*` are allowed imports.
- `concurrent.futures` is fine for the `batch` subcommand if useful;
  it is NOT a substitute for the `PoolDispatcher` (that is a watcher
  concern, issue 004).

## Definition of done

- All acceptance criteria above are checked.
- ADR-0005 status is flipped to `Accepted` (or a superseding ADR is
  recorded if the implementer deviates).
- A tester acceptance protocol per
  ISSUE-DEVELOPMENT-METHODOLOGY.md is recorded under
  `docs/testing/acceptance-003.md` with `STATUS: PASS`.
- Branch `feature/issue-003-ireco-worker-plugin-split` is merged
  into `main` only after that protocol exists.
- This issue file is moved to `docs/issues/done/` and the
  status row is updated in `docs/issues/README.md` (per the
  methodology).
