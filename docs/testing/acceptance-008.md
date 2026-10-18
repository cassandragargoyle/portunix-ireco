# Acceptance Protocol — Issue #008

**Current STATUS**: **PASS** (2026-10-18) —
**Approval for merge**: **YES** — Tester: zdendaku (`/role tester`)

**Issue**: models.path default and example are wrong; worker and
watcher resolve a relative path differently
([`docs/issues/done/008-models-path-default-and-anchoring.md`](../issues/done/008-models-path-default-and-anchoring.md),
GitHub #8)
**Branch**: `fix/008-models-path-anchoring`
**Commits under test**:

- `aa36802` — fix(8): anchor relative models.path at the config file in worker and watcher
- `b8aafe0` — docs: Use zero-padded issue numbers in branch names
  (contributing docs only, no code; it is on the branch and merges with it)

**Tester**: zdendaku (QA / Test Engineer — generic)
**Date**: 2026-10-18
**Testing OS**: **Host — Ubuntu 26.04 (Linux 7.0.0-38-generic, amd64)**,
detected with `portunix system info`. Python 3.12.13, environment
managed by `uv`. The change is path resolution only (no new system
dependencies), so a host run is sufficient. Tesseract 5.5.0 and
`pdf2image` are installed, so no test is skipped.

**Note on independence**: the implementation and this test run were
done in the same assistant session (developer role, then tester role).
The baseline comparison against `main` (section C) was added so the
result does not depend on the implementer's own unit tests.

## Plan

1. Run the full automated suite with all prerequisites present.
2. Run the real CLIs (`ptx-ireco-worker run` / `batch`,
   `ptx-ireco-watcher` with `local` and `cli` backends) from a working
   directory that is **not** the directory of the config file.
3. Run the same scenarios against `main` (detached worktree,
   `PYTHONPATH=<worktree>/src`) to show that the bug exists there and
   is fixed on the branch.
4. Run the reproduction from the issue on both trees.
5. Check the documentation and the schema against acceptance
   criteria 2–4.

### Test layout

```text
<tmp>/run-<label>/
├── a/b/cfgdir/ireco.config.json     config; "models": {"path": "../models-root"}
├── a/b/models-root/models -> <repo>/models   (symlink)
├── other/                           cwd for all runs; in/a.pdf = flowii sample
└── auto/ireco.config.json           S7 only (auto-detected config)
```

The config is two levels deeper than `other/`, and the models root is
inside the test tree. In the first two attempts the relative path was
computed to the repository on another mount point; it climbed to `/`
and resolved to the same directory from any cwd, so `main` passed too.
That was a defect of the test layout, not of the product. The layout
above removes it.

## Cases

| ID | Given | When | Then |
| --- | --- | --- | --- |
| S1 | config in `a/b/cfgdir/` with `models.path: "../models-root"`, cwd `other/` | `worker --config ../a/b/cfgdir/ireco.config.json run --file in/a.pdf -o …` | models found under `a/b/models-root/`, exit 0 |
| S2 | as S1 | `worker … batch --dir in -o out/batch` | file status `success`, exit 0 |
| S3 | `models.path` absolute (repo root), cwd `other/` | `worker … run` | exit 0 |
| S4a | no `models` section, cwd = repo root | `worker --config <abs> run` | default root = cwd, exit 0 |
| S4b | no `models` section, cwd `other/` (no models there) | `worker … run` | clean error naming `other/models/invoice/…`, exit 2 |
| S5 | `models.path: "./does-not-exist"`, cwd `other/` | `worker … --models ../a/b/models-root run` | `--models` wins and is cwd-relative, exit 0 |
| S6 | as S5 without `--models` | `worker … run` | clean error naming `a/b/cfgdir/does-not-exist/…`, no traceback, exit 2 |
| S7 | `ireco.config.json` in cwd with relative `models.path` | `worker run` (no `--config`) | auto-detected config, exit 0 |
| S8-local | as S1 | `watcher --config … --backend local`, then drop a PDF | `scan.processed`, `a.vim.json` written |
| S8-cli | as S1 | `watcher --config … --backend cli`, then drop a PDF | `scan.processed`, `a.vim.json` written |

## Results

### A. Automated suite — PASS

```bash
uv run --extra dev pytest -q --strict-markers -rs
```

**312 passed, 0 skipped, 0 failed** (4.5 s). The issue-specific files
(`tests/unit/test_worker_models_path.py`,
`tests/unit/test_watcher_config.py`): 30 passed.

### B. CLI scenarios on the branch — PASS

| ID | Exit | Result |
| --- | --- | --- |
| S1 | 0 | template `11748862-…`, profile `invoice/profiles/cze/invoice-cze-2025-01-01.json` |
| S2 | 0 | `"status": "success"` |
| S3 | 0 | same template match |
| S4a | 0 | same template match |
| S4b | 2 | `No profiles directory for country 'CZE' at <tmp>/run-branch/other/models/invoice/profiles/cze` (expected) |
| S5 | 0 | same template match |
| S6 | 2 | `… at <tmp>/run-branch/a/b/cfgdir/does-not-exist/models/invoice/profiles/cze`, 0 tracebacks (expected) |
| S7 | 0 | same template match |
| S8-local | — | `scan.processed`, `a.vim.json` |
| S8-cli | — | `scan.processed`, `a.vim.json` |

The `.vim.json` outputs of S1 (relative), S3 (absolute) and S4a
(default) are byte-equal after JSON normalization.

### C. Baseline against `main` (`8f0d929`) — bug confirmed

| ID | Branch | `main` | Meaning |
| --- | --- | --- | --- |
| S1 | 0 | **2** | `main` resolves `../models-root` against cwd |
| S2 | 0 | **1** | `ExtractionError: … at ../models-root/models/invoice/profiles/cze` |
| S3, S4a, S5, S7 | 0 | 0 | unchanged behavior |
| S4b | 2 | 2 | unchanged default (cwd) |
| S6 | 2 (`a/b/cfgdir/does-not-exist/…`) | 2 (`does-not-exist/…`) | anchoring changed as intended |
| S8-local, S8-cli | processed | processed | watcher unchanged (it already passed an absolute `--models`) |

### D. Reproduction from the issue — PASS

Run with cwd `other/` and the config path `../cfgdir/ireco.config.json`:

| Call | `main` | Branch |
| --- | --- | --- |
| default root (`ModelPaths.default(...).templates`) | `other/models/invoice/templates` | `other/models/invoice/templates` |
| worker, `models.path: "./m"` | `other/m` | `cfgdir/m` |
| watcher, `models.path: "./m"` | `cfgdir/m` | `cfgdir/m` |

The worker and the watcher now give the same root.

### E. Acceptance criteria

| # | Criterion | Result |
| --- | --- | --- |
| 1 | One anchoring rule for worker and watcher; `--models` stays cwd-relative | **PASS** — shared `ptx_ireco.config.resolve_models_path`; sections C, D; S5 |
| 2 | `watcher.md` and the schema state the real default and the rule; example does not use `"./models"` | **PASS** — comment, example (`"../ireco-models"`) and table row corrected; schema descriptions corrected; schema is valid JSON; the `watcher.md` example validates with `load_config_dict` (with placeholder `doc_types` / `invoice`) |
| 3 | `MODELS_DEFAULT_PATH` removed or corrected | **PASS** — removed; no references left in `src/`, `tests/`, `docs/` |
| 4 | `worker.md` describes `models.path` without "reserved for issue 004" | **PASS** |
| 5 | Tests cover default root and relative `models.path` for worker and watcher | **PASS** — unit tests run from a cwd other than the config directory, plus CLI wiring for `run` and `batch` |

### F. Documentation lint — PASS (no new findings)

`markdownlint-cli2 docs/cli/watcher.md docs/cli/worker.md`: 31
findings on the branch, 31 on `main`. All are existing MD060 table-style
findings; none is in a changed line.

## Coverage

| Level | What | Where |
| --- | --- | --- |
| Unit | shared rule: missing / absolute / relative with and without config | `test_worker_models_path.py` |
| Unit | worker `_resolve_repo_root`: default, no config, absolute, relative, `--models` | `test_worker_models_path.py` |
| Unit | watcher: missing key, relative path independent of cwd | `test_watcher_config.py` |
| Unit | worker/watcher parity (3 relative forms) | `test_worker_models_path.py` |
| Integration | `run` and `batch` through `main()` with a stubbed pipeline | `test_worker_models_path.py` |
| E2E (manual) | real CLIs and watcher daemon, both backends, branch vs `main` | this protocol, sections B–C |

## Failure injection

- Nonexistent relative `models.path` (S6): clean `ExtractionError`
  message with the anchored path, exit 2, no traceback.
- Broken `models.path` overridden by `--models` (S5): the flag wins.
- No models in cwd and no `models` section (S4b): clean error, exit 2.

Ideas not run (low risk for this change): `models.path` as a symlink
loop, a config path given through a symlinked directory
(`Path.resolve()` follows the link, so the anchor is the real
directory), Windows drive-relative paths (`C:models`).

## CI notes

- The new tests need no optional prerequisites and no markers.
- A future e2e test for S1/S2 must keep the models root inside
  `tmp_path` (see "Test layout"). A relative path to the repository can
  climb to `/` and then pass on both the old and the new code.

## Findings

| ID | Severity | Finding | Action |
| --- | --- | --- | --- |
| F1 | Info | `docs/adr/0005-ireco-plugin-split.md:207-208` still shows `"path": "./models"` with the comment "root containing models/invoice/…", and lines 318-320 suggest the default "cwd `./models`". This is an accepted ADR and not one of the places listed in the issue. | Non-blocking. Optional: add a short note to the ADR that points to issue #8. |
| F2 | Info | Downstream: `portunix-reco-studio` keeps a byte-equal copy of `docs/schemas/ireco-config-1.0.json` and must take over the corrected descriptions after the merge (known from the issue). | Follow-up in `portunix-reco-studio`. |

## Final Decision

**STATUS**: **PASS**

**Approval for merge**: **YES**
**Date**: 2026-10-18
**Tester signature**: zdendaku (generic QA / Test Engineer role —
`/role tester`)
