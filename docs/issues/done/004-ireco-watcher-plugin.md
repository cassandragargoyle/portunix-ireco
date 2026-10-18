# Issue 004 — Add `ptx-ireco-watcher` plugin

- **Status**: done
- **GitHub**: [#4](https://github.com/cassandragargoyle/portunix-ireco/issues/4)
- **Closed**: 2026-05-11
- **Priority**: high
- **Area**: cli, plugin, watcher, config
- **Related**: [ADR-0005](../../adr/0005-ireco-plugin-split.md) —
  authoritative architecture for the worker/watcher split;
  [ADR-0004](../../adr/0004-ireco-config-schema.md) (`ireco.config.json`
  schema this issue extends with optional sections).
- **Depends on**: [Issue 003](003-ireco-worker-plugin-split.md) —
  worker binary, `worker/api/pipeline` façade, and TaskAdapter must
  exist before this issue can land.
- **Branch**: `feature/issue-004-ireco-watcher-plugin`

## Goal

Add a long-running file-system watcher daemon `ptx-ireco-watcher` that
monitors `io.input_dir` (from `ireco.config.json`) for new PDFs and
dispatches them to `ptx-ireco-worker`. Modeled on `ptx-reco-watcher`
in the parent project.

```text
            ireco.config.json   ◀── ptx-ireco init (Step 8: watcher; section [5])
                    │
                    ▼
       ┌──────────────────────┐                         ┌─────────────────────┐
   PDF │ ptx-ireco-watcher    │  on detect (cooldown):  │ ptx-ireco-worker    │
   ──▶ │   monitor input_dir  │  ─── dispatch ──▶       │   process / run     │
       │   pool dispatcher    │  local | cli | grpc     │   (issue 003)       │
       │   event router       │                         └─────────────────────┘
       └──────────────────────┘                                    │
                    │ scan.{detected,processed,failed}             │
                    ▼                                              ▼
            optional events.jsonl                        output_dir / *.vim.json
```

## Background

`portunix-reco` ships `ptx-reco-watcher` as a sibling plugin to
`ptx-reco-worker`. The watcher uses `watchdog` to monitor
directories, applies a configurable cooldown to allow file writes to
finish, and dispatches each detected file via one of three backends
(`local`, `cli`, or reserved `grpc`). Multi-worker batches use a
`PoolDispatcher` with a `ProcessPoolExecutor`. ADR-0005 records the
decision to mirror this pattern in ireco.

This issue ships the **watcher plugin** half. Issue 003 ships the
worker half and is a hard prerequisite — the watcher's `local`
backend imports `ptx_ireco.worker.api.pipeline.run`, the `cli`
backend spawns `ptx-ireco-worker run`.

## Scope

### In scope

1. **CLI entry point** `ptx-ireco-watcher` registered in
   `pyproject.toml`.
2. **Module layout** — `src/ptx_ireco/watcher/` package with
   `monitor.py`, `dispatcher.py`, `config.py`, `events.py`,
   `router.py` (pattern copied from `ptx_reco/watcher/`).
3. **Three dispatch backends**:
   - `local` (default) — direct call to
     `ptx_ireco.worker.api.pipeline.run`.
   - `cli` — spawn `ptx-ireco-worker run --file <p> -o <o>`
     subprocess.
   - `grpc` — reserved (raises `DispatchError("not yet implemented")`).
4. **`ireco.config.json` schema additions** — two new optional
   top-level sections: `watcher` and `models`. Schema stays at
   `version: 1`; existing valid configs remain valid.
5. **Wizard updates** — append optional Step 8 (watcher settings) to
   the create flow; add `[5] watcher` and `[6] models` entries to the
   update section menu.
6. **Pool dispatcher** with `workers > 1` for concurrent batch /
   stream processing. Mirrors reco's `PoolDispatcher`.
7. **Plugin manifest** `plugin-watcher.json` at repo root, mirroring
   `portunix-reco/plugin-watcher.json` shape.
8. **Event stream** — three event types
   (`scan.detected`, `scan.processed`, `scan.failed`) emitted to
   registered callbacks. Optional `--events-log <file>` writes one
   JSON line per event (JSONL).
9. **Documentation** — `docs/cli/watcher.md` with CLI reference,
   config sections, dispatch backends, and example deployment recipe;
   root `README.md` updated.

### Out of scope

- gRPC server / client implementation (reserved per ADR-0005).
- Cross-host or remote dispatch (any non-local target beyond
  `cli`).
- Receipts / delivery notes / purchase orders (ADR-0004 reserves
  them; the watcher dispatches only PDFs whose declared
  `doc_types` is `["invoice"]` — the worker rejects others with
  exit code 3, which the watcher records as `scan.failed`).
- Schema version bump or any non-additive schema change.
- Replacing the existing `samples/`-based test fixtures (use
  `samples/invoice/flowii-FA_26050001.pdf`).

## Design

### Module layout (additions only)

```text
src/ptx_ireco/
├── cli/
│   └── watcher_main.py             # NEW — ptx-ireco-watcher entry
├── watcher/                        # NEW package
│   ├── __init__.py
│   ├── monitor.py                  # FileSystemMonitor (watchdog-based)
│   ├── dispatcher.py               # dispatch(file, cfg) + PoolDispatcher
│   ├── config.py                   # WatchConfig dataclass
│   ├── events.py                   # WatchEvent, EventType
│   └── router.py                   # EventRouter
└── config/
    ├── schema.py                   # extend with optional watcher/models sections
    └── wizard.py                   # extend with Step 8 + section [5]/[6]
```

### `pyproject.toml` change

```toml
[project.scripts]
ptx-ireco         = "ptx_ireco.cli.main:main"
ptx-ireco-worker  = "ptx_ireco.cli.worker_main:main"     # from issue 003
ptx-ireco-watcher = "ptx_ireco.cli.watcher_main:main"    # NEW
```

`ptx-ireco-watcher` adds a runtime dependency on `watchdog>=3.0`.
That dependency is already pulled in transitively via `ptx-reco`,
but pin it directly in ireco's `pyproject.toml` so the watcher's
import surface is explicit.

### `ireco.config.json` schema additions (v1)

Both new sections are **optional**. Absence falls back to defaults.

```jsonc
{
  "version": 1,
  // ... existing keys ...

  "watcher": {                       // NEW, optional
    "backend": "local",              // local | cli | grpc
    "workers": 1,                    // integer ≥ 1
    "cooldown_seconds": 1.0,         // float ≥ 0
    "patterns": ["*.pdf"],           // glob array
    "recursive": true                // bool
  },

  "models": {                        // NEW, optional
    "path": "./models"               // absolute or relative to config file
  }
}
```

Schema rules:

- `watcher.backend`: enum `"local" | "cli" | "grpc"`. Default
  `"local"`.
- `watcher.workers`: integer ≥ 1. Default `1`.
- `watcher.cooldown_seconds`: number ≥ 0. Default `1.0`.
- `watcher.patterns`: array of glob strings. Default `["*.pdf"]`.
- `watcher.recursive`: boolean. Default `true`.
- `models.path`: string path; absolute or relative to the config
  file. Default `"./models"`.

`docs/schemas/ireco-config-1.0.json` is updated to include both as
optional with the rules above. **Existing valid configs without these
keys continue to validate unchanged.**

### Wizard updates

#### Create flow — append Step 8

After the existing Step 7 (review summary), prompt:

```text
Step 8 (optional): Configure watcher settings? [y/N]
  if "n" (default): write defaults — equivalent to omitting the section.
  if "y":
        backend [local/cli/grpc]   (default: local)
        workers [1..16]            (default: 1)
        patterns (comma-separated) (default: *.pdf)
        cooldown seconds           (default: 1.0)
        recursive [y/n]            (default: y)
        models path                (default: ./models)
```

If the user accepts but answers all defaults, the writer MAY omit the
sections entirely (semantically equivalent). Implementer's choice;
document either way.

#### Update flow — extend section menu

```text
[1] doc types  [2] I/O paths  [3] invoice tenancy  [4] recipients
[5] watcher    [6] models     [7] write & exit     [q] quit
```

Selecting `[5]` or `[6]` shows existing values as defaults
(consistent with sections 1–4). Selecting either preserves all other
sections byte-equal where the schema allows ordering to be preserved
(per issue 002 acceptance criterion C).

### Watcher CLI shape

Mirrors `ptx-reco-watcher`:

```text
ptx-ireco-watcher [--config <ireco.config.json>]
                  [--watch-dir <dir> ...]
                  [--backend local|cli|grpc]
                  [--workers N]
                  [--patterns "*.pdf,*.PDF"]
                  [--cooldown 1.0]
                  [--no-recursive]
                  [-o <output_dir>]
                  [--models <models_path>]
                  [--events-log <file>]
                  [-v/--verbose]
                  [--version]
```

Config-loading precedence (highest → lowest):

1. Explicit `--config <path>`.
2. `./ireco.config.json` if present in cwd.
3. Built-in defaults (requires `--watch-dir` and `-o` on the CLI;
   refuses to start otherwise).

CLI flags override the loaded config, per-flag.

### Plugin manifest `plugin-watcher.json`

```json
{
  "name": "ireco-watcher",
  "version": "<pyproject.toml version>",
  "description": "File system monitor for invoice/document recognition pipeline",
  "author": "CassandraGargoyle",
  "license": "MIT",
  "plugin": {
    "type": "helper",
    "binary": "ptx-ireco-watcher",
    "runtime": "python",
    "python_min_version": "3.11",
    "interface": "cli,grpc"
  },
  "dependencies": {
    "portunix_min_version": "2.0.0",
    "ptx_ireco_worker_min_version": "<issue-003 version>",
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
      "name": "ptx-ireco-watcher",
      "description": "File system watcher for automatic invoice processing",
      "usage": "portunix ireco-watcher [options]",
      "subcommands": []
    }
  ]
}
```

### Dispatch backend semantics

| Backend | Trigger                                    | Crash isolation | Latency |
|---------|--------------------------------------------|-----------------|---------|
| `local` | `from ptx_ireco.worker.api.pipeline import run; run(path, out, models=...)` | None — a worker crash kills the watcher process | Lowest |
| `cli`   | `subprocess.run(["ptx-ireco-worker","run","--file",p,"-o",o, ...])` | Per-file — worker crash logs `scan.failed`, watcher stays alive | Higher (process spawn) |
| `grpc`  | Reserved — `DispatchError("not yet implemented")` | n/a | n/a |

For `--backend grpc`, the watcher SHOULD refuse to start with a clear
error rather than failing on the first dispatch (fail-fast at config
time). Implementer's choice; document either way in
`docs/cli/watcher.md`.

### Pool dispatcher

Reuse reco's pattern:

- `_worker_execute(file_path, ...)` is a module-level function so
  it pickles for `ProcessPoolExecutor`.
- The pool is created lazily — only when `workers > 1` AND a backend
  that supports parallelism is in use (`local` and `cli`).
- On `Ctrl-C` or `monitor.stop()`, the pool is shut down with
  `wait=True` so in-flight files complete cleanly.
- A worker crash returns `{"status": "error", "error.code":
  "WORKER_CRASH", ...}` — surfaced as `scan.failed`. Watcher does
  not exit.

### Events

Three event types (mirror reco):

- `scan.detected` — emitted as soon as the watcher sees the file
  (before cooldown).
- `scan.processed` — emitted after a successful dispatch with
  `metadata.result_keys` (or a richer summary if cheap).
- `scan.failed` — emitted on any dispatch failure with
  `metadata.error` containing the formatted error message.

`--events-log <file>` writes one JSON line per event. Format:

```json
{"event": "scan.processed", "source": "/abs/scan.pdf", "ts": "2026-05-09T10:30:00Z", "metadata": {"result_keys": ["entities","template_match"]}}
```

## Acceptance criteria

### A. Schema additions

- [ ] `docs/schemas/ireco-config-1.0.json` accepts the example config
      with `watcher` AND `models` blocks (validates green).
- [ ] All existing test-fixture and `samples/` configs (without
      `watcher`/`models`) continue to validate green.
- [ ] Invalid `watcher.backend` value (e.g. `"http"`) is rejected
      with a JSON-pointer-style error
      (`watcher.backend: must be one of [local, cli, grpc]`).
- [ ] Invalid `watcher.workers` value (`0`, `-1`, `"two"`) is
      rejected with a JSON-pointer-style error.
- [ ] `models.path` is validated as a string; missing files are NOT
      checked at validation time (consistent with `io.input_dir` /
      `io.output_dir`).

### B. Wizard updates

- [ ] Create flow ends with Step 8. Declining (default) writes a
      config without `watcher` or `models` sections (or with explicit
      defaults — implementer's choice; document the behavior).
- [ ] Accepting Step 8 with non-default values persists the user's
      choices; the resulting file validates green.
- [ ] Update menu shows `[5] watcher` and `[6] models` entries.
- [ ] Selecting `[5]` shows existing `watcher.*` values as defaults
      and accepts edits; other sections remain byte-equal (modulo
      canonicalized key order, per issue 002 criterion C).
- [ ] Selecting `[6]` edits `models.path` similarly.
- [ ] All issue 002 wizard acceptance criteria still pass against
      the extended schema and wizard.

### C. `ptx-ireco-watcher` CLI

- [ ] `ptx-ireco-watcher --version` prints the package version.
- [ ] In a directory with a valid `ireco.config.json` containing
      `io.input_dir`, `io.output_dir`, and optional `watcher`:
      starts, monitors `io.input_dir`, writes `.vim.json` files into
      `io.output_dir` for each detected PDF.
- [ ] Drop `samples/invoice/flowii-FA_26050001.pdf` into the watched
      dir → corresponding `.vim.json` appears in `io.output_dir`
      with the semantic layer populated. Cooldown is honored before
      dispatch.
- [ ] `--watch-dir <d>` overrides `io.input_dir`.
- [ ] `-o <d>` overrides `io.output_dir`.
- [ ] `--no-recursive` overrides `watcher.recursive`.
- [ ] `--patterns "*.pdf,*.PDF"` overrides `watcher.patterns`.
- [ ] `--cooldown 0.5` overrides `watcher.cooldown_seconds`.
- [ ] `--models <path>` overrides `models.path`.
- [ ] `Ctrl-C` exits cleanly: observer stopped, pool joined, no
      orphaned subprocesses, exit code 0.
- [ ] Without any config and without `--watch-dir`, the watcher
      refuses to start with a clear error pointing at one of the two
      authoring paths (`ptx-ireco init` or `--watch-dir`).

### D. Dispatch backends

- [ ] `--backend local` (default) processes files in-process via
      `ptx_ireco.worker.api.pipeline.run`.
- [ ] `--backend cli` spawns `ptx-ireco-worker run --file ... -o
      ...` per file. Subprocess exit 0 → `scan.processed`; non-zero
      → `scan.failed` with the worker's stderr captured into
      `metadata.error`.
- [ ] `--backend grpc` either refuses to start or fails fast on
      first dispatch with `DispatchError("not yet implemented")`.
      Document the chosen behavior in `docs/cli/watcher.md`.
- [ ] When `cli` backend is used, the watcher resolves the
      subprocess command with a deterministic rule (e.g. same
      `sys.executable` + `-m ptx_ireco.cli.worker_main`, OR via
      `shutil.which("ptx-ireco-worker")`). Document the rule.

### E. Concurrency

- [ ] `--workers 4` distributes pending files across 4 worker
      processes via `PoolDispatcher`. A test that drops 8 PDFs
      observes parallel processing (no strict ordering guarantee;
      simply verify total wall time < 0.6× the serial baseline on
      a multi-core CI runner — match reco's tolerance).
- [ ] Worker crash (simulated via `os._exit` from a mocked handler)
      surfaces as `scan.failed` with `error.code: WORKER_CRASH`;
      the watcher remains alive and continues processing subsequent
      files.
- [ ] Pool is shut down cleanly on `Ctrl-C`; `wait=True` waits for
      in-flight tasks before exit.

### F. Events

- [ ] `EventType.SCAN_DETECTED` emitted as soon as the file is seen
      (before cooldown).
- [ ] `EventType.SCAN_PROCESSED` emitted after successful dispatch
      with `metadata.result_keys` (or a richer summary).
- [ ] `EventType.SCAN_FAILED` emitted with `metadata.error` on
      failure.
- [ ] `--events-log <file>` writes one JSON line per event in the
      format documented above. The file is created with mode `0644`
      and appended to (does not truncate on restart).

### G. Plugin manifest

- [ ] `plugin-watcher.json` exists at repo root with the shape in
      the design.
- [ ] `version` stays in sync with `pyproject.toml` via the same
      mechanism as issue 003.
- [ ] `dependencies.ptx_ireco_worker_min_version` matches the
      version produced by issue 003 at the time this issue lands.

### H. Tests

- [ ] Unit tests for `WatchConfig.from_yaml` / `from_dict` covering
      defaults, overrides, and missing `watcher`/`models` sections.
- [ ] Unit tests for `dispatch()` per backend:
      - `local` with a fake façade returning a known result.
      - `cli` with a `subprocess.run` mock producing stdout JSON.
      - `grpc` raising `DispatchError`.
- [ ] Unit test for `PoolDispatcher` with 2 workers and 4 mock
      tasks (mirror reco's tests, including crash handling).
- [ ] Integration test: drop one fixture PDF into a tempdir
      configured via `ireco.config.json` (known tenancy with
      `example-buyer`) → assert `.vim.json` appears in the configured
      `output_dir` AND that `recipient_id == "example-buyer"` is
      attached.
- [ ] Integration test: `--backend cli` end-to-end against the same
      fixture (verifies the subprocess path).
- [ ] Regression: all issue 002 wizard tests pass against the
      extended schema and wizard.
- [ ] Regression: all issue 003 worker tests pass.

### I. Documentation

- [ ] `docs/cli/watcher.md` (new) documents the watcher CLI, the
      `watcher` / `models` config sections, the three dispatch
      backends with examples, and the event schema.
- [ ] `docs/cli/init.md` is updated to mention Step 8 and the
      `[5] watcher` / `[6] models` section menu entries.
- [ ] `docs/adr/0004-ireco-config-schema.md` gets a short
      "Schema additions in 0005" note (no version bump; this is
      additive). Alternatively, ADR-0005 itself records the
      additions and ADR-0004 is left untouched — implementer's
      choice; document.
- [ ] `README.md` (root) gets a "Watcher daemon" subsection
      alongside the worker subsection added in issue 003.

## Open architectural questions (resolve before / during impl)

1. **`cli` backend resolution.** Use `sys.executable -m
   ptx_ireco.cli.worker_main` (venv-deterministic) or
   `shutil.which("ptx-ireco-worker")` (PATH-dependent)? Suggested:
   `sys.executable -m` with `shutil.which` fallback when running from
   a non-venv context. Document and lock down in tests.
2. **`grpc` fail-fast vs. fail-on-dispatch.** ADR-0005 leaves the
   choice open. Suggested: fail-fast at config time so misconfigured
   deployments crash visibly instead of silently dropping files.
3. **Restart policy for the events log.** Append (default) or
   rotate? Suggested: pure append; rotation is a deployment concern
   handled by `logrotate` or similar. Document.
4. **`patterns` case-sensitivity.** `*.pdf` matches `scan.pdf` but
   not `scan.PDF` on case-sensitive filesystems. Should the wizard
   default to `["*.pdf", "*.PDF"]` or rely on the user to add both?
   Suggested: default to `["*.pdf"]`; case-sensitive operators add
   what they need. Note in `docs/cli/watcher.md`.

## Implementation hints (non-binding)

- ~80% of `watcher/` can be a structural copy of
  `ptx_reco/watcher/` with import paths swapped and the local
  dispatch function pointed at `ptx_ireco.worker.api.pipeline.run`.
  Keep file/class names identical so future cross-project audits
  remain easy.
- `_worker_execute` MUST be importable at module scope for
  pickling — same constraint as reco.
- Patterns default to `["*.pdf"]` (not the broader image set reco
  uses) — ireco only processes PDFs today.
- `cli` backend: add a simple `_resolve_worker_command()` helper
  with the chosen rule; covered by a unit test that asserts the
  command list.
- For the events log, use `json.dumps(event, ensure_ascii=False) +
  "\n"` — match reco's encoding decisions where they exist.

## Definition of done

- All acceptance criteria above are checked.
- A tester acceptance protocol per
  ISSUE-DEVELOPMENT-METHODOLOGY.md is recorded under
  `docs/testing/acceptance-004.md` with `STATUS: PASS`. The protocol
  MUST cover:
  - Both `local` and `cli` backends end-to-end on at least one OS
    (Linux for the primary tester).
  - Multi-worker pool with at least 4 fixture PDFs.
  - Wizard create AND update flows with the new sections.
- Branch `feature/issue-004-ireco-watcher-plugin` is merged into
  `main` only after that protocol exists AND issue 003 is closed.
- This issue file is moved to `docs/issues/done/` and the
  status row is updated in `docs/issues/README.md`.
