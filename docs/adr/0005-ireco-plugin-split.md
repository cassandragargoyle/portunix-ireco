# ADR-0005: ireco worker/watcher plugin split

- **Status**: Accepted (wizard-placement statement *superseded in part
  by [ADR-0006](0006-runtime-only-scope.md)* on 2026-05-10 — the
  `init` wizard moves out of the driver CLI to `portunix-reco-studio`
  per INT-037; the rest of this ADR is unaffected)
- **Date**: 2026-05-09
- **Deciders**: zdendaku
- **Scope**: top-level architecture of `portunix-ireco` — binaries,
  plugin manifests, dispatch backends, and the unified task contract.
- **Relates to**: [ADR-0003](0003-flexy-pipeline-two-step.md) (two-step
  parse → extract pipeline), [ADR-0004](0004-ireco-config-schema.md)
  (`ireco.config.json` schema). Reference implementation in the sibling
  `portunix-reco` project (worker/watcher split, `plugin-*.json`
  manifests, `TaskAdapter` contract).

## Context

`portunix-ireco` today is a single CLI binary (`ptx-ireco`) with
subcommands `init / parse / extract / run`. It depends on the parent
`portunix-reco` Python package and uses its VIM parser via direct
imports.

`portunix-reco`, however, has a meaningfully different shape: it ships
**two Portunix plugin binaries**, each with its own manifest:

- `ptx-reco-worker` — stateless processing engine (CLI + Python API +
  reserved gRPC), driven by a unified `TaskAdapter` contract.
- `ptx-reco-watcher` — long-running file-system watcher that dispatches
  detected files to the worker via `local | cli | grpc` backends, with
  multi-process pool support and a typed event stream
  (`scan.detected`, `scan.processed`, `scan.failed`).

Each plugin is registered with `portunix` through `plugin-worker.json` /
`plugin-watcher.json` and slots into Portunix's install/run/upgrade
flow without bespoke handling.

ireco needs the same shape because:

1. **Operational symmetry.** A typical deployment ingests PDFs into a
   watched directory and produces `.vim.json` results in another
   directory. Today the operator has to script that themselves; in
   reco they get it for free from the watcher daemon.
2. **`ireco.config.json` already declares the plumbing.** Issue 002 /
   ADR-0004 introduced `io.input_dir` and `io.output_dir`. The watcher
   is the natural consumer of those fields — without it, the config's
   "I/O" section is purely advisory.
3. **Plugin lifecycle.** `portunix` already understands reco's two
   plugins. Surfacing ireco as the same shape (two manifests, two
   binaries, one driver CLI) means it integrates the same way.
4. **Reusable concurrency model.** reco's `PoolDispatcher` and
   `--workers N` machinery solves a real problem (parallel batch
   processing with crash isolation). Mirroring its dispatch interface
   lets ireco adopt that pattern without re-deriving it.

What ireco brings on top of reco's pattern:

- Doc-type-aware processing (invoices today; receipts /
  delivery_notes / purchase_orders reserved per ADR-0004).
- A directory-level config (`ireco.config.json`) with a wizard.
- A two-step parse → extract pipeline whose boundary is a `.vim.json`
  file (ADR-0003). The watcher's natural dispatch unit is therefore
  "a PDF in, a `.vim.json` out", not "an image in, an arbitrary JSON
  out" as reco's watcher assumes.

## Decision

Restructure `portunix-ireco` into **two Portunix plugins plus a thin
driver CLI**, modeled directly on reco.

```text
                            ireco.config.json   ◀── ptx-ireco init (wizard, driver CLI)
                                    │
              ┌─────────────────────┴─────────────────────┐
              │                                           │
              ▼                                           ▼
     ┌────────────────┐                          ┌─────────────────┐
     │ ptx-ireco-     │  on file detection:      │ ptx-ireco-      │
     │ watcher        │  ──────────────────▶     │ worker          │
     │ (daemon)       │  dispatch backend:       │ (stateless)     │
     │                │  local | cli | grpc      │                 │
     └────────────────┘                          └─────────────────┘
              ▲                                           │
              │ events: scan.detected | scan.processed |  │
              │         scan.failed                       │
              │                                           ▼
              │                                output_dir / *.vim.json
              └────────────────────────────────────────────────────
```

### Plugin 1 — `ireco-worker` (`ptx-ireco-worker`)

Stateless invoice/document processing engine.

- **Manifest** `plugin-worker.json` at repo root, mirroring
  reco's manifest shape.
- **Python entry point** registered in `pyproject.toml`:
  `ptx-ireco-worker = "ptx_ireco.cli.worker_main:main"`.
- **Module layout** (additions only):

  ```text
  src/ptx_ireco/
  ├── cli/                              # NEW package (replaces cli.py)
  │   ├── main.py                       # ptx-ireco (driver, unchanged UX)
  │   └── worker_main.py                # ptx-ireco-worker
  └── worker/                           # NEW package
      ├── api/
      │   └── pipeline.py               # facade: parse, extract, run
      └── task/
          ├── adapter.py                # TaskAdapter (own)
          ├── registry.py               # ireco.invoice.* handlers
          └── errors.py                 # error code constants
  ```

- **CLI shape** (mirrors `ptx-reco-worker`):

  ```text
  ptx-ireco-worker process --file <pdf> [--config <cfg>] [-o <out.vim.json>]
  ptx-ireco-worker run     --file <pdf> [--config <cfg>] [-o <out.vim.json>]
  ptx-ireco-worker batch   --dir <input_dir> [--config <cfg>] [-o <output_dir>]
  ptx-ireco-worker task execute [--file request.json | < stdin]
  ptx-ireco-worker --version
  ```

- **Task contract** — unified TaskRequest/TaskResponse JSON, same
  shape as reco. ireco-namespaced task types:
  - `ireco.invoice.parse` — input `{pdf_path}` → result with VIM dict.
  - `ireco.invoice.extract` — input `{vim_path, in_place, out_path}`,
    config `{models_path, invoice.recipients, invoice.tenancy}` →
    result with semantic entities + optional `recipient_id`.
  - `ireco.invoice.run` — input `{pdf_path, out_path}` → end-to-end
    result with `vim_path` and a summary block.

- **Statelessness contract.** Every call carries its own
  `--config` (or TaskRequest `config` block) and `--models` path. The
  worker MUST run cleanly when neither cwd config nor a `--config`
  flag is supplied (preserves today's per-file UX).

### Plugin 2 — `ireco-watcher` (`ptx-ireco-watcher`)

File-system watcher that monitors a directory for new PDFs and
dispatches them to the worker.

- **Manifest** `plugin-watcher.json` at repo root.
- **Python entry point** in `pyproject.toml`:
  `ptx-ireco-watcher = "ptx_ireco.cli.watcher_main:main"`.
- **CLI shape** (mirrors `ptx-reco-watcher`):

  ```text
  ptx-ireco-watcher [--config <ireco.config.json>] [--watch-dir <d>]
                    [--backend local|cli|grpc] [--workers N]
                    [--patterns "*.pdf"] [--cooldown 1.0]
                    [--no-recursive] [-o <output_dir>]
                    [--models <models_path>] [--events-log <file>]
                    [--version]
  ```

- **Default behavior**: read `ireco.config.json` from cwd (or
  `--config`); take `io.input_dir`, `io.output_dir`, and the new
  `watcher.*` block from there.

- **Dispatch backends**:
  - `local` (default) — direct in-process call to
    `ptx_ireco.worker.api.pipeline.run`.
  - `cli` — spawn `ptx-ireco-worker run --file <p> -o <o>` subprocess.
  - `grpc` — **reserved**: raises `DispatchError("not yet
    implemented")`. Manifest still declares `interface: cli,grpc` for
    forward compatibility.

- **Concurrency**: reuse the `PoolDispatcher` pattern from reco when
  `workers > 1`. `_worker_execute` must be a module-level function
  for pickling.

- **Events** emitted (same names as reco):
  `scan.detected`, `scan.processed`, `scan.failed`. Optional
  `--events-log <file>` writes one JSON line per event.

### Driver CLI — `ptx-ireco`

- **Unchanged UX**: `init`, `parse`, `extract`, `run` keep their
  flags, exit codes, and behavior from issues 001/002.
- **Internally**: `parse|extract|run` become **thin facades** that
  import `ptx_ireco.worker.api.pipeline` directly. They are NOT
  subprocess shells around `ptx-ireco-worker`; both surfaces share
  the same Python API.
- **Wizard (`init`)** stays in the driver CLI. It is not duplicated
  into worker or watcher.

### `ireco.config.json` schema additions (v1, optional sections)

The schema **stays at `version: 1`** (no migration). Two new
top-level sections are optional with sensible defaults:

```jsonc
{
  "version": 1,
  // ... existing keys ...

  "watcher": {                  // NEW, optional
    "backend": "local",         // local | cli | grpc
    "workers": 1,
    "cooldown_seconds": 1.0,
    "patterns": ["*.pdf"],
    "recursive": true
  },

  "models": {                   // NEW, optional
    "path": "./models"          // root containing models/invoice/{templates,profiles,extraction}
  }
}
```

Existing valid configs without these keys remain valid. CLI flag
precedence (highest → lowest): explicit CLI flag → `ireco.config.json`
value → built-in default.

The wizard gains an optional **Step 8 (watcher settings)** in the
create flow and a `[5] watcher` / `[6] models` entry in the update
section menu. These changes land with issue 004 (where the watcher
makes them useful).

### TaskAdapter — own registry, types from reco

ireco's worker has its **own** TaskAdapter
(`ptx_ireco.worker.task.adapter`). It imports type aliases / error
code constants from `ptx_reco.worker.task.errors`, but the registry of
handlers is local to ireco.

Reasoning:

- **Plugin lifecycle independence** — bumping ptx-reco shouldn't
  force a co-bump of ptx-ireco; ireco's contract evolves on its own
  cadence.
- **Distinct namespaces** — `ireco.invoice.*` vs. `reco.*`; natural to
  keep registries separate.
- **Future flexibility** — eventually allows reco-less consumers
  (e.g. running ireco against a different VIM parser) without
  disentangling from a shared registry.

### gRPC

**Reserved but not implemented** in this ADR's issues. Same approach
as reco today: manifest declares the interface, dispatch path raises
`DispatchError`. A follow-up issue lands gRPC server + client when
it becomes a priority.

## Consequences

### Positive

- **Symmetric with reco** — same install/run/upgrade flow under
  `portunix`, no special-case handling.
- **Watcher unblocks batch automation** — operators get
  folder-watch + dispatch for free, mirroring reco's value
  proposition.
- **Stateless worker is testable in isolation** — TaskAdapter golden
  tests, mocked `models/`, no filesystem scaffolding.
- **Dispatch backends compose** — `local` for low overhead, `cli`
  for crash isolation, `grpc` later for cross-host.
- **`ireco.config.json` becomes the shared contract** between wizard,
  worker (for defaults), and watcher.
- **Backwards-compatible schema** — `version: 1` configs from
  issue 002 keep validating; no migration tooling needed.

### Negative

- **Three CLI binaries to maintain** (`ptx-ireco`,
  `ptx-ireco-worker`, `ptx-ireco-watcher`). Mitigation: the driver
  CLI is a 100-line thin façade; worker and watcher mains are
  near-direct mirrors of the reco files.
- **Two new manifests to keep aligned** with version bumps.
  Mitigation: a Makefile target reads the package version from
  `pyproject.toml` and stamps both JSONs (same as reco does today).
- **Slight test duplication.** Worker handlers are exercised via
  direct Python calls (driver CLI tests) AND via TaskAdapter (worker
  CLI tests). Acceptable: the TaskAdapter shim is the actual unit
  under test in the second path.

### Neutral

- **Pool dispatcher complexity is inherited rather than written from
  scratch** — adopt reco's pattern as-is, but **without** a code
  dependency on `ptx_reco.watcher.*`. Reasoning: reco's watcher is
  image-shaped; ireco's is PDF→VIM-shaped, and copy is cheaper than
  building an abstraction over diverging domains.
- **Reserved doc types** (`receipt`, `delivery_note`,
  `purchase_order`) stay reserved per ADR-0004; the worker rejects
  them with the same `NotImplementedError` policy.

## Alternatives considered

- **Single binary with subcommands.** Works for ireco-as-library, but
  does not fit Portunix's plugin model and gives up the watcher
  daemonization story.
- **ireco worker as a sub-handler inside `ptx-reco-worker`.** Rejected:
  cross-plugin coupling, version skew risk, and forces reco to grow
  doc-type knowledge it doesn't otherwise need.
- **Watcher as a thin wrapper around reco's `ptx-reco-watcher`** (just
  point it at ireco-worker). Tempting, but reco's watcher dispatches
  at the `RecoPipeline` boundary; ireco's natural unit is the
  parse → extract pair with a `.vim.json` file boundary. Forcing
  ireco through reco's watcher would either widen reco's contract or
  shim inside ireco-worker. Cleaner to ship a sibling watcher.
- **Schema bump to v2.** Rejected: optional new sections are
  backwards-compatible; no migration cost is justified.
- **Shared TaskAdapter registry with reco** (import and register).
  Rejected: tight coupling, version skew. Local registry keeps the
  plugin boundary clean.

## Open questions

1. **Worker `--config` semantics for batch mode.** When the user
   passes both `--config foo.json` and `--dir /scans` with PDFs
   addressed to different recipients, which `recipient_id` wins per
   file? Suggested rule: same as today's `extract` — recipient match
   runs per file against `invoice.recipients[]`. To be confirmed in
   issue 003 acceptance.
2. **`models.path` resolution precedence.** Suggested: explicit
   `--models` flag → `models.path` from `ireco.config.json` → cwd
   `./models`. Implementer should add a single
   `_resolve_model_paths(args, cfg)` helper to keep the rule
   auditable.
3. **Watcher backend default.** `local` (low overhead, single
   process) is right for development; `cli` (crash isolation,
   per-file OOM safety) for production. The schema default is
   `local`; deployment recipes should override. To be confirmed in
   issue 004.
4. **`ptx-reco` minimum version pin.** ireco currently depends on
   `ptx-reco` without a version constraint. Issue 003 should pin a
   floor (`>= 0.3.4`) tied to the TaskAdapter / error-code surface
   the worker re-uses.

## References

- [ADR-0003](0003-flexy-pipeline-two-step.md) — two-step parse →
  extract pipeline; defines the `.vim.json` boundary the watcher
  produces and the worker consumes.
- [ADR-0004](0004-ireco-config-schema.md) — `ireco.config.json` v1
  schema; this ADR adds two optional sections without bumping the
  version.
- `portunix-reco/plugin-worker.json`, `portunix-reco/plugin-watcher.json`
  — reference manifest shape.
- `portunix-reco/src/ptx_reco/watcher/{monitor,dispatcher,router,events,config}.py`
  — reference watcher implementation.
- `portunix-reco/src/ptx_reco/worker/task/{adapter,registry,errors}.py`
  — reference TaskAdapter / unified task contract.
- VIM Format Specification —
  [`../../../portunix-architecture/docs/architecture/components/plugin-vim/vim-format.md`](../../../portunix-architecture/docs/architecture/components/plugin-vim/vim-format.md)
  (sibling repo).
