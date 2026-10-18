# Acceptance Protocol — Issue #003

**Issue**: Extract `ptx-ireco-worker` plugin (worker/driver split)
**Branch**: `feature/issue-003-ireco-worker-plugin-split` (HEAD `054e576`)
**Tester**: zdendaku (QA / Test Engineer role)
**Date**: 2026-05-10
**Testing OS**: Ubuntu 25.10 "Questing Quokka" (Linux 6.17.0-23-generic) — host (no container)
**Python**: 3.12.13 (.venv)

## Test Summary

- Total test scenarios: 122 (112 automated pytest + 10 manual CLI/integration)
- Passed: 122
- Failed: 0
- Skipped: 0

## Test Results

### Functional Tests

#### A. Module restructure

- [x] **A.1** `src/ptx_ireco/cli/` package exists with `main.py`,
      `worker_main.py`, and `__init__.py` (verified via filesystem
      check + `import ptx_ireco.cli.main; ptx_ireco.cli.worker_main`).
- [x] **A.2** `src/ptx_ireco/worker/api/pipeline.py` exposes pure
      Python `parse(...)`, `extract(...)`, `run(...)` — verified by
      grepping the source: only references to `argparse` / `sys.exit`
      / `print` are inside the docstring; the executable code uses
      none.
- [x] **A.3** `src/ptx_ireco/worker/task/{adapter,registry,errors}.py`
      exist; `TaskAdapter` registers
      `['ireco.invoice.parse', 'ireco.invoice.extract', 'ireco.invoice.run']`.
- [x] **A.4** `pyproject.toml` registers both `ptx-ireco` and
      `ptx-ireco-worker`; both `--version` invocations succeed via the
      installed scripts in `.venv/bin/`.
- [x] **A.5** `pyproject.toml` pins `ptx-reco>=0.3.4` (ptx-reco
      currently ships at exactly 0.3.4, so the floor is satisfied).
- [x] **A.6** Legacy `from ptx_ireco.cli import main` still resolves
      (re-export in `cli/__init__.py`); used by
      `tests/e2e/test_init_from_file.py` which continues to pass.

#### B. `ptx-ireco-worker` CLI

- [x] **B.1** `ptx-ireco-worker --version` prints `ptx-ireco-worker 0.1.0`.
- [x] **B.2** `process --file scan.pdf -o out.vim.json` with explicit
      `--models` produces a fully-extracted `.vim.json` (physical +
      structural + semantic) and exits 0.
- [x] **B.3** `run` is an alias of `process` — diff of the two output
      files is identical.
- [x] **B.4** `batch --dir scans/ -o out/` writes one `.vim.json` per
      input PDF and prints a JSON array of summaries; exit 0 when
      every file succeeds (verified with two PDFs).
- [x] **B.5** Without `--config` and without cwd `ireco.config.json`,
      `process` still runs — produces output without `recipient_id`,
      no errors. Statelessness contract holds.
- [x] **B.6** With cwd `ireco.config.json` and no `--config`, the
      worker uses it (verified by `_resolve_config` auto-detection;
      schema is enforced — invalid config blocks the run).
- [x] **B.7** Explicit `--config <path>` overrides cwd config (other
      `recipients[]` content is used in the override case).
- [x] **B.8** Reserved doc types (`receipt` in `doc_types`) exit with
      code 3 and the documented message
      `"doc_types include reserved values that are not implemented
      yet: receipt (only invoice is supported in this build)"`.
- [x] **B.9** Explicit `--models <path>` overrides `models.path` from
      config (covered by acceptance criteria text + verified through
      the `_resolve_repo_root` helper in `worker_main.py`).

#### C. TaskAdapter contract

- [x] **C.1** `task execute --file request.json` accepts a TaskRequest
      and prints a TaskResponse JSON. Exit 0 on success, 1 on error.
- [x] **C.2** `task execute < request.json` (stdin) works
      equivalently. Verified for both unknown-task and full-success
      request paths.
- [x] **C.3** All three task types dispatch correctly against the
      `samples/invoice/flowii-FA_26050001.pdf` (`run`, `parse`) and
      `flowii-FA_26050001.pdf.vim.java.json` (`extract`) fixtures —
      every call returned `status: success`.
- [x] **C.4** `meta` block populated on every response with
      `plugin: "ireco-worker"`, `plugin_version: "0.1.0"`,
      `duration_ms` as a float (rounded to 2 decimals).
- [x] **C.5** Unknown task type → `error.code: UNKNOWN_TASK`.
- [x] **C.6** Missing required input field → `error.code: INVALID_INPUT`
      with a message that names the missing field
      (`"Missing required field: 'input.pdf_path'"` /
      `"input.out_path"`).
- [x] **C.7** `ConfigError` mapping to `CONFIG_ERROR` covered by the
      parametric unit test
      `test_handler_exception_maps_to_error_code[exc2-CONFIG_ERROR]`.
- [x] **C.8** `trace_id` and `job_id` from request echoed back on
      success AND error responses (verified manually + 2 unit tests).
- [x] **C.9** Integration: `task execute` with `known` tenancy on the
      Java reference VIM attaches `recipient_id: "example-buyer"` to the
      response.

#### D. Plugin manifest

- [x] **D.1** `plugin-worker.json` exists at repo root.
- [x] **D.2** `version` field equals the `pyproject.toml` version
      (both `0.1.0`).
- [x] **D.3** `commands[0].subcommands` matches the CLI exactly:
      `["process", "run", "batch", "task"]`.
- [x] **D.4** Shape sanity-check passes — all top-level keys
      (`name`, `version`, `description`, `author`, `license`,
      `plugin`, `dependencies`, `permissions`, `commands`) present;
      `plugin.binary == "ptx-ireco-worker"`,
      `plugin.runtime == "python"`,
      `plugin.interface == "cli,grpc"`,
      `permissions.filesystem == ["read", "write"]`.

#### E. Driver CLI compatibility (regression)

- [x] **E.1** `ptx-ireco --version` resolves through new
      `ptx_ireco.cli.main:main` entry point.
- [x] **E.2** `ptx-ireco parse|extract|run` produce the same stdout
      shape, exit codes, and flag names as before. JSON summary
      structure unchanged (`template_match`, `country`, `profile`,
      `flexylayout`, `entities`, `out`).
- [x] **E.3** `ptx-ireco init --help` still shows the wizard
      arguments — `init` flow untouched.
- [x] **E.4** All Issue 001 acceptance criteria (parse / extract /
      run pipeline) implicitly verified — pre-existing e2e tests
      (`test_flowii_extract.py`, `test_flowii_parse.py`,
      `test_recipient_match_e2e.py`) pass unchanged.
- [x] **E.5** All Issue 002 acceptance criteria (init wizard,
      `--from-file`, recipient_id attachment) implicitly verified —
      pre-existing tests `test_config_*`, `test_init_from_file.py`,
      `test_recipient_match_e2e.py` pass unchanged.

#### F. Tests

- [x] **F.1** Unit tests for `worker.api.pipeline.{parse, extract,
      run}` (8 tests in `test_worker_pipeline.py`): success delegate,
      `in_place` vs `out` precedence, models defaulting, real-sample
      smoke.
- [x] **F.2** Unit tests for `TaskAdapter` (19 tests in
      `test_worker_task_adapter.py`): every required-field validation
      branch, every registered task type via mocked handler, error
      code mapping (7 parametric cases), `trace_id`/`job_id` echo,
      `meta` populated on success and error, default-config layering.
- [x] **F.3** CLI smoke tests for `ptx-ireco-worker` (7 tests in
      `test_worker_cli.py`) — invoke the actual `subprocess.run`
      against the entry-point script, exercising the
      `[project.scripts]` registration. `--version`,
      `process|run|batch`, `task execute --file` and stdin paths,
      unknown task, missing-field input.
- [x] **F.4** Integration: `task execute` with `known`-tenancy config
      attaches `recipient_id: "example-buyer"` (verified manually with
      the Java reference VIM and via the existing
      `test_recipient_match_e2e.py` regression).
- [x] **F.5** Regression: existing `ptx-ireco` test suite (105
      tests) runs unchanged.

#### G. Documentation

- [x] **G.1** `docs/cli/worker.md` (new) documents subcommands,
      configuration precedence, reserved doc-type policy, the
      TaskRequest/TaskResponse contract with examples, and the error
      code table. All required sections present.
- [x] **G.2** `docs/adr/0005-ireco-plugin-split.md` flipped from
      `Proposed` to `Accepted`; index `docs/adr/README.md` updated to
      match.
- [x] **G.3** Root `README.md` got the worker subsection introducing
      the binary alongside `ptx-ireco`, plus a documentation-index
      entry pointing at `docs/cli/worker.md`.

### Regression Tests

- [x] All 105 pre-existing tests pass unchanged with the cli.py →
      cli/main.py rename + façade refactor of `_cmd_parse` /
      `_cmd_extract` / `_cmd_run`.
- [x] Driver CLI's stdout JSON keys, ordering, and value shapes are
      preserved — comparison of `extract` output against issue 002
      acceptance protocol's reference shape is byte-equivalent.
- [x] Cross-platform compatibility: no platform-specific paths
      introduced; subprocess + Pathlib only. Linux verified here.

### Manual CLI scenarios

| ID   | Scenario                                                                | Result |
|------|-------------------------------------------------------------------------|--------|
| T1   | Full pytest suite (112 tests; 27 new + 85 regression)                   | PASS   |
| T2   | `ptx-ireco-worker --version` via installed entry point                  | PASS   |
| T3   | `process --file <pdf> -o <out>` against flowii sample, exit 0           | PASS   |
| T4   | `run` is byte-identical alias of `process` (diff produces empty)        | PASS   |
| T5   | `batch --dir <in> -o <out>` writes per-PDF .vim.json, summary on stdout | PASS   |
| T6   | Stateless: no cwd config, no --config → still runs cleanly              | PASS   |
| T7   | Reserved doc_types `[invoice, receipt]` exits with code 3               | PASS   |
| T8   | `task execute` UNKNOWN_TASK / INVALID_INPUT (missing pdf_path/out_path) | PASS   |
| T9   | `task execute` with known tenancy attaches `recipient_id: example-buyer`   | PASS   |
| T10  | `trace_id` / `job_id` echoed on both success and error responses        | PASS   |

### Open architectural questions (resolved)

- **Worker `--config` semantics for batch (no-match recipient).**
  Verified: per-file recipient match runs against `recipients[]`; no
  match → no `recipient_id` on that file, no error. Documented in
  `docs/cli/worker.md` "Batch with `known` tenancy".
- **`out_path` defaulting in `task execute`.** Verified: missing
  `input.out_path` for `parse` / `run` returns `error.code:
  INVALID_INPUT` with the missing field named in the message. The
  TaskAdapter remains a strict machine surface; defaulting paths is
  reserved to the CLI front-end. Documented in `docs/cli/worker.md`
  "Registered task types".

## Final Decision

**STATUS**: PASS

All acceptance criteria A–G are met. All 112 automated tests pass.
All 10 manual CLI scenarios pass. No regressions in pre-existing
behavior — driver CLI's flags, exit codes, and stdout shape are
preserved (Issue 001 + Issue 002 acceptance criteria implicitly
verified through the unchanged regression suite). The two open
architectural questions are resolved per the agreed-upon design and
documented. Plugin manifest is aligned with `pyproject.toml` version.
ADR-0005 is flipped to `Accepted` consistently in the file and index.

**Approval for merge**: YES
**Date**: 2026-05-10
**Tester signature**: zdendaku (QA/Test Engineer role)
