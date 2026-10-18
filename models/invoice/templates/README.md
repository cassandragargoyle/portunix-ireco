# Invoice Templates

Templates recognize **specific recurring invoice formats** (typically a single
issuer's invoice layout) and provide an identification fast-path for the
processing pipeline.

A template does not contain semantic rules or extraction logic — those still
come from the profile and extraction layers. Its sole responsibility is to
answer: **"is this input an instance of a known template?"** If yes, the
template's `country` selects the country profile (which then resolves to the
right effective version by the invoice date).

See [`docs/adr/0002-invoice-template-layer.md`](../../../docs/adr/0002-invoice-template-layer.md)
for design rationale.

## Naming

- Filename = `<guid>.json`, where `<guid>` is a **UUIDv4** generated when the
  template is created.
  Example: `a3f4e5b1-2c3d-4e5f-6789-abcdef012345.json`.
- A human-readable name is kept inside the file (`"name"` field) for
  documentation and debugging — it is never used as an identifier.

## Template Structure

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://cassandragargoyle.dev/portunix-ireco/models/invoice/templates/<guid>.json",
  "id": "<guid>",
  "name": "Issuer Name — invoice variant (human-readable, optional)",
  "country": "CZE",
  "fingerprint": {
    "match_rules": [
      { "type": "text_anchor", "value": "Issuer Name, a.s.", "weight": 1.0 },
      { "type": "tax_id",      "value": "12345678",          "weight": 1.0 },
      { "type": "vat_id",      "value": "CZ12345678",        "weight": 0.5 }
    ],
    "match_threshold": 0.8
  }
}
```

### Fields

- `id` — UUIDv4, identical to the filename stem
- `name` — optional human-readable label (issuer + variant)
- `country` — ISO 3166-1 alpha-3 code; selects the country profile family.
  The exact profile version is resolved at runtime by the invoice's
  `issue_date` (see ADR-0001), so templates do **not** need to be updated
  when the law changes.
- `fingerprint.match_rules` — list of rules; each contributes a weight if
  satisfied. Initial rule types:
  - `text_anchor` — literal/normalized text present on the document
  - `tax_id` / `vat_id` — issuer identifier present and matching `value`
  - (extensible — layout signatures, barcode IDs, etc., added as needed)
- `fingerprint.match_threshold` — minimum total weight (out of the sum of
  rule weights) for the template to be considered a match.

## Why GUID Filenames?

- Templates are matched **automatically** by fingerprint — humans don't pick
  them by name. A stable, collision-free identifier is enough.
- New templates can be added without bikeshedding over names or worrying
  about renames when an issuer rebrands.
- The `name` field still serves humans reading diffs or logs.

## Lifecycle

- **Add**: generate a UUIDv4, drop in a new file. No registry update needed —
  the resolver enumerates `templates/*.json`.
- **Modify**: edit in place if the change is a fingerprint refinement
  (adding/removing/reweighting rules). The template still represents the
  same logical issuer/format.
- **Retire**: delete the file when the issuer's format is no longer
  encountered. Historical processing of older documents is unaffected
  because templates only assist matching — the canonical model lives in
  core + profile.

The minimal template is intentionally narrow at this stage. Future extensions
(known-issuer defaults, extraction overrides, validity dates) may be added
as additional fields without breaking existing templates.
