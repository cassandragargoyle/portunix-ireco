# `ptx-ireco-watcher` — file-system watcher daemon

`ptx-ireco-watcher` is the long-running Portunix plugin binary that
monitors a directory for new PDFs and dispatches each detected file
through `ptx-ireco-worker`. It is the sibling daemon to the stateless
[`ptx-ireco-worker`](worker.md) — both binaries are registered with
Portunix through their own manifests (`plugin-worker.json` /
`plugin-watcher.json`).

The design is recorded in [ADR-0005](../adr/0005-ireco-plugin-split.md);
the runtime-only scope of this repository is recorded in
[ADR-0006](../adr/0006-runtime-only-scope.md). Authoring of
`ireco.config.json` (the file the watcher consumes) happens in
`portunix-reco-studio`, not here.

## Usage

```text
ptx-ireco-watcher [--config <ireco.config.json>]
                  [--watch-dir <dir> ...]
                  [-o <output_dir>]
                  [--models <models_path>]
                  [--backend local|cli|grpc]
                  [--workers N]
                  [--patterns "*.pdf,*.PDF"]
                  [--cooldown 1.0]
                  [--no-recursive]
                  [--events-log <file>]
                  [-v/--verbose]
                  [--version]
```

`ptx-ireco-watcher` blocks until interrupted (Ctrl-C). On shutdown it
stops the observer threads and waits for any in-flight pool tasks
to complete (`wait=True`) so no `.vim.json` is left half-written.

## Configuration precedence

For every flag, values are resolved in this order (highest wins):

1. Explicit CLI flag.
2. Value from `ireco.config.json` (the `watcher.*` / `models.*` / `io.*`
   blocks).
3. Built-in defaults.

The config file is located via:

1. Explicit `--config <path>`.
2. `./ireco.config.json` in the current working directory.
3. None — the watcher then requires `--watch-dir` and `-o` on the
   command line; otherwise it refuses to start.

CLI flags override the loaded config field-by-field. A `--watch-dir`
flag replaces the entire `watch_dirs` list (it is repeatable to watch
multiple roots).

## `ireco.config.json` sections consumed

The watcher reads three top-level sections:

```jsonc
{
  "version": 1,
  // ... doc_types, invoice ...

  "io": {
    "input_dir": "./scans",
    "output_dir": "./out"
  },

  "watcher": {            // optional, all fields have defaults
    "backend": "local",   // local | cli | grpc
    "workers": 1,         // integer >= 1
    "cooldown_seconds": 1.0,
    "patterns": ["*.pdf"],
    "recursive": true
  },

  "models": {             // optional; default root = cwd (models in ./models/invoice/)
    "path": "../ireco-models"  // root that contains models/invoice/
  }
}
```

| Key | Default | Notes |
|---|---|---|
| `io.input_dir` | required (or `--watch-dir`) | Source directory for new PDFs. |
| `io.output_dir` | required (or `-o`) | Destination for `.vim.json` outputs. |
| `watcher.backend` | `local` | Dispatch backend (see below). |
| `watcher.workers` | `1` | Pool size; `1` = sequential. |
| `watcher.cooldown_seconds` | `1.0` | Pause before dispatch to let writers finish. |
| `watcher.patterns` | `["*.pdf"]` | Case-sensitive globs (matched against file names). |
| `watcher.recursive` | `true` | Watch subdirectories. |
| `models.path` | cwd (models in `./models/invoice/`) | Root that contains `models/invoice/`. Absolute, or relative to the directory of the config file (worker and watcher alike). `--models` overrides it and is relative to cwd. |

Schema additions are **additive** — configs from earlier issues that
do not declare `watcher` or `models` keep validating against the v1
schema unchanged.

## Dispatch backends

| Backend | Trigger | Crash isolation | Latency |
|---------|---------|-----------------|---------|
| `local` | Direct in-process call to `ptx_ireco.worker.api.pipeline.run`. | None — a worker crash kills the watcher. | Lowest. |
| `cli`   | Subprocess: `<python> -m ptx_ireco.cli.worker_main run --file <pdf> -o <out>` (falls back to `shutil.which("ptx-ireco-worker")` if the interpreter is unavailable). | Per-file — a worker crash logs `scan.failed`; the watcher stays alive. | Higher (process spawn). |
| `grpc`  | Reserved. The watcher **fails fast at start time** with `--backend grpc is reserved and not yet implemented` so misconfigured deployments do not silently drop files. | n/a | n/a |

### `local` deployment recipe

Single-process, lowest overhead — appropriate for development and
small workloads.

```bash
ptx-ireco-watcher --config /etc/ireco/ireco.config.json
```

### `cli` deployment recipe

Per-file crash isolation. Recommended for production where a single
malformed PDF must not bring the daemon down.

```bash
ptx-ireco-watcher --config /etc/ireco/ireco.config.json \
                  --backend cli --workers 4
```

The watcher resolves the worker command deterministically as
`<sys.executable> -m ptx_ireco.cli.worker_main` so the spawned
subprocess shares the same virtual environment as the watcher
itself. If `sys.executable` is unavailable (rare; mostly frozen
builds), it falls back to `shutil.which("ptx-ireco-worker")`.

## Concurrency — `--workers N`

When `workers > 1`, files are submitted to a
`concurrent.futures.ProcessPoolExecutor`. The internal
`_worker_execute` function is module-level (importable) so it pickles
into child processes.

- A worker process crash returns
  `{"status": "error", "error": {"code": "WORKER_CRASH", ...}}`,
  which surfaces as `scan.failed`. The watcher process keeps running
  and continues accepting new files.
- On `Ctrl-C` the pool is shut down with `wait=True` so in-flight
  files complete cleanly before exit.

## Event stream

Three event types are emitted to every callback registered on
`monitor.router.on_event(...)`:

| Event | When | Metadata |
|---|---|---|
| `scan.detected` | As soon as the watcher sees a matching file (before cooldown). | (empty) |
| `scan.processed` | After a successful dispatch. | `result_keys`: list of keys in the result dict (e.g. `["vim_path", "entities", "recipient_id"]`). |
| `scan.failed` | On any dispatch failure. | `error`: human-readable message. `error.code` (optional): `DISPATCH_ERROR` or `WORKER_CRASH`. |

`--events-log <file>` writes one JSON object per line (UTF-8). The
log is **appended**, not truncated, so restarts preserve history.
Rotation is a deployment concern — wire `logrotate` to it if you
need it.

```json
{"event": "scan.detected",  "source": "/scans/scan.pdf", "ts": "2026-05-10T10:30:00Z", "metadata": {}}
{"event": "scan.processed", "source": "/scans/scan.pdf", "ts": "2026-05-10T10:30:01Z", "metadata": {"result_keys": ["vim_path", "entities", "recipient_id"]}}
```

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Clean shutdown (Ctrl-C). |
| `2` | Usage error — missing watch directory, missing output directory, unimplemented backend, etc. |
| `3` | Config declares `doc_types` that are not yet implemented (only `invoice` is). |
| `4` | Config file is missing or fails schema validation. |

## Limitations and open items

- **Doc types**: the watcher dispatches only PDFs whose declared
  `doc_types` is `["invoice"]`. Other types (`receipt`,
  `delivery_note`, `purchase_order`) are reserved per
  [ADR-0004](../adr/0004-ireco-config-schema.md) and rejected with
  exit code 3.
- **Pattern case sensitivity**: globs are matched verbatim against the
  file name. On case-sensitive filesystems, `*.pdf` does **not** match
  `scan.PDF`. To accept both, configure
  `"patterns": ["*.pdf", "*.PDF"]` or pass
  `--patterns "*.pdf,*.PDF"`.
- **gRPC** dispatch is reserved. The manifest declares
  `interface: cli,grpc` for forward compatibility; the actual
  server / client implementation will land in a follow-up issue.
- **Authoring `ireco.config.json`**: this repository is runtime-only
  per [ADR-0006](../adr/0006-runtime-only-scope.md). To create or
  edit the file, use `portunix-reco-studio`.
