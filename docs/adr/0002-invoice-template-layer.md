# ADR-0002: Invoice template layer

- **Status**: Accepted
- **Date**: 2026-05-09
- **Deciders**: zdendaku
- **Scope**: `models/invoice/templates/`
- **Extends**: [ADR-0001](0001-invoice-profile-design.md)

## Context

ADR-0001 establishes a three-layer invoice model: core semantic schema,
country profiles versioned by effective date, and extraction rules
(flexylayouts).

In practice a large share of incoming invoices comes from a small set of
recurring issuers — utilities, telcos, software vendors, recurring suppliers.
Each such issuer typically uses a stable, recognizable invoice layout and
identifies itself with the same business and tax identifiers across all of
their invoices.

Treating every invoice as if it were unknown forces the pipeline to do
country detection, profile resolution, and full extraction from generic
flexylayouts on every document — even when a much more specific recognizer
already exists. There is room for a **fast-path** that checks "have we seen
this format before?" before the generic pipeline runs.

The fast-path needs to:

- Be cheap to add (drop in a new file when a new recurring issuer appears).
- Not invent a parallel semantic model. Validation, identifiers, VAT rules,
  and labels still belong to the country profile.
- Not become stale when the law changes. Profile versions evolve; the
  fast-path should remain valid as long as the issuer's *layout* is the same.

## Decision

Add a fourth layer **above** the existing three: `models/invoice/templates/`.

### What a template is

A template is a fingerprint-based recognizer for a specific recurring
invoice format. Its sole responsibility is to answer:

> Is this input an instance of a known template?

If yes, the template's `country` selects the country profile family for the
rest of the pipeline. The exact profile *version* is still resolved at
runtime by the invoice's `issue_date` per ADR-0001 — templates do not pin a
profile version.

A template carries **no semantic rules, no extraction logic, and no
defaults**. Those remain in profile and extraction layers. This keeps the
template surface small and the dependency direction one-way: templates
point at country profiles, profiles point at the core schema.

### File and directory conventions

- Templates live in `models/invoice/templates/`.
- Filename = `<guid>.json`, where `<guid>` is a **UUIDv4** generated when the
  template is created. Example:
  `a3f4e5b1-2c3d-4e5f-6789-abcdef012345.json`.
- A human-readable label is kept inside the file (`"name"` field); it is
  never used as an identifier.

### Template structure

```json
{
  "id": "<guid>",
  "name": "Issuer Name — variant (optional)",
  "country": "CZE",
  "fingerprint": {
    "match_rules": [
      { "type": "text_anchor", "value": "Issuer Name, a.s.", "weight": 1.0 },
      { "type": "tax_id",      "value": "12345678",          "weight": 1.0 }
    ],
    "match_threshold": 0.8
  }
}
```

Initial rule types: `text_anchor`, `tax_id`, `vat_id`. The set is
intentionally small and extensible (layout signatures, barcode IDs, etc.,
added when needed).

### Processing flow

1. Enumerate `templates/*.json` and run fingerprint matching against the
   input. Pick the highest-scoring template that meets its
   `match_threshold`.
2. If a template matched, use its `country`; otherwise detect the country
   from the document.
3. Resolve the profile under `profiles/<country>/` by `issue_date`
   (ADR-0001 selection rule).
4. Run extraction (flexylayouts).
5. Validate the result against core + profile.

The template layer is **optional** — every step from (2) onward works the
same whether a template matched or not.

### Lifecycle

- **Add**: generate a UUIDv4, drop in a new file. No registry update is
  required; the resolver enumerates the directory.
- **Modify**: in-place edits are allowed when refining the fingerprint
  (adding/removing/reweighting rules). The template still represents the
  same logical issuer/format.
- **Retire**: delete the file when the issuer's format is no longer seen.
  Historical processing is unaffected because the canonical model lives in
  core + profile, not in the template.

## Why GUID filenames

- Templates are matched **by fingerprint**, not by name — a stable,
  collision-free identifier is sufficient.
- New templates can be added without arguing over names or worrying about
  renames when an issuer rebrands.
- Any human context (issuer, variant) lives in the `name` field, which is
  visible in diffs and logs but does not constrain the filesystem.

## Alternatives considered

- **Skip templates entirely; treat every invoice as unknown.**
  Rejected: forces full generic extraction on every document, including
  high-volume recurring issuers where we already have strong signals.
- **Templates pin a specific profile version (path to file, not just country
  code).** Rejected: every legal change would require touching every
  affected template. Decoupling lets templates remain valid across legal
  changes that do not affect the issuer's format.
- **Put issuer defaults and extraction overrides into the template now.**
  Deferred. The minimal template is useful and unblocks recognition; richer
  templates can be added later as additional optional fields without
  breaking existing files.
- **Human-readable filenames (e.g. `cez-distribuce-electricity.json`).**
  Rejected per user direction: the filename has no role in matching, and
  GUIDs avoid renames during issuer rebrands and bikeshedding when adding
  templates.
- **Validity dates on templates (`valid_from` / `valid_to`).** Deferred. If
  an issuer changes their layout, simplest path is a new template alongside
  the old one — both can match independently. Validity windows can be
  added later if duplicate matches become a problem.

## Consequences

### Positive

- **Fast-path for recurring issuers.** High-volume cases benefit from a
  cheap recognition step before the generic pipeline runs.
- **Low cost to add.** A template is a small JSON file with a UUIDv4 name.
- **Resilient to legal changes.** Templates point at a country, not a
  profile version; profile evolution does not invalidate templates.
- **No semantic duplication.** All semantic rules stay in the profile;
  templates carry only identification.

### Negative

- **Match logic must be implemented.** The resolver needs to enumerate
  templates, score fingerprints, and apply a threshold. Mitigation: simple
  weighted-rule scoring is enough for the initial set of rule types.
- **Possible overlap.** Two templates could both match an input. Mitigation:
  pick the highest score; if tied, deterministic ordering (e.g. lexical
  GUID). Revisit if collisions become common in practice.
- **Templates without rich content may feel underused initially.** Accepted
  — the layer is intentionally minimal at first; richer templates are an
  open extension point.

### Neutral

- The same pattern applies to other document types (`models/receipt/`,
  `models/contract/`, …) when they acquire their own templates layer.

## References

- [ADR-0001](0001-invoice-profile-design.md) — invoice profile design
  (foundation this ADR extends)
- UUIDv4 (RFC 4122)
- ISO 3166-1 alpha-3 country codes
