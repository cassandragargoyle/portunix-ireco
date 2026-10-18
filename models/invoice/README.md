# Invoice Model

Layered model for the **invoice** document type.

## Architecture

The invoice model is split into four layers:

1. **Templates** (`templates/`) — fingerprint-matched recognizers for specific
   recurring invoice formats (typically per issuer). If a template matches the
   input, processing follows its `country` to select the profile family.
   Filename = UUIDv4. Optional layer — used as a fast-path when applicable.
2. **Core** (`core/`) — country-neutral semantic model based on [EN 16931](https://www.ceniso.eu/) (European e-invoicing standard).
   Defines universal fields (issuer, buyer, line items, totals, dates, currency) using EN 16931 Business Term identifiers (`BT-*`, `BG-*`).
3. **Country profiles** (`profiles/<country>/`) — country-specific extensions (additional required fields, identifiers, validation rules). Each profile is
   versioned by its effective date — legal changes produce a **new file**, not an edit. The active profile is selected by document date.
4. **Extraction rules** (`extraction/`) — flexible layouts (flexylayouts) that map raw OCR/parsed input onto the core + profile fields.

### Processing Flow

1. **Try template match** against `templates/*.json` by fingerprint.
   If matched → use its `country`. If not → detect country from the document.
2. **Resolve profile**: pick the profile under `profiles/<country>/` whose
   `valid_from`/`valid_to` window contains the invoice's `issue_date`.
3. **Run extraction** to obtain field values.
4. **Validate** the result against the core schema + the resolved profile.

## Directory Layout

```text
models/invoice/
├── templates/                 # fingerprint-matched issuer templates (UUIDv4 names)
│   └── <guid>.json
├── core/                      # EN 16931 semantic model
│   └── invoice.schema.json
├── profiles/
│   ├── cze/                   # Czech Republic
│   │   ├── invoice-cze-2013-01-01.json
│   │   └── invoice-cze-2025-01-01.json
│   ├── deu/                   # Germany
│   │   └── invoice-deu-2025-01-01.json
│   └── svk/                   # Slovakia
│       └── (TBD)
└── extraction/                # OCR/parsing -> model mapping rules
```

## Country Codes

ISO 3166-1 alpha-3, lowercase (`cze`, `deu`, `svk`, `aut`, `pol`, ...).

## Profile Versioning

- Filename pattern: `<doc-type>-<country>-<effective-date>.json`
  (e.g. `invoice-cze-2013-01-01.json`)
- Effective date is ISO 8601 (`YYYY-MM-DD`)
- Each profile declares `valid_from` and optional `valid_to`
- Selection rule: pick the profile where `valid_from <= invoice_date < valid_to`
- Older versions are preserved for processing historical documents

## Format

All model files are **JSON**. JSON Schema (Draft 2020-12) is used for the core
model and profile validation.

## Related

- [`docs/adr/0001-invoice-profile-design.md`](../../docs/adr/0001-invoice-profile-design.md) — three-layer model, profile versioning rules
- [`docs/adr/0002-invoice-template-layer.md`](../../docs/adr/0002-invoice-template-layer.md) — template layer for fingerprint-based recognition
- Sample invoice documents: `samples/invoice/` (gitignored)
- EN 16931, UBL 2.1, Peppol BIS Billing 3.0 — reference standards
