# Country Profiles

Country-specific invoice profiles that extend the core EN 16931 model in
`../core/`.

## Naming

- Directory name = **ISO 3166-1 alpha-3** country code, lowercase
  (e.g. `cze`, `deu`, `svk`, `aut`, `pol`).
- Filename = `invoice-<country>-<effective-date>.json`, where
  `<effective-date>` is ISO 8601 (`YYYY-MM-DD`).
  Example: `invoice-cze-2013-01-01.json`.

## Versioning

Each profile declares `valid_from` and optional `valid_to`. Legal changes
produce a **new file** rather than editing an existing one. Profile selection
is driven by the invoice's `issue_date` (or `tax_point_date` where relevant).

## Profile Structure

Profiles are JSON documents that describe:

- `country` — ISO 3166-1 alpha-3 code
- `valid_from` / `valid_to` — effective date range
- `extends` — relative path to the core schema being extended
- `language`, `currency_default`
- `identifiers` — country-specific identifiers (tax IDs, VAT IDs, etc.) with
  patterns, labels, and applicability
- `required_fields` — fields mandatory in this jurisdiction
- `required_one_of` — at-least-one-of constraints
- `field_aliases` — local-language labels for core fields
- `vat_categories` — applicable VAT categories and rates
- `notes` — free-form remarks

## Current Profiles

| Country | Code  | Versions                  |
|---------|-------|---------------------------|
| Czechia | `cze` | `2013-01-01`, `2025-01-01` |
| Germany | `deu` | `2025-01-01`              |
| Slovakia| `svk` | (TBD)                      |
