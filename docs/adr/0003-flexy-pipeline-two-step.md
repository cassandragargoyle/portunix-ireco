# ADR-0003: Two-step flexy document pipeline (parse → extract)

- **Status**: Accepted
- **Date**: 2026-05-09
- **Deciders**: zdendaku
- **Scope**: pipeline that turns a source document into a populated VIM file
- **Relates to**: [ADR-0001](0001-invoice-profile-design.md),
  [ADR-0002](0002-invoice-template-layer.md)

## Context

The "flexy" document pipeline turns a source document (PDF, scan, …) into a
canonical, validated representation that downstream systems can consume.
Two responsibilities are mixed together if the pipeline is built as one
monolithic step:

1. **Parsing** — getting text, layout, barcodes, tables, and graphic
   elements out of the source file.
2. **Extraction** — interpreting that raw evidence as semantic entities
   (issuer, buyer, totals, dates, payment, …) per a country/template
   profile.

These two responsibilities have very different inputs, dependencies, error
modes, and rates of change. Parsing depends on PDF/OCR libraries and
produces *positional* facts. Extraction depends on the country profile
(ADR-0001), the optional template layer (ADR-0002), and the flexylayouts in
`models/invoice/extraction/`, and produces *interpreted* facts. Re-running
extraction with a corrected profile or a new flexylayout should not require
re-parsing the original PDF.

The repository already standardizes on the **VIM format**
(`.vim.json` — Versatile Information Model) as the interchange shape for
extracted document information. VIM is explicitly **layered**: the
`physical` and `structural` layers describe what is on the page and how it
is grouped; the `semantic` layer describes what it *means*. The format
specification lives in the sibling architecture repo:
[`../portunix-architecture/docs/architecture/components/plugin-vim/vim-format.md`](../../../portunix-architecture/docs/architecture/components/plugin-vim/vim-format.md).

VIM's layer split lines up exactly with the parse/extract split above, so
it is a natural pivot point for the pipeline.

## Decision

The flexy document pipeline is split into **two explicit steps** with the
`.vim.json` file as the boundary between them:

```text
                     ┌────────────────────────────┐
   source document ──▶  Step 1: PARSE             ──▶  *.vim.json
                     │  (PDF/OCR → physical +     │       (physical +
                     │   structural [+ toc] +     │        structural
                     │   document metadata)       │        layers populated;
                     └────────────────────────────┘        semantic empty)

                     ┌────────────────────────────┐
   *.vim.json     ──▶│  Step 2: EXTRACT           ──▶  *.vim.json
   (from step 1)     │  (template match → country │       (semantic layer
                     │   profile → flexylayouts;  │        populated, with
                     │   write into semantic      │        provenance back
                     │   layer **of the same      │        to physical/
                     │   file**)                  │        structural)
                     └────────────────────────────┘
```

### Step 1 — Parse

- **Input**: source document (initial scope: PDF; OCR/image inputs may be
  added later via the same step contract).
- **Output**: a `.vim.json` file that conforms to the VIM format (currently
  `vim_version` 1.5).
- **Populated layers**: `physical`, `structural`, optional `toc`, plus the
  top-level `document` metadata (`source`, `pages`, optional metadata).
- **Not populated**: the `semantic` layer is left empty (or absent) at the
  end of step 1. Step 1 has no knowledge of invoices, profiles, or
  templates.
- **Determinism**: identical input must produce identical output (modulo
  documented timestamps), so step 2 can be re-run reproducibly.

### Step 2 — Extract

- **Input**: a `.vim.json` produced by step 1 (or any other source that
  emits valid VIM at this version).
- **Processing**:
  1. Run **template fingerprint matching** (ADR-0002) against the
     `physical` / `structural` content. If a template matches, use its
     `country`. If not, detect the country from the document.
  2. Resolve the country **profile** (ADR-0001) by `issue_date`.
  3. Apply the relevant **flexylayouts** (`models/invoice/extraction/`) to
     pull entities, payment data, and amounts out of the structural blocks
     and barcodes.
  4. Write the resulting entities into the **`semantic` layer of the same
     `.vim.json` file**, preserving provenance back to physical/structural
     blocks (`source_block`, `source_barcode` references defined by VIM).
- **Output**: the same `.vim.json` file with a populated `semantic` layer.
  No new file format is introduced.

### Why VIM is the boundary

- VIM already separates "what is on the page" (physical + structural) from
  "what it means" (semantic). The two-step split would otherwise require
  inventing a parallel intermediate format.
- VIM mandates provenance: every semantic entity references the physical
  block or barcode it came from. That is exactly the audit trail needed by
  flexy extraction and by downstream validation against profiles.
- VIM is forward-compatible: unknown fields are ignored. Extraction may
  write new keys into `semantic.entities[*].fields` without breaking older
  consumers.

### Re-extraction without re-parsing

Because step 2 takes a `.vim.json` as input and writes into the same file's
`semantic` layer, the pipeline supports:

- Re-running step 2 alone after a flexylayout fix.
- Re-running step 2 alone after a country profile is updated (ADR-0001
  versioning) and historical documents need to be re-classified.
- Producing several `.vim.json` outputs from one parse for A/B comparison
  of extractors.

The parse stage — typically the most expensive — does not have to be
repeated.

### Failure modes

- If step 1 fails, no `.vim.json` is produced; step 2 is not invoked.
- If step 2 fails (no profile, no flexylayout, low template confidence),
  the file from step 1 is still preserved on disk; the `semantic` layer is
  simply left empty (or partially populated with `confidence` values that
  reflect the uncertainty, per VIM's design principle 5).

## Alternatives considered

- **Single monolithic pipeline (parse + extract in one pass).**
  Rejected: couples a slow, library-heavy parsing stage to a fast-changing
  extraction stage. Re-extraction after a profile fix would force a
  re-parse. Failures in either responsibility are harder to localize.
- **Custom intermediate format between parse and extract.**
  Rejected: VIM already has a layered model designed for exactly this
  hand-off, with a documented spec and existing samples in `samples/`.
  Inventing a parallel format would be duplicate work and would lose
  provenance guarantees.
- **Write the extracted semantic data to a separate file
  (`*.semantic.json`) instead of back into the same `.vim.json`.**
  Rejected: VIM's `semantic` layer already exists for this purpose, and
  keeping all layers in one file preserves the back-references between
  semantic entities and their physical/structural sources without an
  external join. Tooling and consumers only need to read one file.
- **Three steps (parse → structuralize → extract).**
  Deferred: VIM treats the `physical` → `structural` transition as part of
  parsing, and current parsers produce both layers in one pass. If a future
  parser produces only `physical`, a structural step can be added without
  changing the extract contract.

## Consequences

### Positive

- **Clean boundary.** Parsing and extraction can evolve independently, in
  separate modules, with separate tests and separate dependencies.
- **Reproducible re-extraction.** A `.vim.json` snapshot makes it cheap to
  re-run extraction after flexylayouts or profiles change, including for
  historical documents.
- **Provenance preserved.** Every semantic entity references the
  physical/structural block it came from, by virtue of VIM.
- **Aligns with existing layered model.** The pipeline split is the same
  split VIM already uses; no new format is introduced.

### Negative

- **Two artifacts to think about.** Operators see "the parsed file" and
  "the extracted file" — but both are the same on-disk `.vim.json`,
  differing only in whether the `semantic` layer is populated. Mitigation:
  document this clearly in the pipeline README; consider a `--report`
  command that summarizes which layers are present.
- **Step 2 must be tolerant of partial input.** A `.vim.json` from step 1
  may legitimately lack barcodes, tables, or `toc`. Extraction must handle
  the absence of optional layers gracefully.

### Neutral

- The same two-step shape applies to other document types (`receipt`,
  `contract`, …). Step 1 is document-type-agnostic; step 2 dispatches on
  document type to the right model under `models/<doc-type>/`.

## References

- VIM Format Specification —
  [`../portunix-architecture/docs/architecture/components/plugin-vim/vim-format.md`](../../../portunix-architecture/docs/architecture/components/plugin-vim/vim-format.md)
  (sibling repo)
- [ADR-0001](0001-invoice-profile-design.md) — three-layer invoice model,
  profile versioning rules
- [ADR-0002](0002-invoice-template-layer.md) — template layer for
  fingerprint-based recognition
- Sample artifact already on disk:
  `samples/invoice/flowii-FA_26050001.pdf` and the corresponding
  `samples/invoice/flowii-FA_26050001.pdf.vim.json` (output of step 1)
