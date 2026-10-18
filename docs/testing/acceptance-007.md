# Acceptance Protocol — Issue #007

**Current STATUS**: **PASS** (Round 2, 2026-10-18) —
**Approval for merge**: **YES** — Tester: zdendaku (`/role tester`)

**Issue**: Per-page OCR fallback in `parse` step
**Branch**: `feature/issue-007-ocr-step`
**Commits under test**:

- `ed66e0b` — feat(007): add parse.ocr block to ireco.config.json schema
- `c9e07e9` — feat(007): wire OCR fallback into parse, CLI, and worker pipeline
- `c169f71` — test(007): unit + e2e coverage for OCR fallback with skip markers
- `5b7b768` — docs(007): document OCR fallback and pytest skip markers
- `1faccb9` — feat(007): propagate parse.ocr through watcher + ptx-ireco-worker (G1+G2)
- `520bbff` — test(007): cover watcher + worker OCR propagation (G1+G2)
- `7f04767` — docs(007): worker.md OCR section + plan-007 update for closed G1/G2
- Pending in tester branch state (uncommitted): TTF-font fixture fix in
  `tests/conftest.py`. Reason recorded under "Findings → F2".

**Plan**: [`docs/testing/plan-007.md`](plan-007.md) v1.1
**Companion (closed)**: `portunix-reco` INT-024 — `OcrExtractorPlugin`
**Tester**: zdendaku (QA / Test Engineer — generic)
**Date**: 2026-05-20
**Testing OS**: **Host — Linux 6.17.0-23-generic**, Python 3.12.13 in
`.venv` (uv-managed). Per `tester-linux` convention the
authoritative env is normally the container; the host run is
sufficient for this protocol because every prerequisite is locally
satisfied (Tesseract 5.5.0, Poppler 25.03, `pdf2image` 1.17.0,
`pytesseract` 0.3.13, Liberation Sans TTF) and the suite is fast
(~3s). A container re-run is recommended before main merge to
confirm cross-environment parity.

## Re-test — Round 2 (2026-10-18) — STATUS PASS

**Branch head under test**: `12244ae` (adds `1abb88b` F2 fix,
`d269143` round-1 protocol, `970f4b7` and `12244ae` chores — no
production code changes since round 1)
**Testing OS**: **Host — Linux 7.0.0-38-generic**, Python 3.12.13,
environment managed by `uv` (`uv run`, `.venv` not called directly)
**ptx-reco**: 0.3.10, editable from `../portunix-reco` via
`[tool.uv.sources]`

```text
Tesseract:   5.5.0 (ces, eng)
Poppler:     pdftoppm 26.01.0
pdf2image:   1.17.0
pytesseract: 0.3.13
Pillow:      12.2.0
pypdf:       6.21.1
```

### Automated suite

```bash
uv run --extra dev pytest -q --strict-markers -rs
```

**297 passed, 0 skipped, 0 failed** (4.6 s). The 7 `test_worker_cli.py`
cases skipped in round 1 now run and pass: `uv run` puts the
`ptx-ireco` / `ptx-ireco-worker` console scripts on `PATH`. The
round-1 skip was an environment issue, not a defect.

### Condition 1 — F2 fixture fix committed — MET

Committed as `1abb88b test(007): use TTF font for OCR fixtures`.
The suite passes on a clean `uv` sync.

### Condition 2 — F1 follow-up filed — MET

`portunix-reco` INT-025 ("OCR block content + provenance") is filed,
implemented and closed with acceptance STATUS PASS. Both parts of the
fix (`block_builder` fills `block.content`, `StructuralBlock.from_text_block`
copies `provenance`) are present in `ptx-reco` tags v0.3.4 through
v0.3.10. The ireco floor `ptx-reco>=0.3.4` therefore already includes
the fix — no dependency bump is needed.

Remaining action at closure (developer): link INT-025 from
`docs/issues/done/007-ocr-step.md` when the issue is archived.

### MS-3 re-run — image-only invoice, full pipeline — PASS

Fixture: `samples/invoice/flowii-FA_26050001.pdf` rasterized at
200 DPI into a 1-page image-only PDF (no text layer).

| Step | Command | Result |
|------|---------|--------|
| R2-1 | `ptx-ireco parse <img.pdf>` (no OCR) | `RuntimeError: ... no structural blocks` — pre-007 contract kept ✅ |
| R2-2 | `ptx-ireco parse --ocr --ocr-language ces+eng <img.pdf>` | 11 blocks, all `provenance.extractor == "ocr"`, **0 with empty content** ✅ (F1 closed) |
| R2-3 | `ptx-ireco run --ocr --ocr-language ces+eng <img.pdf>` | parse + extract succeed; `semantic.entities` produced (`invoice_number=26050001`, `issue_date=2026-05-09`, `due_date=2026-05-23`, `vat_id=CZ12345678`, `currency=CZK`) ✅ |
| R2-4 | `ptx-ireco run <img.pdf>` (no OCR) | `RuntimeError` as expected ✅ |
| R2-5 | `ptx-ireco-worker run --ocr --ocr-language ces+eng --file <img.pdf>` | exit 0, 11 blocks, 5 entities ✅ (worker / watcher CLI path) |
| R2-6 | `ptx-ireco run samples/invoice/flowii-FA_26050001.pdf` (text PDF) | succeeds, regression OK ✅ |

Per-page OCR metadata on R2-2:
`{"ran": true, "ink_ratio": 0.0209, "language": "ces+eng", "dpi": 300,
"engine": "tesseract", "engine_version": "5.5.0", "text_block_count": 11}`

D-1 / D-2 (provenance and text on OCR blocks), which were
CONDITIONAL in round 1, now pass.

### F3 — `pypdf` warning — not reproduced

With the `uv`-synced environment `pypdf` 6.21.1 is installed and the
metadata extractor warning does not appear. It stays non-blocking.

### Observation (not a 007 defect)

Some `issuer` fields are mis-assigned (e.g. `name` = "12300 Ráj Daňový
doklad"). The same kind of mis-assignment happens on the original
text-based PDF (`invoice_number` = "26050001Dříč"), so it is in the
flexylayout extract step, not in the OCR fallback. It is out of scope
for 007 and should be tracked separately if needed.

### Note for the developer

The first `uv run` created `uv.lock` (untracked). `portunix-reco`
commits its `uv.lock`; committing it here as well is the developer's
call.

---

# Round 1 (2026-05-20) — original record

## Test Summary

| Counter                          | Value          |
|----------------------------------|----------------|
| Automated test scenarios (run)   | 297            |
| Automated: passed                | 290            |
| Automated: failed                | 0              |
| Automated: skipped               | 7 (pre-existing worker-CLI e2e — `pip install -e .` needed) |
| Manual acceptance scenarios      | 5 (MS-1..MS-5) |
| Manual: passed                   | 4              |
| Manual: conditional              | 1 (MS-2 → re-cast as a hand-built mixed PDF substitute; see D below) |
| Manual: failed                   | 0              |
| Duration (full suite)            | 3.05 s         |

The +4 test increase from plan estimate (286 → 290) accounts for the
four OCR e2e cases (`tests/e2e/test_parse_ocr_e2e.py`) that
transitioned from skipped to passing once `pdf2image` was installed.

## Environment

```text
Host:        Linux 6.17.0-23-generic
Python:      3.12.13 (uv-managed .venv)
Tesseract:   5.5.0 (langs: ces, eng, osd; slk not installed — not used)
Poppler:     pdftoppm 25.03, pdfinfo 25.03
pdf2image:   1.17.0
pytesseract: 0.3.13
Pillow:      12.2.0
Font:        /usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf
qpdf:        not installed — MS-2 substituted with a PIL-only multi-page fixture
```

## Results by acceptance criterion

### A. Wiring — PASS

- [x] **A-1.** `OcrOptions()` defaults match the spec
  (`enabled=False`, `language="eng"`, `dpi=300`, `min_ink_ratio=0.005`,
  `mode="printed"`). Verified by
  `test_ocr_options_defaults_match_issue_007_spec`.
- [x] **A-2.** `parse_pdf(..., ocr=OcrOptions(enabled=False))` keeps
  the pre-007 contract. Manual confirmation against
  `samples/invoice/flowii-FA_26050001.pdf` produced byte-identical
  output to `ocr=None`.
- [x] **A-3.** Spy registry confirms `OcrExtractorPlugin` registers
  iff `ocr.enabled=True`; passing kwargs reach the plugin instance
  (`test_register_optional_extractors_*`).
- [x] **A-4.** Plugin import failure does not abort parse — verified
  indirectly by the registration's `try/except Exception` guard;
  manual rename of the plugin module reproduced "DEBUG log, parse
  continues" behaviour on the text-only fixture.

### B. Blank-page guard — PASS

- [x] **B-1.** 3-page synthetic fixture (blank / inked / blank): OCR
  contributes blocks only on page 2. Automated by
  `test_blank_page_is_skipped` after the F2 fixture fix.
- [x] **B-2 (manual).** Per-page `ocr` metadata recorded for every
  page. Quoted from the actual run:

  ```jsonc
  // doc.layers.physical.pages
  [
    {"page": 1, "ocr": {"ran": false, "skipped_reason": "blank_page", "ink_ratio": 0.0}},
    {"page": 2, "ocr": {"ran": true, "ink_ratio": 0.0249586..., "language": "eng",
                         "dpi": 300, "engine": "tesseract", "engine_version": "5.5.0",
                         "text_block_count": 2}},
    {"page": 3, "ocr": {"ran": false, "skipped_reason": "blank_page", "ink_ratio": 0.0}}
  ]
  ```

  Note: `skipped_reason: null` on the OCR-run page is pruned out by
  `_prune` in `parse.py:_vim_to_dict`; this is consistent with ireco's
  serializer style (drop `None` values). Spec intent preserved.
- [x] **B-3.** `min_ink_ratio=0.99` forces every page to skip (parse
  raises `RuntimeError` — no blocks). Automated by
  `test_min_ink_ratio_can_force_skip`. The opposite extreme
  (`min_ink_ratio=0.0`) was exercised manually and OCR ran on every
  page including the blank ones (zero blocks contributed but
  `ocr.ran=true` recorded).

### C. Text-page short-circuit — PASS

- [x] **C-1.** `flowii-FA_26050001.pdf` parsed with `ocr=None` vs.
  `OcrOptions(enabled=True)` produced identical structural-block
  counts (`test_text_only_pdf_unchanged_with_ocr_enabled`).
- [x] **C-2 (manual).** Per-page `ocr.skipped_reason="had_text"`
  observed when re-running with verbose logging on
  `flowii-FA_26050001.pdf`.

### D. Mixed-content PDF — **CONDITIONAL** (one downstream finding)

- [/] **D-1.** Mixed-PDF approximation: 3-page PIL fixture (blank /
  inked / blank). OCR fires only on page 2 — `text_block_count=2`
  ✅. **However, the structural-block payload omits provenance and
  text** (see Finding F1). Strictly per the acceptance bullet, the
  test fails the `provenance.extractor == "ocr"` requirement because
  `StructuralBlock.from_text_block` in `ptx_reco` does not carry
  `provenance` through.
- [/] **D-2.** Block ordering by `(page, bbox.y)` is preserved (only
  one page produces blocks in the substitute fixture). Strict
  multi-page mixed verification deferred until F1 is resolved.
- [x] **D-3.** Substitute fixture construction via PIL `save_all=True`
  works without `qpdf` for the per-page guard scenario;
  pdfplumber+image hybrid construction is documented as a TODO
  for after F1.

### E. CLI — PASS

- [x] **E-1.** `ptx-ireco parse --help` and `ptx-ireco run --help`
  list every `--ocr*` flag with documented defaults
  (`test_parse_subparser_advertises_ocr_flags`,
  `test_run_subparser_advertises_ocr_flags`).
- [x] **E-2 (manual).** Discoverability WARN emitted to stderr exactly
  as specified:
  ```text
  WARN: 2/3 pages have no extracted text. Re-run with --ocr to recover them.
  ```
  Captured against a synthetic 3-page fixture where pdfplumber found
  text on only one page.
- [x] **E-3 (manual).** `--ocr` on an image-only PDF produces
  `structural.blocks` with non-zero count (2 blocks on the inked
  page) — the WARN does not appear. Per E-3 the acceptance is
  satisfied for block count; the **content of those blocks** is the
  F1 concern, raised separately.
- [x] **E-4 (manual).** `--no-ocr` against an `ireco.config.json`
  with `parse.ocr.enabled: true` correctly disables OCR registration
  (verified by re-running on an image-only PDF and observing the
  pre-007 `RuntimeError`).
- [x] **E-5.** `--ocr-language eng+ces` reaches the plugin's
  `_language` attribute (`test_register_optional_extractors_propagates_options`).

### F. Watcher / config — PASS

- [x] **F-1, F-2, F-3.** Schema additions accepted; all 10 validator
  rejection paths covered by `test_config_validator.py::test_parse_ocr_*`.
- [x] **F-4 (manual, blocker closed by G1).** End-to-end watcher
  dispatch with `parse.ocr: {enabled: true}` in
  `ireco.config.json`:
  - `WatchConfig.from_dict` correctly populates `parse_ocr`
    (verified by direct unit + manual call).
  - `_dispatch_local` forwards `ocr=parse_ocr` to
    `worker_pipeline.run`; the produced `.vim.json` contains
    `structural.blocks` with `total=2` for the inked page and
    `pages_ocr` showing `ran=true` on that page. Acceptance
    "non-empty `structural.blocks`" is satisfied.
  - The full dispatch pipeline (`parse` + `extract`) then fails with
    `ExtractionError: Could not determine country` because the OCR-
    contributed blocks have empty `content` (Finding F1). Pure
    parse-step result is correct; downstream extract impact tracked
    under F1.
  - `_dispatch_cli` builds a subprocess command containing
    `--ocr --ocr-language eng --ocr-dpi 300 --ocr-min-ink-ratio 0.005
    --ocr-mode printed`. The subprocess `ptx-ireco-worker run --ocr`
    completes the parse half identically (Finding F1 reproduces).

### G. Tests — PASS

- [x] **G-1.** `--strict-markers` resolves `requires_tesseract` and
  `requires_pdf2image`; unknown markers would fail collection.
  Confirmed by running `pytest -q --strict-markers -rs`.
- [x] **G-2.** Skip-not-fail confirmed: prior to `pip install
  pdf2image`, the four e2e OCR tests skipped with the documented
  reason; none failed.
- [x] **G-3.** Host suite without `pdf2image`: 286 passed / 11
  skipped (recorded earlier under plan-007 §G-3).
- [x] **G-4.** Host suite with full prereqs:
  **290 passed / 7 skipped**. Matches plan-007 prediction (the
  4 OCR e2e tests transition to passing; the 7 pre-existing
  `worker-cli` skips are unrelated to issue 007 and require
  `pip install -e .` to flip — out of scope).

### H. Documentation — PASS

- [x] **H-1.** `docs/cli/parse.md` documents every `--ocr*` flag with
  defaults, prerequisites (Tesseract, `pdf2image`, Poppler) and
  examples.
- [x] **H-2.** `docs/pipeline/README.md` adds a one-line pointer to
  `docs/cli/parse.md` for the OCR fallback.
- [x] **H-3.** `README.md` (EN), `README.cs.md`, `README.sk.md` all
  contain a one-paragraph OCR mention with a CLI example.
- [x] **H-4.** `docs/contributing/TESTING_METHODOLOGY.md` documents
  the `requires_tesseract` / `requires_pdf2image` markers and the
  skip-not-fail contract.
- [x] **H-5 (extra).** `docs/cli/worker.md` got an "OCR flags (issue
  007)" section pointing at `parse.md` — added during G2 closure.

## Findings

| # | Severity | Location                                           | Description                                                                                                                                                                                                       | Linked case | Recommended action                                                                                                                                                                                                                          |
|---|----------|----------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| F1 | **Major** | `portunix-reco` (downstream of INT-024)            | OCR-built `StructuralBlock` entries in the emitted `.vim.json` have **empty `content`** and **no `provenance`**. Root cause is two-fold: (a) INT-024's `block_builder.build_blocks` populates `TextBlock.text_elements` but never calls `analyze_structure(...)` to derive `header`/`content`; (b) `StructuralBlock.from_text_block` in `ptx_reco.vim.model.vim_document` does not copy `block.provenance` into the structural layer. Net effect: step 2 (`extract`) cannot find country anchors on OCR-only documents — see MS-3. | D-1, F-4    | Open follow-up issue in `portunix-reco` (suggested ID **INT-025**): "Populate `TextBlock.content` / preserve `provenance` for OCR-derived blocks". Until then, ireco's OCR step recovers per-page presence and metadata but not extract-usable text. |
| F2 | **Minor** | `tests/conftest.py` (closed during this protocol)  | The session-scoped `ocr_pdf_fixtures` used PIL's default bitmap font, which produced an ink ratio of ≈ 0.002 on the inked page — below the production default `min_ink_ratio=0.005`. Result: two e2e tests failed with a misleading "no structural blocks" error. Fixed in-place by switching to a Liberation/DejaVu TTF at size 48; test suite now expects a TTF on the host (skip-not-fail when missing). | G-4         | Commit the fixture fix as part of the test layer (this protocol references the fix; bundling the commit is the developer's call).                                                                                                          |
| F3 | **Cosmetic** | `portunix-reco` execution engine                | At verbose log level, parse emits `WARNING: Extractor metadata failed: Metadata extraction requires 'pypdf': No module named 'pypdf'`. Unrelated to issue 007 — `pypdf` is an optional dependency for the metadata extractor. Surfaced because OCR's runtime now drags in the same execution-engine code path more often. | (none)      | Either pin `pypdf` as a transitive dep in `ptx_reco` or downgrade the message to DEBUG. Tracked as a paper-cut, not blocking.                                                                                                                |

## Final Decision

> **Superseded by Round 2 (2026-10-18): STATUS PASS, approval for
> merge YES.** Both conditions below are met; see the Round 2 section
> at the top. The text below is the original round-1 decision.

**STATUS**: **CONDITIONAL**

**Approval for merge**: **YES, with explicit conditions**:

1. The **F2 fixture fix** in `tests/conftest.py` must be committed on
   the feature branch before merge. Without it, the tester-protocol-
   reproducing run on a fresh checkout will fail two e2e tests at
   collection — defeating the suite's role as the merge gate.
2. **F1** is a downstream defect in `portunix-reco`, not ireco. Issue
   007 as written and implemented does not require F1 to be closed
   to merge — every acceptance bullet that is strictly testable
   passes. However, the value proposition of OCR collapses without
   F1: image-only PDFs become parseable but not extractable. A
   follow-up issue in `portunix-reco` (suggested **INT-025**) MUST be
   filed and linked from the closed `docs/issues/done/007-ocr-step.md`
   before this issue is archived.
3. **F3** is non-blocking and may be left to a later sweep.

**Date**: 2026-05-20
**Tester signature**: zdendaku (generic QA / Test Engineer role —
`/role tester`)

---

## Re-acceptance gate

If F1 is closed and the feature branch is re-pushed with no other
material changes, this protocol can be re-confirmed by running:

```bash
.venv/bin/python -m pytest -q --strict-markers -rs
```

and re-executing MS-3 (watcher e2e) — expected outcome flips from
"parse succeeds, extract fails on country detection" to "parse +
extract both succeed, structural.blocks carry provenance.extractor
== 'ocr' on image pages". The protocol's STATUS would then move
from CONDITIONAL to PASS without rewriting findings — only the
Status line at the top updates.
