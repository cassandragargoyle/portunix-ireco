# Test Plan — Issue #007 (Per-page OCR fallback in `parse` step)

**Issue**: [007 — Per-page OCR fallback in `parse` step](../issues/done/007-ocr-step.md)
**Branch under test**: `feature/issue-007-ocr-step`
**Commits**: `ed66e0b` (schema) · `c9e07e9` (code) · `c169f71` (tests) · `5b7b768` (docs)
**Companion (closed)**: `portunix-reco` INT-024 — `OcrExtractorPlugin`
**Tester role**: QA / Test Engineer (generic).
For platform-specific execution: switch to `tester-linux` or
`tester-windows` and re-anchor the OS-specific sections.

---

## Plan

### Scope

This plan covers every acceptance criterion (A–H) listed in
[`007-ocr-step.md`](../issues/done/007-ocr-step.md). Each
acceptance bullet maps to at least one Given/When/Then case in the
Cases section. Where automated coverage already exists in the
branch, the case is linked to the test file + name; the rest must
be exercised manually during acceptance execution.

### Environment

Two reference environments are used; the protocol must run at least
one and call out which.

| Tier        | OS / Runtime                                  | Use                                     |
|-------------|-----------------------------------------------|-----------------------------------------|
| Host        | Linux 6.17.0-23 (current dev host), Python 3.12 in `.venv` | Fast feedback; subset of cases.        |
| Container   | `python:3.12-slim` under Podman (per `acceptance-006.md` pattern) | Authoritative test env for the protocol. |

### Prerequisites (per acceptance criterion G)

The OCR plugin from `ptx_reco` (INT-024) loads three host-provided
pieces lazily. Tester MUST install all three before claiming PASS;
otherwise the four `e2e/test_parse_ocr_e2e.py` tests skip and B/C/D
cannot be exercised.

```bash
# Debian/Ubuntu host
sudo apt install -y tesseract-ocr tesseract-ocr-ces tesseract-ocr-slk poppler-utils
# Project venv
.venv/bin/pip install pdf2image
# Re-confirm
.venv/bin/python -c "import pdf2image, pytesseract; print('ok')"
tesseract --version | head -1
tesseract --list-langs | grep -E '^(ces|slk|eng)$'
```

### Risks / known gaps (must read before execution)

The tester role inspects the implementation **before** writing the
plan; two real gaps were found that the developer commits do not
close. They are documented here so the acceptance run is not
surprised by them — and so the protocol can be honest about
CONDITIONAL vs PASS.

#### G1 — Watcher does not propagate `parse.ocr`

`src/ptx_ireco/watcher/dispatcher.py:75-81` calls
`worker_pipeline.run(file_path, out_path, models=…, options=…,
verbose=False)` **without** the new `ocr=` kwarg. The schema
validates `parse.ocr`, but the value is discarded between config
loader and dispatcher. Acceptance F's last bullet —

> Watcher run with `watcher`/`parse.ocr.enabled: true` produces a
> `.vim.json` whose page 1 has non-empty `structural.blocks`.

— is therefore **expected to FAIL** as the branch stands. Expected
remediation:

1. Extend `WatchConfig` (`src/ptx_ireco/watcher/config.py`) to carry
   `parse_ocr: OcrOptions | None`, loaded via
   `OcrOptions.from_config_dict(cfg)`.
2. Pass it from `_dispatch_local` to `worker_pipeline.run(..., ocr=…)`.
3. For the `cli` backend, plumb `--ocr*` flags through `worker_main.py`
   into the subprocess command line. **`ptx-ireco-worker` does not
   currently expose any `--ocr*` flag** (G2 below).

Until G1 is closed, the protocol will be CONDITIONAL with F listed
as the blocking finding.

#### G2 — `ptx-ireco-worker` CLI has no `--ocr*` flags

The driver CLI `ptx-ireco` got `--ocr*` (acceptance E). The worker
CLI `ptx-ireco-worker run --file …` did not. Since the watcher's
`cli` backend dispatches via `ptx-ireco-worker run`, even after
fixing G1 the `cli` backend would still bypass OCR. Issue 007's
acceptance F covers the watcher end-to-end but does not specify
which backend, so this is a follow-up rather than a blocker — but
worth flagging now.

#### G3 — Mixed-content fixture is synthetic

Acceptance D names `tests/fixtures/parse/ocr/mixed.pdf` with "page 0
text, page 1 scan". The branch's fixture pipeline uses PIL alone,
which cannot stamp a text layer on one page and a raster on another
within the same PDF. The branch substitutes `blank_and_content` (3
pages: blank / inked / blank), which exercises the **per-page guard
logic** but not the "text-blocks present on one page + OCR fills the
other" merge path. To close D fully, the tester must construct a
mixed PDF manually (`qpdf --pages text.pdf 1 -- scan.pdf 1 --
mixed.pdf` or equivalent) and run a manual scenario; see
case **D-3** below.

### Out of scope for this plan

- Handwritten OCR (issue 007 explicitly defers).
- Checkbox detection.
- Per-region OCR for hybrid pages.
- `ptx-reco-studio` config authoring of `parse.ocr` (no studio
  involvement in issue 007).

---

## Cases

Format: Given / When / Then. Test ID encodes acceptance section + index.

> "Automated by:" lists the existing test that already exercises the
> case; tests without an "Automated by:" line are manual scenarios
> the tester executes during acceptance.

### A — Wiring

**A-1. `OcrOptions` dataclass matches the spec.**
- Given: a fresh import of `ptx_ireco.pipeline.parse`.
- When: `OcrOptions()` is constructed without arguments.
- Then: the instance equals
  `OcrOptions(enabled=False, language="eng", dpi=300,
  min_ink_ratio=0.005, mode="printed")`.
- Automated by: `tests/unit/test_parse_ocr.py::test_ocr_options_defaults_match_issue_007_spec`.

**A-2. `parse_pdf(ocr=OcrOptions(enabled=False))` is regression-safe.**
- Given: the existing text-only fixture
  `samples/invoice/flowii-FA_26050001.pdf`.
- When: parsed with `ocr=None` and `ocr=OcrOptions(enabled=False)`.
- Then: both invocations produce the same `.vim.json` content
  (structural blocks identical; no `ocr` metadata added).
- Automated by: `tests/e2e/test_parse_ocr_e2e.py::test_text_only_pdf_unchanged_with_ocr_enabled`
  (covers the slightly stronger case `enabled=True` short-circuit).
- Manual confirmation:
  ```bash
  .venv/bin/python -m ptx_ireco.cli.main parse \
      samples/invoice/flowii-FA_26050001.pdf -o /tmp/off.vim.json
  .venv/bin/python -c "
  from ptx_ireco.pipeline.parse import parse_pdf_to_file, OcrOptions
  parse_pdf_to_file('samples/invoice/flowii-FA_26050001.pdf',
                    '/tmp/disabled.vim.json',
                    ocr=OcrOptions(enabled=False))
  "
  diff /tmp/off.vim.json /tmp/disabled.vim.json && echo IDENTICAL
  ```

**A-3. OCR plugin is registered only when enabled.**
- Given: a spy `PluginRegistry`.
- When: `_try_register_optional_extractors(registry, ocr=…)` is
  invoked with `ocr=None`, `OcrOptions(enabled=False)`, and
  `OcrOptions(enabled=True)`.
- Then: the registered plugin list contains `OcrExtractorPlugin`
  only in the third case, and the plugin instance carries the
  kwargs verbatim.
- Automated by: `tests/unit/test_parse_ocr.py::test_register_optional_extractors_*`.

**A-4. OCR plugin import failure does not abort parse.**
- Given: `ocr=OcrOptions(enabled=True)` and a runtime where
  `ptx_reco.vim.extractors.ocr` cannot be imported (e.g.
  uninstalled `ptx_reco`).
- When: `parse_pdf(text_pdf, ocr=…)` is invoked.
- Then: the parse completes; a `DEBUG` log line records the
  registration skip; no exception escapes.
- Automated by: the registration loop already wraps every plugin
  import in `try/except Exception` (parse.py); covered indirectly
  by A-3 via the spy. Manual test plan: temporarily rename
  `ptx_reco/vim/extractors/ocr/` and re-run `parse` on
  `flowii-FA_26050001.pdf`; expect success.

### B — Blank-page guard

**B-1. Per-page guard with default threshold.**
- Given: the 3-page synthetic fixture from
  `tests.conftest.ocr_pdf_fixtures["blank_and_content"]` (pages 0/2
  blank, page 1 inked).
- When: `parse_pdf_to_file(pdf, out, ocr=OcrOptions(enabled=True))`.
- Then: only page 2 (the inked page) carries OCR-derived structural
  blocks; pages 1 and 3 have none.
- Automated by: `tests/e2e/test_parse_ocr_e2e.py::test_blank_page_is_skipped`.

**B-2. Per-page metadata is recorded for every page.**
- Given: the same 3-page fixture.
- When: parse runs with `OcrOptions(enabled=True)`.
- Then: `doc["layers"]["physical"]["pages"][i]["ocr"]` is present
  for every page; pages 0/2 record `ran=false,
  skipped_reason="blank_page", ink_ratio < 0.005`; page 1 records
  `ran=true, skipped_reason=null, ink_ratio >= 0.005,
  text_block_count > 0, engine="tesseract", engine_version=…`.
- Automated by: covered indirectly via `test_blank_page_is_skipped`;
  the explicit metadata assertion is **a manual scenario**
  (acceptance protocol must inspect the JSON and quote it).

**B-3. Threshold is honored at extremes.**
- Given: the inked single-page fixture
  `ocr_pdf_fixtures["image_only_invoice"]`.
- When: parsed with `min_ink_ratio=0.99` (forces skip).
- Then: parse raises `RuntimeError` (no structural blocks).
- And when: parsed with `min_ink_ratio=0.0` (forces OCR on every page).
- Then: parse succeeds with OCR blocks even on the inked page.
- Automated by: `tests/e2e/test_parse_ocr_e2e.py::test_min_ink_ratio_can_force_skip`
  (force-skip direction); the `0.0` direction is a **manual scenario**.

### C — Text-page short-circuit

**C-1. Text-only PDF unchanged when OCR is enabled.**
- Given: `samples/invoice/flowii-FA_26050001.pdf` (text-extractable).
- When: parsed with `OcrOptions(enabled=True)` and
  `OcrOptions(enabled=False)`.
- Then: `structural.blocks` counts are identical; no OCR blocks
  contributed.
- Automated by: `tests/e2e/test_parse_ocr_e2e.py::test_text_only_pdf_unchanged_with_ocr_enabled`.

**C-2. Each page's `ocr` entry records `had_text`.**
- Given: parse of `flowii-FA_26050001.pdf` with OCR enabled.
- When: inspecting `layers.physical.pages[*].ocr`.
- Then: every page has `ran=false, skipped_reason="had_text",
  ink_ratio=null`.
- Automated by: not yet. **Manual scenario** for the protocol.

### D — Mixed-content PDF

**D-1. Mixed PDF: OCR fires only on the image page.**
- Given: a hand-crafted mixed PDF (page 0 text-extractable, page 1
  raster scan) — see G3 above for construction.
- When: parsed with OCR enabled.
- Then: page 0's blocks come from `TextBlockExtractorPlugin`
  (`provenance.extractor == "pdfplumber"` or whatever the plugin
  emits) and page 1's come from `OcrExtractorPlugin`
  (`provenance.extractor == "ocr"`).
- Automated by: not feasible with PIL-only fixtures. **Manual
  scenario** built via `qpdf` or equivalent.

**D-2. Block ordering invariant.**
- Given: the same mixed PDF.
- When: parsed.
- Then: `structural.blocks` is ordered by page, then by `bbox.y`
  within a page; OCR-derived blocks on page 1 appear after all
  page-0 text blocks.
- Automated by: not yet. **Manual scenario.**

**D-3. Mixed fixture construction reference.**
- Given: a text PDF and a single-page raster PDF (e.g. from PIL).
- When: combined with `qpdf --empty --pages text.pdf 1 scan.pdf 1
  -- /tmp/mixed.pdf`.
- Then: page count is 2; pdfplumber reports text on page 1 and zero
  blocks on page 2.
- Automated by: not yet (would require `qpdf` in test environment).
  **Manual setup step** the tester runs before D-1/D-2.

### E — CLI

**E-1. `ptx-ireco parse --help` lists every `--ocr*` flag.**
- Given: a built `ptx-ireco` console script.
- When: `ptx-ireco parse --help` is invoked.
- Then: the output names `--ocr`, `--no-ocr`, `--ocr-language`,
  `--ocr-dpi`, `--ocr-min-ink-ratio`, `--ocr-mode` with their
  documented defaults.
- Automated by:
  `tests/unit/test_cli_ocr.py::test_parse_subparser_advertises_ocr_flags`
  and `test_run_subparser_advertises_ocr_flags`.

**E-2. Default (no `--ocr`) emits the discoverability WARN when
appropriate.**
- Given: an image-only PDF whose parse fails today without OCR
  (`RuntimeError`).
- And given: a real-world multi-page PDF where pdfplumber finds
  text on some pages but zero blocks on others.
- When: `ptx-ireco parse mixed.pdf -o /tmp/x.vim.json` (no `--ocr`).
- Then: stderr contains
  `WARN: <n>/<total> pages have no extracted text. Re-run with --ocr to recover them.`;
  exit code `0`.
- Automated by:
  `tests/unit/test_cli_ocr.py::test_warn_emitted_when_ocr_off_and_pages_missing_text`.
  E2E manual confirmation against a real mixed PDF.

**E-3. `--ocr` produces non-empty blocks for image pages.**
- Given: the mixed PDF from D-3.
- When: `ptx-ireco parse mixed.pdf -o /tmp/x.vim.json --ocr`.
- Then: exit `0`, no WARN, and `structural.blocks` contains entries
  for both page 1 (text) and page 2 (OCR).
- Automated by: not at CLI granularity (only at API level). **Manual
  scenario.**

**E-4. `--no-ocr` overrides config.**
- Given: an `ireco.config.json` with `parse.ocr.enabled: true` in
  the cwd.
- When: `ptx-ireco parse <pdf> -o out --no-ocr`.
- Then: OCR plugin is not registered (no Tesseract spawn).
- Automated by:
  `tests/unit/test_cli_ocr.py::test_build_ocr_options_no_ocr_overrides_config`
  (logic level). Manual E2E confirmation: pass an image-only PDF
  and observe `RuntimeError`.

**E-5. `--ocr-language` is plumbed through.**
- Given: any image-only PDF.
- When: `--ocr --ocr-language eng+ces` is used.
- Then: the registered `OcrExtractorPlugin._language` equals
  `"eng+ces"`.
- Automated by:
  `tests/unit/test_parse_ocr.py::test_register_optional_extractors_propagates_options`.

### F — Watcher / config

**F-1. Schema accepts `parse.ocr` block.**
- Given: an otherwise valid `ireco.config.json`.
- When: a `parse.ocr` block is added with sensible defaults.
- Then: `validate_config` raises no error.
- Automated by:
  `tests/unit/test_config_validator.py::test_parse_ocr_*_accepted`.

**F-2. Configs without `parse.ocr` still validate green.**
- Given: any pre-007 valid config.
- When: validated.
- Then: passes.
- Automated by: every pre-007 happy-path test in
  `test_config_validator.py` (no change needed; regression
  evidence).

**F-3. Invalid values are rejected with clear messages.**
- Given: a config with `parse.ocr.min_ink_ratio: 1.5`,
  `mode: "handwritten"`, `dpi: 50`, `enabled: "yes"`,
  or `parse.ocr.unknown: 1`.
- When: validated.
- Then: `ValidationError` raised; message names the offending JSON
  pointer.
- Automated by: 5 cases in
  `test_config_validator.py::test_parse_ocr_*_rejected`.

**F-4. End-to-end watcher run honors `parse.ocr.enabled`.**
- **EXPECTED FAIL** until gap G1 is fixed. See "Risks / known gaps".
- Given: an `ireco.config.json` containing
  `parse.ocr: {enabled: true}` and a watched input directory
  with a mixed PDF.
- When: `ptx-ireco-watcher` processes the file with the `local`
  backend.
- Then: the produced `.vim.json` has OCR blocks on the image page.
- Status today: F-4 cannot pass because `WatchConfig` does not
  carry `parse.ocr` and `dispatcher._dispatch_local` does not pass
  `ocr=` to `worker_pipeline.run`. Recommend marking acceptance F
  as CONDITIONAL with G1 listed as the remediation.

### G — Tests

**G-1. Marker registration in `pyproject.toml`.**
- Given: `pyproject.toml` post-merge.
- When: pytest collects with `--strict-markers`.
- Then: `requires_tesseract` and `requires_pdf2image` resolve;
  unknown markers would error.
- Manual: `.venv/bin/python -m pytest --strict-markers -q`.

**G-2. Skip-not-fail semantics.**
- Given: a host without Tesseract or `pdf2image`.
- When: the e2e OCR suite is collected.
- Then: every test under
  `tests/e2e/test_parse_ocr_e2e.py` is skipped with a clear
  reason; none fails.
- Automated by: `tests/conftest.py::pytest_collection_modifyitems`.
- Manual confirmation: `tesseract --version` then
  `.venv/bin/python -m pytest -q -rs tests/e2e/test_parse_ocr_e2e.py`
  before/after `apt remove tesseract-ocr`.

**G-3. Full suite green on host (no OCR runtime).**
- Given: dev host without `pdf2image`.
- When: `.venv/bin/python -m pytest -q`.
- Then: `268 passed, 11 skipped` (4 OCR e2e + 7 pre-existing
  worker-CLI skips).
- Automated by: the suite itself.

**G-4. Full suite green in container (Tesseract + pdf2image installed).**
- Given: the `python:3.12-slim` container with
  `apt install tesseract-ocr tesseract-ocr-ces poppler-utils` and
  `pip install -e .[dev] pdf2image`.
- When: `pytest -q`.
- Then: **272 passed, 7 skipped** (the 4 OCR e2e tests now run; the
  7 worker-CLI tests still skip unless the console scripts are on
  `PATH` — they should pass once `pip install -e .` is done).
- Manual: tester executes; protocol records actual counter.

### H — Documentation

**H-1. `docs/cli/parse.md` exists and covers every flag.**
- Given: the branch tree.
- When: `docs/cli/parse.md` is opened.
- Then: each of `--ocr`, `--no-ocr`, `--ocr-language`, `--ocr-dpi`,
  `--ocr-min-ink-ratio`, `--ocr-mode` is documented with its default
  and a usage example; prerequisites (Tesseract, `pdf2image`,
  Poppler) are listed.
- Manual review.

**H-2. `docs/pipeline/README.md` references the OCR fallback.**
- Manual review: the "Step 1 — Parse" subsection links to
  `docs/cli/parse.md` and names issue 007.

**H-3. Root READMEs (EN/CS/SK) mention OCR.**
- Manual review of `README.md`, `README.cs.md`, `README.sk.md`:
  each contains a short paragraph or CLI example with `--ocr`.

**H-4. TESTING_METHODOLOGY.md documents the new markers.**
- Manual review: the "Optional-dependency markers" section names
  `requires_tesseract` and `requires_pdf2image` and reaffirms the
  skip-not-fail contract.

---

## Coverage

### Test pyramid as of branch HEAD

| Tier        | New / changed files                                                                                          | Count of new test cases | Notes                                                                                  |
|-------------|--------------------------------------------------------------------------------------------------------------|--------------------------|----------------------------------------------------------------------------------------|
| Unit        | `tests/unit/test_parse_ocr.py`                                                                                | 17                       | OcrOptions, registration spy, ink-ratio helpers.                                       |
| Unit        | `tests/unit/test_cli_ocr.py`                                                                                  | 15                       | argparse, precedence, WARN logic.                                                      |
| Unit        | `tests/unit/test_config_validator.py` (additions)                                                             | +10                      | parse.ocr happy + 8 rejection paths + unknown-key.                                     |
| Unit        | `tests/unit/test_worker_pipeline.py` (regression update)                                                      | 1 (mod)                  | kwargs shape now includes `ocr`.                                                       |
| E2E         | `tests/e2e/test_parse_ocr_e2e.py`                                                                             | 4                        | Marker-gated; real Tesseract.                                                          |
| Fixtures    | `tests/conftest.py::ocr_pdf_fixtures`                                                                          | n/a                      | Lazily generates 3 image-only PDFs via PIL.                                            |

### Coverage gaps (manual scenarios needed)

These are intentionally not automated and must be exercised by the
tester before claiming PASS:

| Gap ID  | Scenario                                                                                                                | Why not automated                                                  |
|---------|-------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------|
| MS-1    | Inspect `pages[*].ocr` metadata block on `blank_and_content.pdf` (B-2).                                                  | Asserts structure; currently the e2e test inspects blocks only.    |
| MS-2    | Real mixed-content PDF (D-1, D-2, E-3) constructed with `qpdf`.                                                          | PIL alone cannot stamp text + raster in one PDF.                   |
| MS-3    | Watcher end-to-end with `parse.ocr.enabled: true` (F-4).                                                                  | Blocked on G1 — wiring gap. Will FAIL today.                       |
| MS-4    | CLI WARN against a real multi-page PDF with partial coverage.                                                            | Discoverability hint exists in unit tests, not at integration level. |
| MS-5    | Documentation review (H-1..H-4) for missing flags / outdated examples.                                                   | Inherently manual.                                                 |

### Coverage targets

| Module                                  | Target line coverage | Means of verification                                  |
|-----------------------------------------|----------------------|--------------------------------------------------------|
| `ptx_ireco.pipeline.parse` (OCR paths)  | ≥ 90 %               | `pytest --cov=ptx_ireco.pipeline.parse`                |
| `ptx_ireco.config.validator` (OCR)      | ≥ 95 %               | 8 rejection paths + 2 happy → 10 cases.                |
| `ptx_ireco.cli.main` (OCR)              | ≥ 80 %               | argparse + helpers; `_emit_ocr_discoverability_warn`.  |
| `ptx_reco.vim.extractors.ocr` (out of repo) | n/a                   | Owned by INT-024; do not re-test here.                 |

### Failure injection ideas (out-of-the-box scenarios)

These are stretch scenarios the tester may attempt for robustness
confidence. None are mandatory acceptance gates.

1. **Tesseract missing mid-run.** Start parse with Tesseract on
   PATH; `mv $(which tesseract) /tmp/` while parse is running. The
   plugin retries lazily on the next page; expect a `PluginResult`
   failure with a clear message from INT-007 surface.
2. **Corrupted PDF.** Truncate the image-only fixture to 256 bytes
   and re-run. Expect `RuntimeError` (parse path) without leaking
   half-rendered images.
3. **Non-existent language pack.** `--ocr-language xyz`. The plugin
   propagates Tesseract's error verbatim (INT-007 surface).
4. **High DPI on a huge image.** `--ocr-dpi 1200` on a multi-page
   scan. Expect successful completion or OOM kill — record observed
   peak memory.
5. **Race against a watched directory.** Two PDFs dropped within
   the cooldown window with `parse.ocr.enabled=true` and
   `workers=2`. Currently runs OCR-free (G1) so this only exercises
   that the parse_pdf raises don't poison the pool.

---

## CI notes

### Host vs container

- **Host dev runs** never produce a green acceptance signal alone —
  by design the OCR e2e tests skip without Tesseract + `pdf2image`,
  and that masks any regression introduced after the unit-tested
  spy registry. The protocol must include at least one container
  run with all deps installed.
- **Container image.** Re-use the `python:3.12-slim` baseline
  established by `acceptance-006.md`. Add `tesseract-ocr
  tesseract-ocr-ces tesseract-ocr-slk poppler-utils` and `pip
  install pdf2image`.

### Recommended invocation

```bash
# 1. Host smoke pass (must always be green even without Tesseract).
.venv/bin/python -m pytest -q

# 2. Container acceptance pass.
podman run --rm -it -v "$PWD":/repo -w /repo python:3.12-slim bash -lc "
    apt-get update -qq &&
    apt-get install -y -qq tesseract-ocr tesseract-ocr-ces tesseract-ocr-slk poppler-utils &&
    pip install -q -e .[dev] pdf2image &&
    pytest -q -rs --strict-markers
"
```

### Strict markers

`--strict-markers` MUST be used in the container run so unknown
markers fail loudly. Both `requires_tesseract` and
`requires_pdf2image` are registered in `pyproject.toml`; if either
is removed by mistake, the run errors out — protecting against
silent skips.

### Coverage capture

```bash
.venv/bin/python -m pytest -q --cov=ptx_ireco --cov-report=term-missing \
    tests/unit/test_parse_ocr.py \
    tests/unit/test_cli_ocr.py \
    tests/unit/test_config_validator.py
```

The acceptance protocol records the resulting % for the three OCR
modules listed in "Coverage targets".

---

## Acceptance Protocol — skeleton

> Fill in during execution (Phase 3). Move to
> `docs/testing/acceptance-007.md` once complete.

```markdown
# Acceptance Protocol — Issue #007

**Issue**: Per-page OCR fallback in `parse` step
**Branch**: `feature/issue-007-ocr-step`
**Commits under test**: ed66e0b, c9e07e9, c169f71, 5b7b768
**Tester**: <name> (<role>)
**Date**: <YYYY-MM-DD>
**Testing OS**: <host or container OS — name the authoritative env>

## Test Summary

| Counter                          | Value |
|----------------------------------|-------|
| Automated test scenarios (run)   |       |
| Automated: passed                |       |
| Automated: failed                |       |
| Automated: skipped               |       |
| Manual acceptance scenarios      |       |
| Manual: passed                   |       |
| Manual: conditional              |       |
| Manual: failed                   |       |
| Duration (full suite)            |       |

## Environment

```text
Host:        <kernel, distro>
Container:   <image + tag>
Python:      <version>
Tesseract:   <version + language packs>
pdf2image:   <version>
Poppler:     <version>
```

## Results by acceptance criterion

### A. Wiring
- [ ] A-1
- [ ] A-2
- [ ] A-3
- [ ] A-4

### B. Blank-page guard
- [ ] B-1
- [ ] B-2 (manual; quote `pages[*].ocr` JSON in evidence)
- [ ] B-3 (force-skip + force-OCR-on-everything)

### C. Text-page short-circuit
- [ ] C-1
- [ ] C-2 (manual)

### D. Mixed-content PDF
- [ ] D-1 (manual — mixed PDF via qpdf)
- [ ] D-2 (manual)

### E. CLI
- [ ] E-1
- [ ] E-2 (manual real-world PDF)
- [ ] E-3 (manual)
- [ ] E-4 (manual)
- [ ] E-5

### F. Watcher / config
- [ ] F-1
- [ ] F-2
- [ ] F-3
- [ ] F-4 — **expected FAIL until G1 closed** (see Findings)

### G. Tests
- [ ] G-1
- [ ] G-2
- [ ] G-3
- [ ] G-4

### H. Documentation
- [ ] H-1
- [ ] H-2
- [ ] H-3
- [ ] H-4

## Findings

| # | Severity | Description                                                            | Linked case | Recommended fix |
|---|----------|------------------------------------------------------------------------|-------------|-----------------|
| 1 | Blocker  | Watcher does not propagate `parse.ocr` to `worker_pipeline.run`.       | F-4 (MS-3)  | Close gap G1.   |
| 2 | Minor    | `ptx-ireco-worker run` has no `--ocr*` flags (cli backend can't OCR).  | E-3 / F-4   | Close gap G2.   |

## Final Decision

**STATUS**: <PASS | FAIL | CONDITIONAL>
**Approval for merge**: <YES | NO>
**Conditions to lift CONDITIONAL** (if any): <list>
**Date**: <YYYY-MM-DD>
**Tester signature**: <name>
```

---

**Plan version**: 1.1
**Status**: Active — ready for Phase 3 execution against
`feature/issue-007-ocr-step`.

## Plan update — 2026-05-19

Findings G1 and G2 (originally documented under "Risks / known gaps")
have been closed by commits `1faccb9` (code) and `520bbff` (tests) on
the same branch. Net effect on the cases above:

- **F-4** (watcher end-to-end with `parse.ocr.enabled: true`) is no
  longer expected to FAIL. `WatchConfig.parse_ocr` is loaded via
  `OcrOptions.from_config_dict` and `_dispatch_local` forwards it to
  `worker_pipeline.run(ocr=…)`. The pool dispatcher passes the
  options through its pickle envelope. The `cli` backend appends
  `--ocr*` flags to the subprocess command via
  `ocr_options_to_cli_args`.
- **E-3** (CLI `--ocr` produces non-empty blocks on a mixed PDF) now
  applies to **both** `ptx-ireco parse --ocr` and
  `ptx-ireco-worker run --ocr` — the worker CLI advertises the same
  flag set.
- New automated coverage: 4 `test_watcher_config` cases + 4
  `test_watcher_dispatcher` cases + 10 `test_cli_ocr_args` cases →
  expected host count rises to **286 passed / 11 skipped**.

The "Findings" table in the Acceptance Protocol skeleton should now
read:

| # | Severity | Description | Status |
|---|----------|-------------|--------|
| 1 | Closed   | G1 — watcher / pool / dispatcher propagate `parse.ocr`. | Fixed in `1faccb9`. |
| 2 | Closed   | G2 — `ptx-ireco-worker run`/`process`/`batch` accept `--ocr*` and `_dispatch_cli` forwards them. | Fixed in `1faccb9`. |

Acceptance protocol can target STATUS=PASS unmodified by these
findings; only fresh issues discovered during execution should land
in the Findings section going forward.
