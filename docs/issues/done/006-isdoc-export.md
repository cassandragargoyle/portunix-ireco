# Issue 006 — ISDOC export for extracted invoices

- **Status**: done (closed 2026-05-13)
- **GitHub**: [#6](https://github.com/cassandragargoyle/portunix-ireco/issues/6)
- **Priority**: high
- **Area**: pipeline, export, worker, cli, watcher
- **Closed**: 2026-05-13 (acceptance protocol PASS in
  [`docs/testing/acceptance-006.md`](../../testing/acceptance-006.md))
- **Note**: amended 2026-05-12 — ISDOC 6.0.2 instead of 6.0.1; see
  "Implementation amendments" at bottom.
- **Related**:
  - [ADR-0007](../../adr/0007-isdoc-export.md) — authoritative design;
    this issue implements it.
  - [ADR-0003](../../adr/0003-flexy-pipeline-two-step.md) — `.vim.json`
    is the boundary; export consumes the populated `semantic` layer.
  - [ADR-0005](../../adr/0005-ireco-plugin-split.md) — worker/driver
    split; the new task type rides the existing contract.
  - [ADR-0006](../../adr/0006-runtime-only-scope.md) — mapping rules
    live in `models/invoice/exports/isdoc/<country>/`; studio owns
    their authoring (follow-up tracked separately).
- **Depends on**: [Issue 003](done/003-ireco-worker-plugin-split.md)
  (worker task contract) — closed.
- **Branch**: `feature/issue-006-isdoc-export`

## Goal

Add a runtime **`export`** step that turns a populated `*.vim.json`
into an ISDOC 6.0.2 artifact (`*.isdoc` XML and/or `*.isdocx` ZIP
bundle with the original PDF), with a JSON provenance sidecar, full
XSD + business-rule validation, and three surfaces:

1. Python API — `ptx_ireco.export.isdoc.api.export(...)`.
2. Driver CLI — `ptx-ireco export --format isdoc|isdocx ...`.
3. Worker task — new `type: "export"` in `task execute`.

Optionally chain the export from the watcher via
`watcher.post_process: ["export-isdoc"]`.

```text
   *.vim.json   ┌─────────────────────────┐   *.isdoc                (XML, XSD-valid)
   (semantic ─▶ │  Step 3: EXPORT (NEW)   │ ─▶  *.isdocx              (ZIP: .isdoc + .pdf)
    populated)  │   semantic → ISDOC tree │   *.isdoc.provenance.json (sidecar)
                │   XML emit + validation │
                └─────────────────────────┘
```

## Scope

### In scope

1. **Module `src/ptx_ireco/export/isdoc/`** with submodules listed in
   ADR-0007 ("Module layout").
2. **Bundled ISDOC 6.0.2 XSD** (`isdoc-invoice-6.0.2.xsd`) under
   `src/ptx_ireco/export/isdoc/schemas/` (vendored, immutable;
   filename encodes the version, so no per-version subdirectory).
3. **CZ mapping tables** as JSON under
   `models/invoice/exports/isdoc/cze/`:
   - `tax_categories.json` — EN 16931 BT-118 → ISDOC
     `ClassifiedTaxCategory`.
   - `unit_codes.json` — UN/ECE Rec.20 → ISDOC `UnitCode`.
   - `currency_codes.json` — ISO 4217 whitelist used by CZ ERPs.
   - `field_map.json` — the BT/BG → ISDOC XPath mapping table from
     ADR-0007 ("Mapping principles"). The mapper code walks this
     table; it does not hard-code paths.
4. **Three completeness profiles** `minimal | standard | full` (default
   `standard`) per ADR-0007.
5. **Provenance sidecar** `<doc>.isdoc.provenance.json` (informational,
   never embedded in XML).
6. **Validation pipeline**: required-field → XSD → business rules →
   round-trip parse. Each gate produces a structured `ValidationError`.
7. **Driver CLI** subcommand `ptx-ireco export`.
8. **Worker task** `type: "export"` (additive; no wire-format version
   bump).
9. **Watcher hook** `watcher.post_process: ["export-isdoc"]`
   (additive schema change to `ireco.config.json`).
10. **Documentation** — `docs/cli/export.md` (new), update root
    `README.md` (+ CS/SK translations), update `docs/pipeline/
    README.md` to describe the three-step flow.

### Out of scope

- **ISDOC 5.x** target. ADR-0007 leaves 5.x as a future ADR. Mapper
  must not branch on version; it must hard-code 6.0.2.
- **Non-CZ targets** (XRechnung, FatturaPA, UBL-PEPPOL). Module layout
  must keep `isdoc` as a sibling under `export/` so siblings can be
  added later, but no such siblings ship in this issue.
- **Studio editor** for the mapping tables. Static JSON ships from
  ireco; studio's tracking issue is referenced from the CZ mapping
  README — do not block on it.
- **Document types other than invoice / credit-note** (delivery notes,
  proformas, …). The mapper handles BT-3 codes `380` and `381` only;
  others return `VALIDATION_ERROR` with a clear message.
- **gRPC dispatch**. Same restriction as issue 004.

## Design — implementation specifics

> ADR-0007 owns the architectural decisions. This section pins the
> details a developer needs to land the patch without re-deriving
> them.

### Module layout

```text
src/ptx_ireco/
└── export/
    ├── __init__.py
    └── isdoc/
        ├── __init__.py
        ├── api.py            # export() façade
        ├── mapper.py         # BT/BG → ISDOC element tree (walks field_map.json)
        ├── writer.py         # lxml-based XML emit
        ├── bundle.py         # ISDOCX ZIP container
        ├── validator.py      # XSD + business rules + round-trip
        ├── provenance.py     # sidecar emit
        ├── codes.py          # CZ code-table lookups (tax categories, units, currency)
        ├── errors.py         # ExportError, ValidationError dataclasses
        └── schemas/
            ├── README.md
            └── isdoc-invoice-6.0.2.xsd
src/ptx_ireco/
├── cli/
│   └── main.py               # MODIFY — add `export` subcommand
└── worker/
    └── task/
        ├── adapter.py        # MODIFY — register `export` task type
        └── registry.py       # MODIFY — wire export handler
models/invoice/exports/isdoc/
├── README.md
└── cze/
    ├── tax_categories.json
    ├── unit_codes.json
    ├── currency_codes.json
    └── field_map.json
docs/cli/
└── export.md                 # NEW
docs/schemas/
└── ireco-config-1.0.json     # MODIFY — accept watcher.post_process and watcher.post_process_options
```

### Public Python API

```python
# ptx_ireco/export/isdoc/api.py

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ExportFormat = Literal["isdoc", "isdocx"]
ExportProfile = Literal["minimal", "standard", "full"]

@dataclass(frozen=True)
class ExportResult:
    format: ExportFormat
    profile: ExportProfile
    isdoc_path: Path
    provenance_path: Path
    bundle_path: Path | None              # set only when format=="isdocx"
    validations: dict[str, str]           # {"xsd": "pass", "business_rules": "pass", ...}

def export(
    vim_path: Path,
    *,
    out_dir: Path | None = None,
    format: ExportFormat = "isdoc",
    profile: ExportProfile = "standard",
    allow_incomplete: bool = False,
    models: Path | None = None,           # defaults to <repo>/models
    source_pdf: Path | None = None,       # required when format=="isdocx" and not next to vim_path
) -> ExportResult: ...
```

`out_dir` defaults to the `.vim.json`'s parent directory. Output names
are derived from the input stem (`scan.vim.json` →
`scan.isdoc`, `scan.isdocx`, `scan.isdoc.provenance.json`).

### Driver CLI

```text
ptx-ireco export --in <file.vim.json> [-o <out_dir>]
                 [--format isdoc|isdocx]              # default: isdoc
                 [--profile minimal|standard|full]    # default: standard
                 [--allow-incomplete]
                 [--models <models_path>]
                 [--source-pdf <file.pdf>]            # only for isdocx; auto-discovered otherwise
                 [-v/--verbose]
```

When `--format isdocx` and `--source-pdf` is omitted, the CLI looks
for `<stem>.pdf` next to the `.vim.json` and falls back to
`document.source` recorded inside the VIM file. If neither resolves,
exit `4 (VALIDATION_ERROR)` with a clear message.

### Worker task contract

```jsonc
// TaskRequest
{
  "type": "export",
  "input": "/abs/scan.vim.json",
  "output_dir": "/abs/out",
  "options": {
    "format": "isdocx",
    "profile": "standard",
    "allow_incomplete": false,
    "models": "/abs/models",
    "source_pdf": "/abs/scan.pdf"   // optional
  }
}
```

```jsonc
// TaskResponse — success
{
  "status": "ok",
  "outputs": [
    "/abs/out/scan.isdoc",
    "/abs/out/scan.isdoc.provenance.json",
    "/abs/out/scan.isdocx"
  ],
  "metadata": {
    "isdoc_version": "6.0.2",
    "profile": "standard",
    "validations": {"xsd": "pass", "business_rules": "pass"}
  }
}
```

```jsonc
// TaskResponse — validation failure
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "BT-112 missing; cannot emit /Invoice/LegalMonetaryTotal/PayableAmount",
    "details": [
      {"rule": "required", "path": "/Invoice/LegalMonetaryTotal/PayableAmount", "bt": "BT-112"}
    ]
  }
}
```

Use existing error codes from `ptx_ireco.worker.task.errors`:
`INVALID_INPUT` (missing/unreadable VIM), `VALIDATION_ERROR` (NEW —
add to `errors.py` re-export list), `PROCESSING_ERROR` (round-trip
parse failure), `UNKNOWN_TASK` (already covered by old workers).

Add `VALIDATION_ERROR` to the ireco-local error surface in
`src/ptx_ireco/worker/task/errors.py`; do not push it into ptx-reco
(it is ireco-specific). Document the addition in the module
docstring.

### Watcher integration

Schema additions in `docs/schemas/ireco-config-1.0.json` (additive,
no version bump):

```jsonc
{
  "watcher": {
    "post_process": ["export-isdoc"],                  // string array; valid values: ["export-isdoc"]
    "post_process_options": {                          // object keyed by post_process value
      "export-isdoc": {
        "format": "isdocx",
        "profile": "standard",
        "allow_incomplete": false
      }
    }
  }
}
```

Behavior:

- If `post_process` is absent or empty, watcher behavior is unchanged.
- For each entry in `post_process`, after a successful
  `scan.processed`, the watcher invokes the handler with the
  per-entry options. Failures emit a new event
  `EventType.POSTPROCESS_FAILED` with `metadata.handler` and
  `metadata.error`; the parser's `.vim.json` is preserved.
- `--post-process export-isdoc` CLI override is provided; overrides
  `watcher.post_process` per-flag (same pattern as the rest of issue
  004).

### Mapping table format

`models/invoice/exports/isdoc/cze/field_map.json`:

```jsonc
{
  "version": "1.0",
  "isdoc_version": "6.0.2",
  "namespace": "http://isdoc.cz/namespace/2013",
  "fields": [
    {
      "bt": "BT-1",
      "semantic_path": "fields.invoice_id",
      "isdoc_xpath": "/Invoice/ID",
      "cardinality": "1",
      "required_in": ["minimal", "standard", "full"]
    },
    {
      "bt": "BT-112",
      "semantic_path": "fields.amounts.total_with_vat",
      "isdoc_xpath": "/Invoice/LegalMonetaryTotal/PayableAmount",
      "cardinality": "1",
      "required_in": ["minimal", "standard", "full"],
      "transform": "decimal2"
    },
    {
      "bg": "BG-25",
      "semantic_path": "fields.lines[*]",
      "isdoc_xpath": "/Invoice/InvoiceLines/InvoiceLine",
      "cardinality": "0..n",
      "required_in": ["standard", "full"],
      "children": [
        {"bt": "BT-126", "semantic_path": "id", "isdoc_xpath": "ID"},
        {"bt": "BT-129", "semantic_path": "quantity", "isdoc_xpath": "InvoicedQuantity", "transform": "decimal3"},
        {"bt": "BT-131", "semantic_path": "net_amount", "isdoc_xpath": "LineExtensionAmount", "transform": "decimal2"}
      ]
    }
  ]
}
```

Transforms: `decimal2`, `decimal3`, `iso_date`, `iso_currency`,
`country_alpha2`, `czech_ico`, `czech_dic`. Each transform is a pure
function in `ptx_ireco.export.isdoc.codes`; unit-tested in isolation.

### Validation pipeline (writer order)

1. **Required-field check** against `field_map.json` filtered by
   `required_in` ∋ profile.
2. **XSD validation** with `lxml.etree.XMLSchema` loaded from the
   bundled XSD.
3. **Business rules**:
   - BR-CO-10: `Σ InvoiceLine/LineExtensionAmount == TaxExclusiveAmount`.
   - BR-CO-13: `TaxExclusiveAmount + TaxAmount == TaxInclusiveAmount`.
   - BR-CZ-IČO: `ID` of CZ-resident parties is 8 digits with mod-11
     check. Skip when country ≠ CZ.
   - BR-CZ-DIČ: matches `^CZ\d{8,10}$`. Skip when country ≠ CZ.
   - BR-CZ-CURRENCY: currency ∈ `currency_codes.json` whitelist.
4. **Round-trip parse**: re-load the emitted XML with
   `etree.fromstring`, re-validate against XSD. Catches encoding /
   escaping bugs.

Each rule lives as a function `def br_co_10(invoice_tree) ->
ValidationError | None`. The validator iterates a list and aggregates
results. **Do not stop at the first failure** — surface them all in
one response.

### Provenance sidecar

Shape per ADR-0007. Build it during mapping: every time the mapper
writes an XPath, record `(xpath, value, bt, source_block, confidence)`
into an accumulator. After XML emit, serialize the accumulator with
`json.dumps(..., ensure_ascii=False, indent=2)`.

Filename: `<stem>.isdoc.provenance.json`. Mode `0644`.

### ISDOCX bundle

`bundle.py` uses `zipfile.ZipFile(..., compression=ZIP_DEFLATED)`:

- `isdoc/<stem>.isdoc` — XML (deflate).
- `<stem>.pdf` — original PDF (stored, no compression — PDFs don't
  benefit and zipping them deflated wastes CPU).
- `META-INF/manifest.xml` — per the ISDOCX convention, lists the two
  entries with their MIME types.

The PDF lives at the ZIP root, not under `isdoc/`, matching what
Pohoda and Money import out of the box.

## Acceptance criteria

### A. Module structure

- [ ] `src/ptx_ireco/export/isdoc/` exists with all submodules listed
      above (`api.py`, `mapper.py`, `writer.py`, `bundle.py`,
      `validator.py`, `provenance.py`, `codes.py`, `errors.py`).
- [ ] `src/ptx_ireco/export/isdoc/schemas/isdoc-invoice-6.0.2.xsd`
      ships in the wheel (covered by a packaging test that imports
      the schema via `importlib.resources`).
- [ ] `models/invoice/exports/isdoc/cze/{tax_categories,unit_codes,
      currency_codes,field_map}.json` exist and validate against the
      shapes documented above.

### B. Python API

- [ ] `from ptx_ireco.export.isdoc import api; api.export(...)`
      works on a sample populated `.vim.json` (provided in fixtures —
      see §H) and returns an `ExportResult` with all four fields
      populated.
- [ ] `format="isdocx"` produces a ZIP with `<stem>.isdoc` and the
      source PDF at the ZIP root + `META-INF/manifest.xml`.
- [ ] `profile="minimal"` strips line items; `profile="full"` includes
      narrative + optional fields; `profile="standard"` matches the
      typical ERP import shape (verified by snapshot diff on a
      fixture).
- [ ] `allow_incomplete=True` emits a non-conformant XML when
      required fields are missing AND raises no exception; the
      returned `ExportResult.validations` carries the failing rules.
- [ ] `out_dir=None` writes alongside the input; explicit `out_dir`
      writes there; non-existent `out_dir` is rejected with a clear
      error.

### C. Driver CLI

- [ ] `ptx-ireco export --help` prints all flags listed in the
      "Driver CLI" section.
- [ ] `ptx-ireco export --in fixture.vim.json` writes
      `fixture.isdoc` + `fixture.isdoc.provenance.json` next to the
      input.
- [ ] `--format isdocx --source-pdf fixture.pdf` writes
      `fixture.isdocx` containing both entries + manifest.
- [ ] `--format isdocx` without `--source-pdf` auto-discovers
      `<stem>.pdf` next to the input; falls back to
      `document.source` in the VIM file; otherwise exits `4` with the
      message `"isdocx requires --source-pdf or a discoverable PDF"`.
- [ ] `--profile minimal` produces the same XML as `api.export(...,
      profile="minimal")` (byte-equal after canonicalization).
- [ ] Exit codes: `0` on success, `4` on validation failure (and on
      `--allow-incomplete` success, return `0` but log `WARN` to
      stderr; the validation result is still in the JSON output when
      `-v` is used).

### D. Worker task

- [ ] `task execute` with `{"type": "export", ...}` returns the
      response shape documented above.
- [ ] `VALIDATION_ERROR` is added to
      `src/ptx_ireco/worker/task/errors.py` and re-exported alongside
      the codes already imported from ptx-reco. Module docstring
      explains the local-only addition.
- [ ] Existing tasks (`process`, `run`) are byte-identical in
      behavior (verified by re-running issue 003 worker tests).
- [ ] Unknown handler in `options.profile` is rejected with
      `INVALID_INPUT` (not `VALIDATION_ERROR` — it is a request shape
      problem, not a data-quality problem).

### E. Watcher integration

- [ ] `docs/schemas/ireco-config-1.0.json` accepts the
      `watcher.post_process` array and `watcher.post_process_options`
      object; configs without these keys still validate green.
- [ ] Invalid `post_process` entry (e.g. `"export-xrechnung"`) is
      rejected at schema time with a clear error.
- [ ] With `watcher.post_process: ["export-isdoc"]`, dropping a
      fixture PDF in the watched dir results in `.vim.json` +
      `.isdoc` + `.isdoc.provenance.json` appearing in
      `io.output_dir`.
- [ ] `EventType.POSTPROCESS_FAILED` is emitted when the export
      validator fails; `.vim.json` is preserved on disk.
- [ ] `--post-process export-isdoc` CLI override works as documented;
      `--post-process ""` (empty) explicitly disables post-processing
      even when the config enables it.

### F. Validation

- [ ] All three completeness profiles produce XML that validates
      green against the bundled XSD on the fixture invoice.
- [ ] Business rules BR-CO-10, BR-CO-13, BR-CZ-IČO, BR-CZ-DIČ,
      BR-CZ-CURRENCY each have a positive (passing) and negative
      (failing) unit test.
- [ ] Round-trip parse (gate 4) is triggered for every successful
      emit (verified by patching `lxml.etree.XMLSchema.validate` and
      asserting it is called post-emit).
- [ ] A `VALIDATION_ERROR` response lists **all** failing rules, not
      just the first.

### G. Provenance sidecar

- [ ] For every emitted ISDOC element with a source block, an entry
      exists in `<stem>.isdoc.provenance.json` with `bt | bg`,
      `isdoc_xpath`, `value`, `source_block`, `confidence`.
- [ ] Sidecar is **never** embedded inside the `.isdoc` XML (verified
      by an XSD validation test).
- [ ] Sidecar JSON is UTF-8 with `ensure_ascii=False`, indented 2
      spaces, deterministic key order — diffable across re-runs.

### H. Tests

Fixtures land under `tests/fixtures/export/isdoc/`:

- `flowii-FA_26050001.vim.json` — populated semantic layer (hand-built
  to BT/BG completeness for the `full` profile).
- `flowii-FA_26050001.pdf` — copied from `samples/invoice/`.
- `flowii-FA_26050001.expected.isdoc` — golden output for the
  `standard` profile.
- `incomplete-missing-bt-112.vim.json` — for the validator failure
  case.

Required tests:

- [ ] Unit tests per submodule (mapper, writer, bundle, validator,
      provenance, codes).
- [ ] Each `codes.py` transform has both a passing and a failing
      case.
- [ ] Snapshot test: `api.export(fixture, profile="standard")`
      matches `flowii-FA_26050001.expected.isdoc` byte-for-byte after
      C14N (`lxml.etree.tostring(..., method="c14n2")`).
- [ ] Integration test: full pipeline (`parse` → `extract` →
      `export`) against `samples/invoice/flowii-FA_26050001.pdf`
      produces a green-validating ISDOC.
- [ ] Integration test: watcher with `post_process: ["export-isdoc"]`
      against the same fixture.
- [ ] Worker task test: round-trip a `task execute` request via the
      `cli` backend (subprocess); verify outputs list and validations.
- [ ] Regression: all issue 003, 004 tests still pass.

### I. Documentation

- [ ] `docs/cli/export.md` (new) — CLI reference, profile semantics,
      validation gates, sample outputs.
- [ ] `docs/pipeline/README.md` — extend to a three-step diagram
      (`parse → extract → export`); explicitly note that export is
      optional and runtime-only.
- [ ] `models/invoice/exports/isdoc/README.md` — explains the
      mapping table format and points at the studio follow-up issue.
- [ ] `README.md` (root, EN) — add an "Export" subsection alongside
      the watcher subsection; show one CLI invocation.
- [ ] `README.cs.md` and `README.sk.md` — mirror the English
      subsection.
- [ ] `docs/adr/0007-isdoc-export.md` — already accepted; no change
      required.

## Open architectural questions (resolve before / during impl)

1. **`isdocx` PDF compression mode.** ADR-0007 left this to the
   implementation. Suggested: `STORED` (no compression) for the PDF;
   PDFs are already compressed and re-deflating wastes CPU on the
   importer side. Document the choice in `docs/cli/export.md`.
2. **Fallback when `document.source` is a non-PDF (e.g. an image).**
   Suggested: refuse to build `isdocx` and exit `4` with a clear
   message; document. The XML emit path (`--format isdoc`) is
   unaffected.
3. **Provenance for derived values** (e.g. `TaxInclusiveAmount`
   computed by the mapper rather than read from a source block).
   Suggested: emit a synthetic entry with
   `source_block: "computed:<rule>"` and the same `confidence` as the
   inputs (min). Document in the sidecar README.
4. **Schema-level `post_process` enum vs. open string.** Suggested:
   start with an enum of one (`"export-isdoc"`). Future targets
   (`export-xrechnung`, …) extend the enum in a follow-up issue. This
   keeps the validator strict and prevents typos slipping through.
5. **Where to surface `VALIDATION_ERROR` exit code in the CLI when
   `--allow-incomplete` is set.** Suggested: return `0` (so pipelines
   continue), but log `WARN` to stderr and include the failures in the
   verbose JSON output. Document.

## Implementation hints (non-binding)

- Use `lxml` (already a likely transitive dep via ptx-reco; pin
  directly in `pyproject.toml`). The stdlib `xml.etree` cannot do
  XSD validation.
- For the field-map walker, write a tiny dotted-path resolver
  (`fields.amounts.total_with_vat` → `dict["fields"]["amounts"]
  ["total_with_vat"]`); avoid `jsonpath` libraries — overkill.
- Keep `writer.py` deterministic: sort attribute keys, use
  `etree.tostring(..., pretty_print=False, method="xml",
  encoding="utf-8", standalone=False)`. The snapshot test in §H
  relies on this.
- For the round-trip gate, re-parse the bytes you just emitted; do
  not re-serialize an in-memory tree (you would miss escaping bugs).
- Avoid hard-coding the namespace URL in the writer — pull it from
  `field_map.json` so future targets can sit alongside without
  touching writer code.

## Rollback steps

If the export step needs to be reverted (e.g. ISDOC spec churn or a
mapping-table regression that escapes tests):

1. Remove the `export` subcommand registration in
   `src/ptx_ireco/cli/main.py` (one block).
2. Unregister the `export` task type in
   `src/ptx_ireco/worker/task/registry.py`.
3. Drop the `watcher.post_process` schema additions in
   `docs/schemas/ireco-config-1.0.json` (additive, so removal is
   safe).
4. Leave the `src/ptx_ireco/export/` package in place; it is dead
   code without the CLI/task wiring, and keeping it makes a future
   re-enable a one-PR change.

No data migrations required — the export is read-only over
`.vim.json` and writes new files alongside, never modifying inputs.

## Definition of done

- All acceptance criteria above are checked.
- A tester acceptance protocol per
  ISSUE-DEVELOPMENT-METHODOLOGY.md is recorded under
  `docs/testing/acceptance-006.md` with `STATUS: PASS`. The protocol
  MUST cover:
  - Python API, CLI, and worker-task surfaces against the fixture
    invoice.
  - All three completeness profiles.
  - All three validation gates (required-field, XSD, business rules)
    on both passing and failing fixtures.
  - Watcher end-to-end with `post_process: ["export-isdoc"]`.
  - At least one negative test where `--allow-incomplete` is
    required to emit.
- Branch `feature/issue-006-isdoc-export` is merged into `main` only
  after that protocol exists.
- This issue file is moved to `docs/issues/done/` and the
  status row is updated in `docs/issues/README.md` per the archival
  convention in ISSUE-DEVELOPMENT-METHODOLOGY.md.

## Implementation amendments

Recorded 2026-05-12 during pre-implementation discovery. All
amendments are non-breaking (namespace and business rules unchanged)
and mirror the "Implementation amendments" section of ADR-0007.

1. **ISDOC version bumped 6.0.1 → 6.0.2.** The upstream
   distribution at https://mv.gov.cz/isdoc/ ships 6.0.2; 6.0.1 is
   no longer offered by the licensor (Ministry of the Interior of
   the Czech Republic). Namespace
   (`http://isdoc.cz/namespace/2013`) is identical.
2. **Single self-contained XSD** (`isdoc-invoice-6.0.2.xsd`)
   instead of the two files originally listed (`isdoc.xsd` +
   `isdoc_invoice.xsd`). The upstream 6.0.2 distribution ships one
   file with no `xs:import`.
3. **No per-version subdirectory** under `schemas/`. The upstream
   filename already encodes the version, so multiple versions can
   coexist directly under `schemas/`. Final layout:
   `src/ptx_ireco/export/isdoc/schemas/{README.md,
   isdoc-invoice-6.0.2.xsd}`.

These amendments override the corresponding inline mentions
("ISDOC 6.0.1" / "schemas/6.0.1/{isdoc.xsd, isdoc_invoice.xsd}")
wherever they still appear above. The `field_map.json` records
`"isdoc_version": "6.0.2"`.
