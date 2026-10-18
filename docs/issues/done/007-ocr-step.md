# Issue 007 — Per-page OCR fallback in `parse` step

- **Status**: done
- **GitHub**: [#7](https://github.com/cassandragargoyle/portunix-ireco/issues/7)
- **Closed**: 2026-10-18
- **Acceptance**: [acceptance-007.md](../../testing/acceptance-007.md)
  — Round 2, STATUS PASS
- **Priority**: medium
- **Area**: pipeline, parse, config
- **Related**:
  - `portunix-reco` **INT-025** — "OCR-derived blocks lose text content
    and provenance in the structural layer" (acceptance-007 Finding F1).
    Closed 2026-05-22; fix included in `ptx-reco>=0.3.4`.
  - [ADR-0003](../../adr/0003-flexy-pipeline-two-step.md) — `parse` is the
    boundary that emits `physical` + `structural` layers into
    `.vim.json`; OCR augments those layers, not the `semantic` layer.
  - Issue 001 — established the two-step pipeline this extends.
- **Depends on**: `portunix-reco` **INT-024** —
  `ptx_reco.vim.extractors.ocr.extractor:OcrExtractorPlugin` wrapping
  the existing `ptx_reco.worker.ocr` engines. Must be merged and a
  release published before this issue can finish.
- **Branch**: `feature/issue-007-ocr-step`

## Goal

Make `parse_pdf` recover text from **image-only PDF pages** (scanned
invoices, photographs of paper) by running OCR per page and merging
the OCR text blocks into the `structural` layer of `.vim.json`. The
existing text path (pdfplumber via `TextBlockExtractorPlugin`) stays
the primary source; OCR is a per-page fallback that runs only when
pdfplumber found no text on a given page.

To avoid wasting Tesseract on blank scans, each candidate page is
gated by a cheap **ink-ratio check** on the rendered bitmap before
OCR is invoked.

```text
   PDF page ──▶ pdfplumber text blocks
                       │
        ┌──── any text blocks on the page? ────┐
        │ yes                                  │ no
        ▼                                      ▼
   keep blocks                       render page → ink ratio ≥ threshold?
                                              │
                                  ┌───────────┴───────────┐
                                  │ yes                   │ no
                                  ▼                       ▼
                          OCR (Tesseract)            skip (blank page)
                                  │
                                  ▼
                          OCR text blocks merged into `structural`
```

## Scope

### In scope

1. **Register OCR extractor plugin** in
   `src/ptx_ireco/pipeline/parse.py` — extend the `optional` tuple in
   `_try_register_optional_extractors()` with the new
   `OcrExtractorPlugin` from `ptx_reco` (best-effort import; failure
   to import keeps current behavior).
2. **Configuration** for OCR knobs, exposed at two levels:
   - **Python API**: new keyword args on `parse_pdf(...)` and
     `parse_pdf_to_file(...)` — `ocr: OcrOptions | None = None`.
   - **Driver CLI** (`ptx-ireco parse ...`): `--ocr/--no-ocr`,
     `--ocr-language`, `--ocr-dpi`, `--ocr-min-ink-ratio`,
     `--ocr-mode` (printed for v1; see "Out of scope" for handwritten).
   - **Watcher config** `ireco.config.json`: new `parse.ocr` block in
     `docs/schemas/ireco-config-1.0.json`.
3. **Per-page decision logic** lives in the OCR plugin (in
   `ptx_reco`) but the **configuration surface** and **defaults** are
   owned by `ptx_ireco`. The plugin must accept the options dict
   verbatim.
4. **Blank-page guard** — non-white pixel ratio computed on a binarized
   render of the page; OCR runs only when ratio ≥ `min_ink_ratio`.
   Default threshold: **0.005** (0.5 %). Configurable per-call.
5. **Reporting** — every page that ran OCR is recorded under
   `layers.physical.pages[i].ocr` with:
   - `ran: bool`
   - `skipped_reason: "had_text" | "blank_page" | null`
   - `ink_ratio: float` (always present when the page was a candidate)
   - `language: str`, `dpi: int`, `engine: "tesseract"`, `engine_version: str`
   - `text_block_count: int` (number of blocks the plugin contributed)
6. **Documentation** —
   - `docs/cli/parse.md` (extend if it exists; create otherwise) —
     OCR flags, defaults, examples.
   - `docs/pipeline/README.md` — mention OCR as an optional augment
     inside step 1.
   - `README.md` (EN) + `README.cs.md` + `README.sk.md` — one-line
     mention under "Parse".

### Out of scope

- **Handwritten OCR** (`ptx_reco.worker.ocr.handwritten`). Punt to a
  follow-up issue once `printed` is solid.
- **Checkbox detection** (`ptx_reco.worker.ocr.engines.checkbox`).
  Follow-up issue.
- **Per-region OCR** for hybrid pages (text vrstva + scanned stamps).
  This issue treats OCR as page-level fallback only.
- **OCR for non-PDF inputs** (loose images). The pipeline boundary
  stays PDF-only.
- **Tesseract model installation / management.** Assumes Tesseract +
  required language data are present on the host; documented in
  `docs/cli/parse.md`. No bundled binaries, no auto-download.
- **Cloud OCR backends** (Google Vision, AWS Textract, …). Not in
  this issue.

## Design — implementation specifics

### Config shape

```python
# ptx_ireco/pipeline/parse.py — new dataclass
from dataclasses import dataclass, field
from typing import Literal

OcrMode = Literal["printed"]   # extend with "handwritten" in a later issue

@dataclass(frozen=True)
class OcrOptions:
    enabled: bool = False
    language: str = "eng"           # Tesseract language code, e.g. "eng+ces"
    dpi: int = 300                  # render DPI for OCR
    min_ink_ratio: float = 0.005    # 0..1, fraction of non-white pixels
    mode: OcrMode = "printed"
```

`min_ink_ratio` is computed as:

```
ratio = count(pixels != white) / total_pixels
```

after rendering the page to a grayscale bitmap at `dpi` and binarizing
with Otsu's method. Implementation lives in the plugin (`ptx_reco`),
not in `ptx_ireco`. `ptx_ireco` only passes the threshold through.

### Watcher config — `docs/schemas/ireco-config-1.0.json`

Additive (no version bump):

```jsonc
{
  "parse": {
    "ocr": {
      "enabled": false,
      "language": "eng",
      "dpi": 300,
      "min_ink_ratio": 0.005,
      "mode": "printed"
    }
  }
}
```

If `parse.ocr` is absent, behavior is unchanged.

### CLI

```text
ptx-ireco parse --in <file.pdf> [-o <out.vim.json>]
                [--ocr | --no-ocr]                       # default: --no-ocr
                [--ocr-language <code>]                  # default: eng
                [--ocr-dpi <int>]                        # default: 300
                [--ocr-min-ink-ratio <float>]            # default: 0.005
                [--ocr-mode printed]                     # default: printed
                [-v/--verbose]
```

When `--ocr` is omitted and the parsed PDF has at least one page with
zero text blocks, the CLI **logs a one-line hint to stderr**:

```
WARN: 3/12 pages have no extracted text. Re-run with --ocr to recover them.
```

This makes the OCR path discoverable without enabling it silently.

### Plugin registration

`src/ptx_ireco/pipeline/parse.py:99-114` currently registers optional
extractors best-effort. Add OCR to the tuple **conditionally** — only
when `ocr.enabled is True` — to avoid pulling Tesseract bindings into
every parse:

```python
def _try_register_optional_extractors(registry, *, ocr: OcrOptions | None) -> None:
    optional = (
        ("ptx_reco.vim.extractors.barcode.extractor", "BarcodeExtractorPlugin", {}),
        ("ptx_reco.vim.extractors.table.extractor", "TableExtractorPlugin", {}),
        ("ptx_reco.vim.extractors.graphics.extractor", "GraphicsExtractorPlugin", {}),
        ("ptx_reco.vim.extractors.toc.extractor", "TocExtractorPlugin", {}),
        ("ptx_reco.vim.extractors.fulltext.metadata_extractor", "MetadataExtractorPlugin", {}),
    )
    if ocr is not None and ocr.enabled:
        optional = optional + (
            ("ptx_reco.vim.extractors.ocr.extractor", "OcrExtractorPlugin", _ocr_options_to_dict(ocr)),
        )
    for module_path, class_name, kwargs in optional:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            registry.register_extractor(cls(**kwargs) if kwargs else cls())
        except Exception as exc:
            logger.debug("Optional extractor %s skipped: %s", class_name, exc)
```

The existing extractors keep their no-arg `cls()` form; only OCR
takes kwargs.

### Per-page report shape

Final `.vim.json` excerpt for a 2-page mixed PDF (page 0 had text,
page 1 was a scan):

```jsonc
{
  "layers": {
    "physical": {
      "pages": [
        {
          "index": 0,
          "ocr": {"ran": false, "skipped_reason": "had_text", "ink_ratio": null}
        },
        {
          "index": 1,
          "ocr": {
            "ran": true,
            "skipped_reason": null,
            "ink_ratio": 0.087,
            "language": "eng",
            "dpi": 300,
            "engine": "tesseract",
            "engine_version": "5.3.4",
            "text_block_count": 14
          }
        }
      ]
    },
    "structural": { "blocks": [ /* text + OCR blocks intermixed, ordered by page+bbox */ ] }
  }
}
```

OCR-derived blocks carry `provenance.extractor: "ocr"` so downstream
consumers can distinguish them from pdfplumber blocks. Confidence
scores from Tesseract land in `provenance.confidence` (0..1, mean of
word-level conf reported by Tesseract for the block).

## Acceptance criteria

### A. Wiring

- [ ] `OcrOptions` dataclass exists in `src/ptx_ireco/pipeline/parse.py`
      with the fields listed above and the documented defaults.
- [ ] `parse_pdf(..., ocr=OcrOptions(enabled=False))` is byte-identical
      in output to the current `parse_pdf(...)` on every fixture in
      `tests/fixtures/` (regression).
- [ ] `parse_pdf(..., ocr=OcrOptions(enabled=True))` registers
      `OcrExtractorPlugin` from `ptx_reco`; if the import fails, parse
      still succeeds and emits one `WARN`-level log line.

### B. Blank-page guard

- [ ] On a synthetic 3-page PDF where pages 0 and 2 are blank scans
      (white only) and page 1 is a scanned invoice, OCR runs **only**
      on page 1.
- [ ] `layers.physical.pages[0].ocr` and `pages[2].ocr` record
      `ran=false`, `skipped_reason="blank_page"`, `ink_ratio < 0.005`.
- [ ] `pages[1].ocr.ran=true`, `ink_ratio >= 0.005`, and
      `text_block_count > 0`.
- [ ] Threshold is honored: with `min_ink_ratio=0.0`, page 0 OCRs
      anyway (and contributes zero blocks); with `min_ink_ratio=0.5`,
      even the invoice page is skipped.

### C. Text-page short-circuit

- [ ] On a fully text-extractable PDF (e.g.
      `samples/invoice/flowii-FA_26050001.pdf`), `parse_pdf(...,
      ocr=OcrOptions(enabled=True))` produces output **byte-equal**
      to `ocr=OcrOptions(enabled=False)` (i.e. OCR was registered but
      no page met the "no text blocks" condition).
- [ ] All `pages[*].ocr` entries record
      `ran=false, skipped_reason="had_text"`.

### D. Mixed-content PDF

- [ ] On a hand-crafted fixture `tests/fixtures/parse/ocr/mixed.pdf`
      (page 0 text, page 1 image scan), OCR runs only on page 1 and
      the merged `structural.blocks` contains both pdfplumber blocks
      (page 0) and OCR blocks (page 1).
- [ ] OCR-derived blocks have `provenance.extractor == "ocr"`;
      pdfplumber blocks have `provenance.extractor == "pdfplumber"`
      (or whatever the existing value is — match what
      `TextBlockExtractorPlugin` already emits).

### E. CLI

- [ ] `ptx-ireco parse --help` lists all `--ocr*` flags with their
      documented defaults.
- [ ] `ptx-ireco parse --in mixed.pdf -o out.vim.json` (no `--ocr`)
      prints the discoverability `WARN` to stderr and produces a VIM
      file with empty `structural.blocks` for page 1.
- [ ] `ptx-ireco parse --in mixed.pdf -o out.vim.json --ocr` produces
      a VIM file with non-empty blocks for page 1 and exits `0`.
- [ ] `--ocr-language ces+eng` is plumbed through to the plugin
      (verified by patching `OcrExtractorPlugin` and asserting the
      received options).

### F. Watcher config

- [ ] `docs/schemas/ireco-config-1.0.json` accepts the optional
      `parse.ocr` block; configs without it still validate green.
- [ ] Invalid values (`min_ink_ratio: 1.5`, `mode: "handwritten"`)
      are rejected at schema time with a clear error message.
- [ ] Watcher run with `parse.ocr.enabled: true` on a fixture
      directory containing `mixed.pdf` produces a `.vim.json` whose
      page 1 has non-empty `structural.blocks`.

### G. Tests

Fixtures under `tests/fixtures/parse/ocr/`:

- `mixed.pdf` — page 0 text, page 1 scan of the same invoice.
- `blank-and-content.pdf` — pages 0/2 blank, page 1 scanned invoice.
- `text-only.pdf` — symlink or copy of an existing text-PDF fixture.

Required tests:

- [ ] Unit: `OcrOptions` defaults match the documented values.
- [ ] Unit: `_try_register_optional_extractors` registers OCR only
      when `ocr.enabled=True`, and tolerates a missing
      `ptx_reco.vim.extractors.ocr` module (debug log only).
- [ ] Integration: each acceptance scenario A–F above is exercised by
      at least one pytest case.
- [ ] Regression: existing issue 001 / 003 / 004 parse tests still
      pass with OCR code present.
- [ ] Tesseract gate: if `tesseract` binary is not on `PATH`, the
      OCR-enabled tests are **skipped** (not failed) with a clear
      reason. Add a `pytest` marker `requires_tesseract` and document
      it in `docs/contributing/TESTING_METHODOLOGY.md`.

### H. Documentation

- [ ] `docs/cli/parse.md` documents all `--ocr*` flags, the blank-page
      heuristic, and the Tesseract prerequisite.
- [ ] `docs/pipeline/README.md` adds one paragraph: "Parse step may
      optionally invoke OCR per page; see `docs/cli/parse.md`."
- [ ] Root READMEs (EN/CS/SK) mention OCR support in the "Parse"
      subsection with one CLI example.

## Open questions (resolve during impl)

1. **Default language.** `"eng"` is safe but useless for CZ/SK
   invoices. Should the default be `"eng+ces+slk"`? Tradeoff: bigger
   default download for fresh installs vs. fewer footguns for the
   target use case. Suggested: keep `"eng"` and document the
   `"ces+slk"` install in `docs/cli/parse.md`.
2. **Blank-page heuristic** — Otsu binarization is fine for clean
   scans but may misclassify pages with heavy shading (gray
   backgrounds, photo paper) as "ink everywhere". Document and revisit
   if it causes problems in real-world data.
3. **Confidence aggregation per block** — Tesseract reports word-level
   confidences. Suggested: mean of words ≥ 0 (drop -1 sentinels).
   Document.
4. **Page render cache** — OCR rendering at 300 DPI is expensive.
   Should the rendered bitmap be reused across extractors that need
   it? Out of scope here, but flag for a future plugin-registry
   improvement.

## Implementation hints (non-binding)

- Don't import Tesseract bindings (`pytesseract`, `tesserocr`, …) at
  module load time in `parse.py`. The plugin in `ptx_reco` does that
  lazily; `parse.py` just imports the plugin class.
- The ink-ratio check should run **before** Tesseract is touched —
  it's the whole point of the guard. Verify with a profiling test
  that no Tesseract subprocess is spawned for blank pages.
- For the snapshot tests, canonicalize the OCR-derived block text by
  stripping trailing whitespace and collapsing internal runs of
  whitespace; Tesseract output is mildly non-deterministic across
  versions.

## Rollback steps

1. Remove the `--ocr*` flags from the CLI parser
   (`src/ptx_ireco/cli/main.py`).
2. Remove the `OcrOptions` parameter from `parse_pdf` and
   `parse_pdf_to_file`; revert
   `_try_register_optional_extractors` to its current no-arg form.
3. Remove the `parse.ocr` block from
   `docs/schemas/ireco-config-1.0.json`.
4. Leave the `OcrExtractorPlugin` in `ptx_reco` untouched — it's
   independent and may be useful for other consumers.

No data migrations. The OCR fields under `layers.physical.pages[*].ocr`
are additive; older readers ignore unknown keys.

## Definition of done

- All acceptance criteria above are checked.
- The companion `ptx_reco` issue is merged and a release with
  `OcrExtractorPlugin` is consumed here.
- Tester acceptance protocol per
  `docs/contributing/ISSUE-DEVELOPMENT-METHODOLOGY.md` is recorded
  under `docs/testing/acceptance-007.md` with `STATUS: PASS`. The
  protocol MUST cover:
  - All four fixtures (`text-only`, `mixed`, `blank-and-content`,
    plus the existing samples regression).
  - At least one run with `--ocr-language` set to a non-default value.
  - At least one run with `min_ink_ratio` tuned to demonstrate both
    extremes (0.0 and 0.5).
  - Watcher end-to-end with `parse.ocr.enabled: true`.
- Branch `feature/issue-007-ocr-step` is merged into `main` only
  after that protocol exists.
- This issue file is moved to `docs/issues/done/` and the
  status row is updated in `docs/issues/README.md` per the archival
  convention in `ISSUE-DEVELOPMENT-METHODOLOGY.md`.
