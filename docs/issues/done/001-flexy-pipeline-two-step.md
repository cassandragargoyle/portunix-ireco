# Issue 001 — Implement two-step flexy document pipeline (parse → extract)

- **Status**: done
- **GitHub**: [#1](https://github.com/cassandragargoyle/portunix-ireco/issues/1)
- **Closed**: 2026-05-09
- **Priority**: high
- **Area**: pipeline, models/invoice
- **Related**: [ADR-0003](../../adr/0003-flexy-pipeline-two-step.md),
  [ADR-0001](../../adr/0001-invoice-profile-design.md),
  [ADR-0002](../../adr/0002-invoice-template-layer.md)
- **Branch**: `feature/issue-001-flexy-pipeline-two-step`

## Goal

Implement the flexy document processing pipeline as **two explicit steps**
with a `.vim.json` file as the boundary, per ADR-0003.

```text
source document ──▶ Step 1: PARSE ──▶ *.vim.json
                                         │ (physical + structural [+ toc])
                                         ▼
                    Step 2: EXTRACT  ──▶ *.vim.json (semantic layer added)
```

The output of step 1 must conform to the VIM format specification kept in
the sibling architecture repo:
[`../portunix-architecture/docs/architecture/components/plugin-vim/vim-format.md`](../../../../portunix-architecture/docs/architecture/components/plugin-vim/vim-format.md)
(relative to this issue file).

As part of this issue, deliver a working **invoice extraction template**
that populates the semantic layer of
`samples/invoice/flowii-FA_26050001.pdf.vim.json`. The PDF and the
parsed-only VIM file are already in `samples/invoice/`.

## Background

ADR-0003 splits parsing and extraction so that:

- Parsing (PDF/OCR → physical + structural) is independent of any
  invoice/country/template knowledge.
- Extraction (template match → profile resolution → flexylayouts →
  populate `semantic` layer) can be re-run against an existing
  `.vim.json` without re-parsing the source document.

The interchange format is **VIM 1.5+** (`.vim.json`). All extracted
entities written into `semantic.entities[*]` must reference their source
`physical`/`structural` block (`source_block`, `source_barcode`) and carry
a `confidence` value, per VIM design principles.

## Scope

In scope:

1. Step 1 (parse): produce `.vim.json` from a source document with
   `physical` + `structural` layers populated. The `semantic` layer must
   be left empty/absent.
2. Step 2 (extract): given a `.vim.json` from step 1, run
   template→profile→flexylayout, and write results into the `semantic`
   layer of the **same** file. Must preserve all pre-existing layers
   unchanged.
3. CLI / orchestrator command(s) that can run each step independently
   *and* both in sequence. Suggested shape (final naming up to the
   implementer; document whatever is chosen):
   - `<cli> parse <input> -o <out.vim.json>`
   - `<cli> extract <in.vim.json> [--in-place | -o <out.vim.json>]`
   - `<cli> run <input> -o <out.vim.json>` (= parse then extract)
4. **Invoice template** for the sample
   `samples/invoice/flowii-FA_26050001.pdf.vim.json` that, when the
   pipeline runs end-to-end, yields a populated `semantic` layer for
   that file. Place the template under `models/invoice/templates/` per
   ADR-0002 (UUIDv4 filename, `country: "CZE"`).
5. A flexylayout under `models/invoice/extraction/` driving the
   semantic-layer population for that template (or a generic CZE
   flexylayout that covers it — implementer's choice, but document the
   decision).

Out of scope:

- New document types other than invoice.
- A second country profile (CZE only is enough for this issue; ADR-0001
  selection logic should still be wired in so the right CZE profile is
  picked by date).
- Web UI / API service. CLI is sufficient.

## Acceptance criteria

### A. Two-step contract

- [ ] Running step 1 alone produces a `.vim.json` whose `semantic` layer
      is empty/absent and whose `physical` + `structural` layers are
      populated.
- [ ] Running step 2 against the output of step 1 (or against the
      already-checked-in
      `samples/invoice/flowii-FA_26050001.pdf.vim.json`) writes the
      `semantic` layer **into the same file** without altering the
      `physical`, `structural`, `toc`, or top-level `document` fields.
- [ ] Re-running step 2 on a file whose semantic layer already exists is
      idempotent (or clearly documented as overwriting; pick one and
      stick to it).
- [ ] If step 2 cannot match a template / resolve a profile / extract,
      it exits non-zero with a descriptive error and does **not**
      partially corrupt the input file.

### B. Invoice template for the sample (mandatory)

- [ ] A template exists in `models/invoice/templates/<uuid>.json` whose
      fingerprint matches `samples/invoice/flowii-FA_26050001.pdf.vim.json`
      with score ≥ its `match_threshold`. Suggested rule set for that
      sample (match-only — no semantic content lives here per ADR-0002):
  - `text_anchor`: `"Dříč s.r.o."` — issuer name on the invoice.
  - `text_anchor`: `"www.flowii.com"` — Flowii-rendered footer present
    on these invoices.
  - `tax_id`: `"12345678"` (issuer IČO).
  - `vat_id`: `"CZ12345678"` (issuer DIČ).
  - `match_threshold`: pick a value that the sample clears with margin.
- [ ] Template `country` = `"CZE"`. Profile version is resolved at
      runtime by `issue_date` per ADR-0001 — the template must NOT pin a
      profile file.
- [ ] When step 2 runs against the sample `.vim.json`, the resulting
      `semantic` layer contains, at minimum:
  - The **invoice header**: invoice number `"26050001"`, issue date
    `2026-05-09`, taxable supply date (DUZP) `2026-05-09`, due date
    `2026-05-23`.
  - The **issuer (vystavil)**: `Dříč s.r.o.`, IČO `12345678`,
    DIČ `CZ12345678`, address (Za rohem 123, 12300 Ráj, Česká
    republika).
  - The **buyer (odběratel)**: `PŘÍKLADOVÁ a.s.`, IČO `00000019`,
    DIČ `CZ00000019`, address (Ukázková 1, 110 00 Praha 1,
    Česká republika).
  - **Totals**: total without VAT `1 000 000,00`, VAT `210 000,00`,
    total with VAT `1 210 000,00`, currency `CZK`.
  - **VAT breakdown**: 21% bracket with base `1 000 000,00` and tax
    `210 000,00`.
  - **Payment**: variable symbol `26050001`, total to pay
    `1 210 000,00 CZK`, method "Převodní příkaz".
  - Each entity references the `source_block` (or `source_barcode`)
    from which it was derived, and has a numeric `confidence`.

### C. Pipeline behavior

- [ ] Step 1 output validates against the VIM format spec
      (`vim_version` populated, layer fields well-formed, UTF-8, null
      handling per spec).
- [ ] Step 2 selects the country profile from the resolved
      `country` + `issue_date` per ADR-0001's selection rule (a CZE
      profile valid for `2026-05-09` must exist or be added).
- [ ] If no template matches, step 2 falls back to country detection
      from the document content (per ADR-0003, ADR-0002).
- [ ] All written semantic entities respect the VIM `SemanticEntity`
      shape (`type`, `source_block`, `fields`, `confidence`).

### D. Tests

- [ ] Unit tests for: template fingerprint scoring, profile date
      resolution, flexylayout extraction primitives.
- [ ] Integration / end-to-end test that runs step 1 + step 2 against
      `samples/invoice/flowii-FA_26050001.pdf` (or step 2 against the
      pre-parsed `*.vim.json`) and asserts the populated semantic layer
      matches a checked-in expected fixture.
- [ ] A negative test where the template does not match → pipeline
      either falls through to country detection or exits with a clear
      error (per chosen behavior).

### E. Documentation

- [ ] Top-level pipeline doc that describes the two steps, the CLI, and
      the invariant "the output of step 1 is also the input of step 2;
      it is the same file shape".
- [ ] `models/invoice/extraction/README.md` describing the flexylayout
      file structure (or update if it already exists) and how
      extraction maps onto the VIM `semantic` layer.
- [ ] Any ADR-0003 deviations noted in this issue or in a follow-up
      ADR.

## Implementation hints (non-binding)

- The pre-parsed sample `samples/invoice/flowii-FA_26050001.pdf.vim.json`
  is already on disk and uses `vim_version` 1.4. New parses should emit
  the current VIM version (currently 1.5); the extractor must accept
  both 1.4 and 1.5 inputs (forward-compatibility per VIM spec).
- Useful evidence already present in the sample for matching/extraction:
  - Issuer block: "Dříč s.r.o." / "Za rohem 123" / "12300 Ráj" /
    "Česká republika" / "IČO: 12345678" / "DIČ: CZ12345678".
  - Buyer block (under "Odběratel:"): "PŘÍKLADOVÁ a.s." / address /
    "IČO: 00000019" / "DIČ: CZ00000019".
  - Header: "Faktura: 26050001" / "Datum vystavení: 9.5.2026" /
    "DUZP: 9.5.2026" / "Splatnost: 23.5.2026".
  - Totals: "Fakturovaná částka 1 210 000,00 Kč", VAT row at 21%.
  - Payment: "Variabilní symbol: 26050001",
    "Způsob platby: Převodní příkaz".
- The VIM spec is the source of truth for field names, layer structure,
  and confidence semantics — link from
  [`../portunix-architecture/docs/architecture/components/plugin-vim/vim-format.md`](../../../../portunix-architecture/docs/architecture/components/plugin-vim/vim-format.md).

## Definition of done

- All acceptance criteria above are checked.
- ADR-0003 is referenced from the pipeline README.
- A tester acceptance protocol per ISSUE-DEVELOPMENT-METHODOLOGY.md is
  recorded under `docs/testing/acceptance-001.md` with `STATUS: PASS`.
- Branch is merged into `main` only after that protocol exists.
- This issue file is moved to `docs/issues/done/` and the
  status row is updated in `docs/issues/README.md` (per the methodology).
