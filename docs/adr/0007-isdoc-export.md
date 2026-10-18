# ADR-0007: ISDOC export for extracted invoices

- **Status**: Accepted (amended 2026-05-12 — see "Implementation amendments")
- **Date**: 2026-05-12
- **Deciders**: zdendaku (Architect)
- **Scope**: a runtime export path that turns a populated `*.vim.json`
  (output of the two-step parse → extract pipeline, ADR-0003) into a
  Czech ISDOC e-invoice artifact (`*.isdoc` XML, optionally
  `*.isdocx` ZIP container with the original PDF embedded).
- **Relates to**:
  - [ADR-0001](0001-invoice-profile-design.md) — three-layer invoice
    model. The country-neutral core schema (`models/invoice/core/
    invoice.schema.json`) is **EN 16931-aligned** by design; ISDOC 6.0.1
    has a published correspondence with EN 16931, so mapping starts
    from BT/BG semantics rather than from raw extractor output.
  - [ADR-0003](0003-flexy-pipeline-two-step.md) — `.vim.json` is the
    boundary artifact; export consumes a fully populated `semantic`
    layer and never re-parses the source PDF.
  - [ADR-0005](0005-ireco-plugin-split.md) — worker/driver split. The
    export path is shipped as a worker capability and surfaced via the
    driver CLI and Portunix task contract; no new plugin binary is
    introduced.
  - [ADR-0006](0006-runtime-only-scope.md) — ireco is a runtime. The
    **export mapping rules** (CZ-specific tax codes, registration
    numbers, ICO/DIC format constraints) are *consumed* here; their
    *authoring* belongs in `portunix-reco-studio`.

## Context

Czech ERP systems (Pohoda, Money S3/S5, ABRA Gen/Flexi, K2, Helios,
ALTUS Vario, …) overwhelmingly accept **ISDOC** as the canonical
import format for electronic invoices. ISDOC ("Information System
Document") is maintained by *Sdružení pro informační společnost (SPIS)*;
the current production schema is **ISDOC 6.0.1**, namespace
`http://isdoc.cz/namespace/2013`. ISDOCX is the same XML bundled with
the original PDF in a ZIP container — used widely as the audit-friendly
delivery unit between accountants and ERPs.

Today, ireco extracts invoices into a populated `semantic` layer of a
`.vim.json` (per ADR-0003). That layer is country-neutral EN 16931 BT/BG
data (per `models/invoice/core/invoice.schema.json`). Downstream
consumers wanting to **post** the invoice into a Czech ERP have to
re-encode that data into ISDOC themselves. Three forces drive the
decision to ship ISDOC export inside ireco:

1. **Mapping is a runtime concern, not a per-deployment concern.** The
   semantic-to-ISDOC mapping is identical across all installations
   that target Czech ERPs. Shipping it once in ireco prevents N
   re-implementations of the same translation in N integrations.

2. **EN 16931 ↔ ISDOC 6.0.1 is well-specified.** The core schema is
   already EN 16931-aligned. There is an authoritative correspondence
   between EN 16931 Business Terms (BT) / Business Groups (BG) and
   ISDOC element paths. The mapping is mechanical for the
   ~80 fields ERPs actually consume; the remaining ~20 fields are
   either CZ-specific (DUZP / tax-point date, CZ tax-rate categories,
   ICO 8-digit check) or optional.

3. **Provenance must survive the export.** VIM's design principle is
   that every semantic value references the physical block it came
   from. When an ERP imports an ISDOC and the operator questions a
   line, they should be able to trace it back to the source PDF box.
   ISDOC has no native provenance container, so the export must keep
   that trace in a sidecar that does not pollute the conformant XML.

The repo's runtime-only scope (ADR-0006) makes the placement decision
straightforward: a `parse → extract → export` flow stays entirely on
the runtime side. ISDOC mapping **rules** (per-country tax-rate code
tables, registration-number validators) are authoring artifacts — they
belong in `portunix-reco-studio` and are *delivered* to ireco under
`models/invoice/exports/isdoc/<country>/`, the same shape the
flexylayouts already use.

## Decision

ireco gains a third pipeline step — **`export`** — that operates on a
populated `.vim.json` and emits one or both of:

- `<doc>.isdoc` — an ISDOC 6.0.1 XML file that validates green against
  the bundled XSD.
- `<doc>.isdocx` — a ZIP container with `<doc>.isdoc` + the original
  `<doc>.pdf` (when available), per the ISDOCX convention.

The boundary stays `.vim.json`. Export is a **one-way, deterministic,
read-only** transformation of the semantic layer; it never modifies the
VIM file.

```text
       *.vim.json                ┌────────────────────────┐
       (semantic layer ─────────▶│ Step 3 (NEW): EXPORT   │──▶  *.isdoc   (XML, XSD-valid)
        fully populated)         │  semantic → ISDOC tree │     *.isdocx  (ZIP: isdoc + PDF)
       *.pdf (optional ─────────▶│  XML emit              │     *.isdoc.provenance.json
        for ISDOCX bundling)     │  XSD + BR validation   │     (sidecar; never inside .isdoc)
                                 └────────────────────────┘
```

### Where the export lives

| Surface                       | Form                                                                                                          |
|-------------------------------|---------------------------------------------------------------------------------------------------------------|
| **Python API**                | `ptx_ireco.export.isdoc.api.export(vim_path, *, out, format, profile, allow_incomplete, models) -> ExportResult` |
| **Driver CLI**                | `ptx-ireco export --format isdoc[x] --in <file.vim.json> [-o <out>] [--profile minimal\|standard\|full] [--allow-incomplete] [--models <path>]` |
| **Worker task** (`task execute`) | New task type `export` in the TaskRequest contract (issue 003); same JSON shape as `process` / `run`.        |
| **Watcher** (issue 004)        | Existing `scan.processed` callback may chain `export` when `watcher.post_process: ["export-isdoc"]` is set in `ireco.config.json` (additive schema change).           |

No new plugin binary. Export is a worker capability surfaced through
the existing `ptx-ireco-worker` and `ptx-ireco`. This is consistent
with ADR-0005's principle that runtime steps share the worker host.

### Module layout (additions only)

```text
src/ptx_ireco/
└── export/
    ├── __init__.py
    └── isdoc/
        ├── __init__.py
        ├── api.py            # public export() façade
        ├── mapper.py         # EN16931 BT/BG → ISDOC element tree
        ├── writer.py         # ISDOC XML serialization (lxml)
        ├── bundle.py         # ISDOCX ZIP container
        ├── validator.py      # XSD + business-rule validation
        ├── provenance.py     # sidecar emit
        ├── codes.py          # CZ tax-rate / unit-code lookup tables
        └── schemas/          # bundled ISDOC XSD (read-only)
            └── 6.0.1/
                ├── isdoc.xsd
                └── isdoc_invoice.xsd
models/invoice/exports/
└── isdoc/
    ├── README.md
    └── cze/
        ├── tax_categories.json   # EN 16931 BT-118 category → ISDOC <ClassifiedTaxCategory>
        ├── unit_codes.json       # UN/ECE Rec.20 → ISDOC <UnitCode>
        └── currency_codes.json   # ISO 4217 whitelist used by CZ ERPs
```

### Mapping principles

The mapper is **EN 16931 BT-id-indexed**, not "field-name-indexed".
Each BT has at most one ISDOC target path; missing BTs are treated
according to ISDOC cardinality (skip if optional, error if mandatory,
gated by the completeness profile — see below).

Reference shape of the core mapping table (illustrative subset):

| EN 16931 BT/BG                    | Semantic field (`fields.*`)        | ISDOC path                                                                  | Notes                       |
|-----------------------------------|-------------------------------------|-----------------------------------------------------------------------------|-----------------------------|
| BT-1 Invoice number               | `invoice_id`                        | `/Invoice/ID`                                                               | Required                    |
| BT-2 Issue date                   | `issue_date`                        | `/Invoice/IssueDate`                                                        | Required, `xsd:date`        |
| BT-3 Invoice type code            | `invoice_type_code`                 | `/Invoice/DocumentType` + `/Invoice/DocumentTypeCode`                       | 380=invoice, 381=credit-note|
| BT-5 Invoice currency             | `currency`                          | `/Invoice/LocalCurrencyCode` + `/Invoice/CurrencyCode`                      | ISO 4217                    |
| BT-9 Payment due date             | `due_date`                          | `/Invoice/PaymentMeans/Payment/PaymentDueDate` (Czech ERPs also read `/Invoice/PaymentDueDate`) |  |
| BT-72 VAT chargeable date (DUZP)  | `vat_chargeable_date`               | `/Invoice/TaxPointDate`                                                     | CZ-mandatory                |
| BG-4 Seller party                 | `issuer.*`                          | `/Invoice/AccountingSupplierParty/Party/*`                                  |                             |
| BT-31 Seller VAT ID (DIČ)         | `issuer.tax_id`                     | `…/Party/PartyTaxScheme/CompanyID`                                          | CZ format `CZ\d{8,10}`      |
| BT-29 Seller registration (IČO)   | `issuer.registration_id`            | `…/Party/PartyIdentification/ID`                                            | 8 digits + mod-11 check     |
| BG-7 Buyer party                  | `buyer.*` (or `recipient.*` when known-tenancy config attaches `document.recipient_id`) | `/Invoice/AccountingCustomerParty/Party/*` |  |
| BG-25 Invoice lines               | `lines[*]`                          | `/Invoice/InvoiceLines/InvoiceLine[*]`                                      | Iterate                     |
| BG-23 VAT breakdown               | `vat_breakdown[*]`                  | `/Invoice/TaxTotal/TaxSubTotal[*]`                                          | Group by rate               |
| BT-112 Total amount with VAT      | `amounts.total_with_vat`            | `/Invoice/LegalMonetaryTotal/PayableAmount`                                 | Required                    |
| BT-109 Total without VAT          | `amounts.total_without_vat`         | `/Invoice/LegalMonetaryTotal/TaxExclusiveAmount`                            | Required                    |
| BT-110 Total VAT                  | `amounts.total_vat`                 | `/Invoice/LegalMonetaryTotal/TaxAmount`                                     | Required                    |
| BG-17 Credit transfer / IBAN      | `payment.iban`, `payment.account`   | `/Invoice/PaymentMeans/PayeeFinancialAccount/{IBAN, BankAccountID}`         |                             |
| BT-83 Remittance information      | `payment.variable_symbol`           | `/Invoice/PaymentMeans/VariableSymbol`                                      | CZ-specific (legacy field)  |

The complete mapping table is delivered as a versioned JSON document
under `models/invoice/exports/isdoc/cze/` (see "Where authoring lives"
below) — the mapper code only walks the table, it does not hard-code
field paths.

### Completeness profiles

Three profiles control what the exporter does when the semantic layer
is incomplete:

- **`minimal`** — only ISDOC-required and CZ-mandatory fields. Always
  validates green against the XSD provided every required BT is
  present in the semantic layer.
- **`standard`** (default) — `minimal` + invoice lines + VAT breakdown.
  Matches what typical Czech AP modules import.
- **`full`** — every mapped BT/BG, including optional narrative,
  delivery, and barcode-derived hints. Used by audit and round-trip
  testing.

If a required field is missing for the chosen profile, the export
**refuses to emit by default** (exit code `4`, see "Error surface"
below). `--allow-incomplete` overrides: a non-conformant ISDOC is
written and a `validation.failed` event is emitted; the worker still
returns a non-zero status so pipelines do not silently drop bad data.

### Provenance sidecar

A second file is written alongside the ISDOC:

```text
<doc>.isdoc                       # conformant XML
<doc>.isdoc.provenance.json       # sidecar — JSON, not part of ISDOC
```

The sidecar maps each emitted ISDOC element back to the
`semantic.entities[*].source_block` (or `source_barcode`) it came
from. Sidecar shape:

```json
{
  "isdoc_version": "6.0.1",
  "vim_source": "scan.vim.json",
  "vim_version": "1.5",
  "entries": [
    {
      "isdoc_xpath": "/Invoice/ID",
      "value": "FA_26050001",
      "bt": "BT-1",
      "source_block": "block_3",
      "confidence": 0.97
    },
    {
      "isdoc_xpath": "/Invoice/LegalMonetaryTotal/PayableAmount",
      "value": "12345.00",
      "bt": "BT-112",
      "source_block": "block_27",
      "confidence": 0.92
    }
  ]
}
```

The sidecar is informational. ERPs ignore it; auditors read it.
It is never embedded inside the `.isdoc` XML so the conformance
profile stays strict.

### Validation pipeline (in writer order)

1. **Required-field check** against the chosen completeness profile.
2. **XSD validation** against `schemas/6.0.1/isdoc_invoice.xsd`.
3. **Business rules** — a subset of EN 16931 BR-* (e.g. BR-CO-10:
   `Σ line net = TaxExclusiveAmount`) and CZ-specific BR-CZ-* (IČO
   mod-11 check; DIČ regex; currency ∈ CZ-whitelist).
4. **Round-trip parse** (XSD + lxml) — defense in depth, ensures the
   writer didn't emit text that escapes-decodes differently.

Each gate failure produces a structured `ValidationError` with
`{rule, path, value, message}`. The worker maps gates 1–3 to exit
code `4 (VALIDATION_ERROR)` and gate 4 to exit code `2
(PROCESSING_ERROR)`.

### Worker task contract additions

The `task execute` JSON gains a new task type. **No version bump on
the wire format** — the change is additive (new `type` values are
accepted; old worker rejects them with `UNKNOWN_TASK`, which is
already in the error code surface re-exported from ptx-reco).

```jsonc
// TaskRequest — new type
{
  "type": "export",
  "input": "/abs/path/scan.vim.json",
  "output_dir": "/abs/out",
  "options": {
    "format": "isdocx",        // "isdoc" | "isdocx"
    "profile": "standard",     // "minimal" | "standard" | "full"
    "allow_incomplete": false,
    "models": "/abs/models"
  }
}
```

```jsonc
// TaskResponse — success
{
  "status": "ok",
  "outputs": [
    "/abs/out/scan.isdoc",
    "/abs/out/scan.isdoc.provenance.json"
  ],
  "metadata": {
    "isdoc_version": "6.0.1",
    "profile": "standard",
    "validations": {"xsd": "pass", "business_rules": "pass"}
  }
}
```

### Watcher integration (optional, additive)

`ireco.config.json` v1 gains an optional `watcher.post_process` array
(no schema-version bump; the field is additive per ADR-0004 rules):

```jsonc
{
  "watcher": {
    "post_process": ["export-isdoc"],
    "post_process_options": {
      "export-isdoc": {"format": "isdocx", "profile": "standard"}
    }
  }
}
```

When `post_process` contains `export-isdoc`, the watcher invokes the
export step after a successful `scan.processed` event. Failures emit
`export.failed`; the parser's output is preserved on disk regardless.

### Where authoring lives

Per ADR-0006, anything that produces a configuration artifact lives in
`portunix-reco-studio`. ireco *consumes* these artifacts at runtime:

| Artifact                                | Producer (studio)              | Consumer (ireco)                              |
|-----------------------------------------|--------------------------------|-----------------------------------------------|
| `models/invoice/exports/isdoc/cze/*.json` (mapping tables, code lists) | Studio editor              | `export.isdoc.codes`, `export.isdoc.mapper`   |
| ISDOC XSD bundle                        | Vendored from SPIS (immutable) | `export.isdoc.validator`                      |
| Provenance sidecar shape                | n/a (defined by ireco)         | `export.isdoc.provenance`                     |

Studio raises a follow-up issue tracked separately (referenced from
the implementation issue) for editing the CZ tax-rate / unit-code
tables. Until that lands, the tables ship as static JSON in the
ireco repo and are versioned alongside the mapper.

## Alternatives considered

- **External tool (e.g. UBL converter + post-processing script).**
  Rejected: a generic UBL→ISDOC converter can produce conformant XML,
  but loses the per-element provenance back to the source PDF and adds
  a non-Python dependency to the runtime install. The mapper is small
  enough to own in-repo.
- **Emit ISDOC directly from the extractor (skip the .vim.json
  boundary).** Rejected: violates ADR-0003. Re-running export after a
  mapping-rule fix would force re-parsing the PDF. The two-step
  boundary is the whole point of VIM.
- **Push ISDOC mapping into `portunix-reco`.** Rejected: ireco is the
  invoice-specialized runtime (ADR-0006). reco is upstream/generic and
  has no invoice-specific semantic layer to map from.
- **Generate the XML by string-templating instead of lxml.** Rejected:
  fails round-trip validation (gate 4) too often. lxml gives XSD
  validation for free and produces deterministic, canonicalized output
  that is easy to diff in tests.
- **Skip the provenance sidecar.** Rejected: every other ireco artifact
  preserves source-block back-references. Losing them at the export
  boundary breaks the audit story end-to-end.
- **Ship `.isdocx` only (no plain `.isdoc`).** Rejected: many CZ ERPs
  still consume the raw XML over EDI/file-watch interfaces.
- **Output ISDOC 5.x for legacy ERPs.** Deferred. The mapping table is
  versioned; a future ADR can add `isdoc:6.0.1`-vs-`isdoc:5.x` as a
  selectable target. Initial scope is 6.0.1 only.

## Consequences

### Positive

- **One-shot ERP onboarding.** Czech accounting integrations get a
  conformant ISDOC out of the box; no per-customer translation layer.
- **Boundary preserved.** Export consumes `.vim.json`, never the PDF;
  re-export after a mapping fix is cheap and reproducible.
- **Provenance preserved.** The sidecar keeps the audit chain
  `ISDOC element → BT/BG → source block → PDF region`.
- **Authoring/runtime split holds.** Mapping rules ship as
  JSON tables, which the studio can edit (ADR-0006); ireco only walks
  them.
- **Validation built in.** XSD + business rules + round-trip parse
  catch malformed output before it reaches the ERP.

### Negative

- **New required artifacts in the repo.** XSD bundle (~200 kB) and
  mapping tables are now part of ireco's footprint. Mitigation: keep
  them under `src/ptx_ireco/export/isdoc/schemas/` so they ship with
  the wheel; size remains well under typical Python wheel limits.
- **CZ specificity inside a country-neutral runtime.** ireco's core is
  EN 16931; this ADR introduces a CZ-named module. Mitigation: the
  module is namespaced (`export.isdoc`) and selectable by format —
  future SK/DE/AT exports (XRechnung, FatturaPA, …) would sit as
  siblings under `export/`.
- **Mapping drift risk.** ISDOC 6.0.1 is stable, but ERPs occasionally
  add reading-side quirks. Mitigation: the mapping table is a versioned
  artifact; corrections do not require code changes.

### Neutral

- The same export shape (`export <fmt>` subcommand + worker task type)
  applies to non-CZ targets: XRechnung (DE), FatturaPA (IT), UBL-PEPPOL
  (EU-wide). When those are added, this ADR is the design template,
  not the spec for them.

## Migration & deprecation

- No deprecation. Net-new feature; all existing surfaces stay
  byte-equivalent.
- Existing `ireco.config.json` files validate unchanged; new
  `watcher.post_process` / `watcher.post_process_options` keys are
  optional.
- Existing TaskRequests (`process`, `run`) are unchanged; old workers
  reject `type: "export"` with `UNKNOWN_TASK`, which is the
  forward-compatible failure mode already used elsewhere.

## Implementation amendments

Recorded during issue 006 implementation (2026-05-12). All amendments
are non-breaking — namespace, business rules, and the on-the-wire
artifact shape are unchanged.

### A1 — Schema version bumped 6.0.1 → 6.0.2

The upstream distribution at https://mv.gov.cz/isdoc/ ships **ISDOC
6.0.2**; 6.0.1 is no longer offered by the licensor (Ministry of the
Interior of the Czech Republic, license transferred from ICT UNIE on
5 May 2021). The namespace
(`http://isdoc.cz/namespace/2013`) is identical; 6.0.2 contains only
minor refinements relative to 6.0.1. The `field_map.json` records
the actual emitted version (`isdoc_version: "6.0.2"`).

### A2 — Single self-contained XSD instead of two

The original Decision section listed two schema files
(`isdoc.xsd` + `isdoc_invoice.xsd`). The upstream 6.0.2 distribution
ships a single self-contained schema (`isdoc-invoice-6.0.2.xsd`,
~141 kB, no `xs:import`). The validator therefore loads one file.

### A3 — No per-version subdirectory under `schemas/`

The original Module Layout placed XSDs under
`src/ptx_ireco/export/isdoc/schemas/6.0.1/`. Because the upstream
filename already encodes the version
(`isdoc-invoice-6.0.2.xsd`), the subdirectory is redundant — multiple
versions can coexist directly under `schemas/` without collision.
Final layout:

```text
src/ptx_ireco/export/isdoc/schemas/
├── README.md
└── isdoc-invoice-6.0.2.xsd
```

The `schemas/README.md` documents the source, license, and update
procedure.

### Impact on Decision section

Where the Decision section above says "ISDOC 6.0.1" / "schemas/6.0.1/
{isdoc.xsd, isdoc_invoice.xsd}", read it as "ISDOC 6.0.2" /
"schemas/isdoc-invoice-6.0.2.xsd". No other section is affected
(mapping principles, completeness profiles, validation pipeline,
worker contract, watcher integration, alternatives, and consequences
all remain valid as written).

## References

- ISDOC 6.0.2 specification & XSDs — Ministry of the Interior of
  the Czech Republic (https://mv.gov.cz/isdoc/), distributed under a
  permissive license; bundle checked into
  `src/ptx_ireco/export/isdoc/schemas/`.
- EN 16931:2017+A1:2019 — European e-invoicing semantic model
  (Business Terms / Business Groups).
- [ADR-0001](0001-invoice-profile-design.md) — three-layer invoice
  model & EN 16931-aligned core schema.
- [ADR-0003](0003-flexy-pipeline-two-step.md) — `.vim.json` boundary.
- [ADR-0005](0005-ireco-plugin-split.md) — worker/driver split and the
  task contract this ADR extends.
- [ADR-0006](0006-runtime-only-scope.md) — runtime/authoring scope rule
  that places mapping tables in studio and consumes them here.
- `models/invoice/core/invoice.schema.json` — semantic source schema.
