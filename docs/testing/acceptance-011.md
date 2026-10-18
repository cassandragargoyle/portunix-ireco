# Acceptance Protocol — Issue #011

**Current STATUS**: **PASS** (2026-10-18) —
**Approval for merge**: **YES** — Tester: zdendaku (`/role tester`)

**Issue**: ADR 0005 shows the old models.path example and default
([`docs/issues/done/011-adr-0005-models-path-note.md`](../issues/done/011-adr-0005-models-path-note.md),
GitHub #11)
**Branch**: `fix/011-adr-0005-models-path-note`
**Commits under test**:

- `f08070a` — docs(11): note models.path changes from #8 in ADR 0005
- `9dd3802` — docs(11): note #8 in ADR index entry for 0005 (fix for F1)

**Tester**: zdendaku (QA / Test Engineer — generic)
**Date**: 2026-10-18
**Testing OS**: **Host — Ubuntu 26.04 (Linux 7.0.0-38-generic)**,
detected with `portunix system info`. Python 3.12.13 (`uv`),
pandoc 3.7.0.2. The change is documentation only; a host run is
sufficient.

**Note on independence**: the change and this test run were done in the
same assistant session (developer role, then tester role). Test T1
checks every statement of the new notes against the runtime, so the
result does not depend on the author's reading of the code.

## Plan

1. Check that the change touches only ADR 0005 (plus its index entry
   after F1) and does not rewrite the original decision text
   (criterion 4).
2. Check every statement in the new notes against the runtime
   behavior that #8 introduced.
3. Check links, markdownlint and the rendered structure (GFM).
4. Run the automated suite as a regression check.

## Cases

| ID | Given | When | Then |
| --- | --- | --- | --- |
| T0 | branch vs `main` | `git diff --numstat main...HEAD` and the removed lines | only ADR 0005 changes; the one removed line is a re-wrap, its text is kept |
| T1 | config in `cfgdir/`, cwd `other/` | resolve the root with the worker and the watcher | `"./models"` → `cfgdir/models/models/invoice/`; no key → cwd; relative path → `cfgdir/…` in both; relative `--models` → cwd; `resolve_models_path` exists |
| T2 | ADR 0005 on the branch | resolve every relative link | all targets exist |
| T3 | ADR 0005 on `main` and on the branch | markdownlint with the project rules | no new findings |
| T4 | the whole `docs/` tree | grep `"path": "./models"` outside `docs/issues/` | only the ADR example (now with a note) and the F1 text in `acceptance-008.md` |
| T5 | ADR 0005 on the branch | render with `pandoc -f gfm` | the note is one blockquote under the example; "Resolved in #8" is inside open question 2; the Status item keeps the ADR-0006 note and adds the #8 note |
| T6 | the branch | `uv run --extra dev pytest -q --strict-markers -rs` | all tests pass |

## Results

### T0. Scope — PASS

`21 insertions, 1 deletion` in `docs/adr/0005-ireco-plugin-split.md`
only. The removed line `per INT-037; the rest of this ADR is
unaffected)` is re-wrapped; the text "the rest of this ADR is
unaffected" is still there. The example value `"./models"` and the
original open-question text are unchanged.

### T1. Statements vs runtime — PASS

| Statement in the ADR | Runtime result |
| --- | --- |
| `"./models"` points to `./models/models/invoice/` | `cfgdir/models/models/invoice/templates` |
| without the key the root is cwd | `other` |
| a relative value is anchored at the config file (worker and watcher) | worker `cfgdir/m`, watcher `cfgdir/m` |
| a relative `--models` is resolved against cwd | `other/flag` |
| shared helper `ptx_ireco.config.resolve_models_path` | `ptx_ireco.config.loader.resolve_models_path`, exported from `ptx_ireco.config` |

### T2. Links — PASS

11 links, all relative, no missing target. The 3 new links to #8 point
to `../issues/done/008-models-path-default-and-anchoring.md`, which is
on `main`.

### T3. markdownlint — PASS

`.markdownlint-cli2.jsonc` ignores `docs/adr/**` even when the file is
named on the command line, so both versions were linted as copies
outside the repository with the project's `.markdownlint.jsonc`:
`main` 0 findings, branch 0 findings. No new line is longer than 77
characters.

### T4. Remaining `"./models"` examples — PASS

Only `docs/adr/0005-ireco-plugin-split.md:213` (the original example,
now followed by the note) and the F1 description in
`docs/testing/acceptance-008.md:178`.

### T5. Rendered structure — PASS

`pandoc -f gfm -t html`: 1 blockquote, which holds the note;
"Resolved in" is inside the list item "`models.path` resolution
precedence"; the Status item holds both the ADR-0006 and the #8 note;
3 rendered links to the #8 file.

### T6. Regression — PASS

**312 passed, 0 skipped, 0 failed**.

### Acceptance criteria

| # | Criterion | Result |
| --- | --- | --- |
| 1 | Status line has a "superseded in part" note with links to #8 and `docs/cli/watcher.md` | **PASS** — also links `docs/cli/worker.md` |
| 2 | The example is marked as outdated with the correct meaning | **PASS** — note under the code block (T1, T5) |
| 3 | The precedence text has the real default and the anchoring rule | **PASS** — "Resolved in #8" in open question 2 |
| 4 | The original decision text is not rewritten | **PASS** — T0 |

## Coverage

Documentation-only change: no code paths change. Every statement of the
new text is checked against the runtime (T1); structure, links and lint
are checked by T2, T3 and T5.

## CI notes

- `docs/adr/**` is excluded in `.markdownlint-cli2.jsonc`, so CI does not
  lint ADRs. Lint them as copies outside the repository (T3) when an ADR
  changes, or add a separate lint step for `docs/adr/`.

## Findings

| ID | Severity | Finding | Action |
| --- | --- | --- | --- |
| F1 | Low | `docs/adr/README.md:31` (the ADR index) still listed the 0005 status as "Accepted (wizard-placement statement superseded in part by ADR-0006)" without the new #8 note. The index and the ADR said different things. Not part of the acceptance criteria. | **Fixed** in `9dd3802`, re-tested below. |

### Re-test of F1 — PASS

- The status cell of 0005 in `docs/adr/README.md` now reads
  "Accepted (wizard-placement statement superseded in part by ADR-0006;
  `models.path` default and anchoring superseded in part by #8)"; only
  this cell changed
- The link target `../issues/done/008-models-path-default-and-anchoring.md`
  exists; `pandoc -f gfm` renders the cell with the code span and the link
- markdownlint (copy outside the ignore globs, project rules): `main` 5,
  branch 5 — the same existing table findings, none new

## Final Decision

**STATUS**: **PASS**

**Approval for merge**: **YES**
**Date**: 2026-10-18
**Tester signature**: zdendaku (generic QA / Test Engineer role —
`/role tester`)
