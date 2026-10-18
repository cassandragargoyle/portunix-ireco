# ADR-0001: Invoice profile design

- **Status**: Accepted
- **Date**: 2026-05-09
- **Deciders**: zdendaku
- **Scope**: `models/invoice/`

## Context

Invoices vary along two independent dimensions that the document model must
accommodate:

1. **Jurisdiction.** Each country imposes its own legal requirements on what
   constitutes a valid invoice — required identifiers (e.g. CZ `IČO`/`DIČ`,
   DE `USt-IdNr.`/`Steuernummer`), applicable VAT rates and categories, payment
   reference conventions (e.g. CZ variabilní/konstantní/specifický symbol),
   localized field labels, and structural rules (e.g. reverse-charge notes,
   small-amount invoice exemptions).
2. **Time.** These rules change. VAT rates are revised, e-invoicing mandates
   are introduced, identifier formats are updated. The system must process
   both newly issued documents under current rules **and** historical documents
   under the rules that were in force when they were issued.

A single monolithic schema cannot capture either dimension cleanly. Conditional
logic ("if country X and date > Y") embedded in one file becomes unauditable as
it grows, and edits to the file destroy the historical record needed to
re-validate older documents.

EN 16931 (the European e-invoicing standard) already defines a country-neutral
semantic core for invoices, and is the basis for UBL 2.1, Cross-Industry
Invoice (CII), Peppol BIS Billing 3.0, ZUGFeRD, and XRechnung. Building on it
both reduces work and aligns the project with the wider e-invoicing ecosystem.

## Decision

The invoice model is split into three layers under `models/invoice/`:

```text
models/invoice/
├── core/                      # EN 16931 semantic model (country-neutral)
├── profiles/<ccc>/            # country-specific extensions, versioned by date
└── extraction/                # OCR / parsing -> model mapping rules
```

### Core layer

- A single JSON Schema (Draft 2020-12) at `core/invoice.schema.json` defines
  the canonical invoice structure (parties, line items, totals, VAT breakdown,
  payment, dates, currency).
- Field-level `$comment` entries reference EN 16931 Business Term identifiers
  (`BT-*`) and Business Groups (`BG-*`) so each field is traceable to the norm.

### Profile layer

- Profiles live under `profiles/<ccc>/` where `<ccc>` is the
  **ISO 3166-1 alpha-3** country code, lowercase (e.g. `cze`, `deu`, `svk`).
- Each profile is a JSON file named
  `<doc-type>-<country>-<effective-date>.json`
  (e.g. `invoice-cze-2013-01-01.json`).
- A profile declares:
  - `country` — ISO 3166-1 alpha-3 code
  - `valid_from` (required) and `valid_to` (optional, `null` = open-ended)
  - `extends` — relative path to the core schema
  - `language`, `currency_default`
  - `identifiers` — country-specific identifiers with patterns, labels, and
    applicability (which party, when required)
  - `required_fields`, `required_one_of` — jurisdictional constraints layered
    on top of the core
  - `field_aliases` — local-language labels for core fields
  - `vat_categories` — applicable VAT codes and rates (which themselves may
    carry `valid_from` for finer-grained changes within a profile)
  - `notes` — free-form remarks
- Profiles use **UTF-8 with full diacritics** in localized strings
  (`IČO`, `DIČ`, `Variabilní symbol`, `ermäßigter Steuersatz`).

### Versioning rule (immutability)

- A legal change produces a **new profile file**, not an edit to an existing
  one. The previous profile's `valid_to` is set when the new one is added.
- Older profiles are kept indefinitely so historical documents can be processed
  under the rules in force at their `issue_date`.
- The selection rule is:
  > Pick the profile where `valid_from <= invoice.issue_date` and
  > (`valid_to` is null or `invoice.issue_date <= valid_to`).
- Typo or clarification fixes that do not change semantics are the only
  permitted in-place edits; any change to required fields, patterns, rates,
  or constraints requires a new file.

### Extraction layer

- Extraction rules (flexylayouts) are kept separate from the semantic model.
  They map raw OCR / parser output onto core + profile fields and may be
  updated independently of the legal model.

## Alternatives considered

- **Single mutable schema with conditional logic.** Rejected: edits destroy the
  historical record; conditional logic in a single file becomes unreadable
  across many countries and many years.
- **Database-backed rule store.** Rejected at this stage: adds runtime tooling
  and obscures the audit trail. JSON files in git already give versioning,
  diffs, code review, and offline use for free. Can be revisited if the
  profile set grows beyond what is comfortable in version control.
- **Custom DSL for profiles.** Rejected: more flexibility than required, and
  pulls in parser/tooling work. Plain JSON + JSON Schema is sufficient.
- **YAML instead of JSON.** Rejected: JSON is unambiguous, has first-class
  schema support (Draft 2020-12), and aligns with the JSON-based payloads
  used elsewhere in the e-invoicing ecosystem.
- **ISO 3166-1 alpha-2 country codes.** Rejected: alpha-3 is more readable in
  filenames and directory listings (`cze` vs `cz`, `deu` vs `de`) and avoids
  visual collisions with two-letter language codes.

## Consequences

### Positive

- **Auditable history.** Every legal change is a new file with a date and a
  diff in git, reviewable like any other code change.
- **Deterministic processing of historical documents.** The right profile is
  selected from the document's date — no special-casing required.
- **Clean separation of concerns.** Semantic model (what an invoice *is*) is
  decoupled from jurisdictional rules (what makes it *valid here*) and from
  extraction (how to *read* it from a scan).
- **Standards-aligned.** Sitting on EN 16931 makes interop with UBL / Peppol /
  XRechnung / ZUGFeRD straightforward when needed.
- **Diffable & reviewable.** JSON in git, country-localized labels with full
  diacritics — readable to humans and to validators.

### Negative

- **File proliferation over time.** Each legal change adds a file; long-lived
  jurisdictions will accumulate many profiles. Mitigation: archive
  long-superseded profiles into a subdirectory if needed, keeping selection
  logic the same.
- **Discipline required.** Contributors must add a new file, not edit, when
  rules change. Mitigation: documented in `models/invoice/profiles/README.md`
  and enforced in code review.
- **Selection logic is non-trivial.** A profile resolver must implement the
  date-based selection above. Mitigation: implement once, share across
  document types.

### Neutral

- The same pattern is intended to apply to other document types
  (`models/receipt/`, `models/contract/`, …) with their own core + profiles.
  Profile filenames already include the document type prefix to keep this
  consistent (`invoice-cze-…`, `receipt-cze-…`).

## References

- EN 16931 — European standard on electronic invoicing
- UBL 2.1 — Universal Business Language
- Peppol BIS Billing 3.0
- ZUGFeRD / Factur-X / XRechnung
- ISO 3166-1 alpha-3 country codes
- ISO 4217 currency codes
- ISO 8601 date format
- JSON Schema Draft 2020-12
