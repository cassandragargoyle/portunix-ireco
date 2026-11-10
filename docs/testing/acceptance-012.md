# Acceptance Protocol — Issue #012

**Current STATUS**: **PASS** (2026-11-10) —
**Approval for merge**: **YES** — Tester: zdendaku (`/role tester`)

**Issue**: Python minimum 3.11 does not match ptx-reco (requires 3.12)
([`docs/issues/012-python-312-minimum.md`](../issues/012-python-312-minimum.md),
GitHub #12)
**Branch**: `fix/012-python-312-minimum`
**Commits under test**:

- `7a6028c` — fix(012): Raise the Python minimum to 3.12 as ptx-reco

**Tester**: zdendaku (QA / Test Engineer — generic)
**Date**: 2026-11-10
**Testing OS**: **Host — Ubuntu 26.04 (Linux 7.0.0-43-generic)**,
detected with `portunix system info`. Python 3.12.13 (project `.venv`),
3.13.13 and 3.11.15 (isolated environments, `uv`). The change is
metadata and configuration only; a host run is sufficient.

**Note on independence**: the change and this test run were done in the
same assistant session (developer role, then tester role). The tests
check the behavior of `uv` and the test suite directly, so the result
does not depend on the author's reading of the change.

## Plan

1. Check the scope of the change against the issue table.
2. Check that the lock file is consistent and has no Python 3.11 split
   (criterion 1).
3. Search for remaining 3.11 minimums outside `docs/issues/done/`
   (criterion 2).
4. Check that Python 3.11 is refused and Python 3.12 / 3.13 work.
5. Run the automated suite and compare black / mypy with the old
   target versions (criterion 3, regression).

## Cases

| ID | Given | When | Then |
| --- | --- | --- | --- |
| T0 | branch vs `main` | `git diff --stat main...HEAD` | only the files from the issue table change |
| T1 | the branch | `uv lock --check` | the lock is up to date |
| T2 | `uv.lock` | search for `python_full_version < '3.12'`, `resolution-markers`, `tomli` | no Python 3.11 split remains |
| T3 | the repository without `uv.lock` and `docs/issues/done/` | `git grep -nE '3\.11\|py311\|cp311'` | no file declares 3.11 as the minimum |
| T4 | `plugin-worker.json`, `plugin-watcher.json` | parse as JSON and read `python_min_version` | valid JSON, value `3.12` |
| T5 | Python 3.11.15, isolated environment | `uv sync --python 3.11 --frozen` | refused with the `requires-python` message |
| T6 | Python 3.12.13, committed lock | `uv run --frozen pytest -q` | all tests pass, none skipped |
| T7 | Python 3.13.13, isolated environment | `uv run --python 3.13 --frozen --extra dev pytest -q` | all tests pass |
| T8 | the branch | black and mypy with the old (3.11) and new (3.12) targets | the same result for both targets |

## Results

### T0. Scope — PASS

`CONTRIBUTING.md`, `plugin-watcher.json`, `plugin-worker.json`,
`pyproject.toml`, `uv.lock` and the new issue file. This matches the
issue table.

### T1. Lock consistency — PASS

`uv lock --check`: `Resolved 46 packages`, exit code 0.

### T2. No Python 3.11 split — PASS

`requires-python = ">=3.12"`. The `resolution-markers` blocks and
`tomli` were removed. The remaining `3.11` matches in `uv.lock` are the
`pycparser` 3.11 package version and wheel hashes, not Python markers.

### T3. Remaining 3.11 minimums — PASS (see O1)

Matches only in the issue file `012` (describes the problem) and in
two usage comments in `scripts/setup-venv.sh` (see O1). No file
declares 3.11 as the minimum.

### T4. Plugin manifests — PASS

Both files are valid JSON with `python_min_version` `3.12`.

### T5. Python 3.11 refused — PASS

```text
error: The requested interpreter resolved to Python 3.11.15, which is
incompatible with the project's Python requirement: `>=3.12`
(from `project.requires-python`)
```

### T6. Test suite on Python 3.12 — PASS

**312 passed, 0 skipped, 0 failed** (5.88 s), with the committed lock
(`--frozen`).

### T7. Test suite on Python 3.13 — PASS

**312 passed** (6.03 s) in an isolated environment.

### T8. black / mypy regression — PASS

| Tool | Target 3.11 | Target 3.12 |
| --- | --- | --- |
| `black --check src tests` | 39 to reformat, 40 unchanged | the same 39 files |
| `mypy src` (strict) | 19 errors in 10 files | 19 errors in 10 files |

These findings already exist and the change of the target version does not
cause them.

### Acceptance criteria

| # | Criterion | Result |
| --- | --- | --- |
| 1 | `uv lock` succeeds | **PASS** — T1, T2 |
| 2 | No file outside `docs/issues/done/` declares Python 3.11 as the minimum | **PASS** — T3, T4 |
| 3 | All tests pass | **PASS** — T6, T7 |

## Coverage

Configuration-only change: no code paths change. The new minimum is
checked from both sides: refusal on 3.11 (T5) and full test runs on
3.12 and 3.13 (T6, T7).

## CI notes

- `ptx-reco` is an editable path source (`../portunix-reco`), so
  `uv.lock` depends on the working tree of the sibling repository.
  During this test run the sibling was on another branch with an
  uncommitted `pyproject.toml` change (adds `certifi`). A plain
  `uv run` then rewrote `uv.lock` (adds `certifi`). The tester restored
  the lock with `git checkout -- uv.lock` and repeated T6 with
  `--frozen`. Use `--frozen` (or `--locked`) in test runs, and make
  sure the sibling is at a committed state before `uv lock`.
- `black` (39 files) and `mypy --strict` (19 errors) are not clean on
  `main` either. CI cannot use them as gates until this is fixed.

## Findings

| ID | Severity | Finding | Action |
| --- | --- | --- | --- |
| O1 | Info | `scripts/setup-venv.sh:7-8`: the usage examples use `./setup-venv.sh 3.11`. With the new minimum, this example fails (T5). The text is a usage example, not a minimum declaration, so criterion 2 is not affected. | Recommended: change the examples to `3.12`. Not blocking. |
| O2 | Info | Lock drift from the editable sibling source (see CI notes). This comes from the environment, not from the change. | No action for #12. |

## Final Decision

**STATUS**: **PASS**

**Approval for merge**: **YES**
**Date**: 2026-11-10
**Tester signature**: zdendaku (generic QA / Test Engineer role —
`/role tester`)
