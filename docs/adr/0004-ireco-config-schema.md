# ADR-0004: Per-directory `ireco.config.json` schema

- **Status**: Accepted (authoring moved — see *Migration note* below)
- **Date**: 2026-05-09
- **Migration note (2026-05-10)**: Authoring of `ireco.config.json`
  (interactive wizard + `--from-file` writer) moved to
  `portunix-reco-studio` per studio issue
  INT-037 (private repository)
  and this repo's issue [#005](../issues/done/005-remove-init-wizard-after-studio-migration.md).
  The schema **specification** in this ADR is unchanged and remains
  authoritative; only the *authoring tool* moved. The schema document
  is now vendored byte-equally in both repos. See studio
  ADR-0001 (private repository)
  for the placement decision and Q1–Q4 resolutions.
- **Deciders**: zdendaku
- **Scope**: directory-level configuration that drives `ptx-ireco`
  document processing
- **Relates to**: [ADR-0001](0001-invoice-profile-design.md),
  [ADR-0002](0002-invoice-template-layer.md),
  [ADR-0003](0003-flexy-pipeline-two-step.md);
  motivating issue [#002](../issues/done/002-init-wizard.md)

## Context

Up to ADR-0003 the pipeline is fully *per-file*: every invocation of
`ptx-ireco parse|extract|run` is given its inputs and outputs on the
command line, and the only persistent configuration in a working
directory is whatever lives under `models/`. There is no declared
contract that says "this directory processes invoices for these
recipients with this depth of extraction".

That gap shows up in three places:

1. **Operator workflow.** A directory typically holds incoming PDFs
   for a fixed set of recipients (often one tenant, sometimes many).
   Re-passing input/output paths and tenant context on every CLI call
   is repetitive and error-prone, and makes it hard to encode the
   *intent* of a directory in version control.
2. **Batch and CI use.** Automation has no machine-readable manifest
   to consult before running the pipeline; it has to encode operator
   knowledge as flags inside scripts.
3. **Tester reproducibility.** Per-issue acceptance protocols
   (ISSUE-DEVELOPMENT-METHODOLOGY.md) want a fixed set of inputs and a
   declared expected behavior. A per-directory config file provides a
   stable artifact to attach those expectations to.

Two further forces shape the schema:

- **Tenancy is bimodal in practice.** Some directories collect
  invoices for a single known recipient or a small fixed list of
  recipients (an accounting firm processing for a known set of client
  companies). Others ingest invoices addressed to any of many
  companies and only learn the recipient from each document
  ("multitenant for unknown recipients"). Conflating these into one
  shape — for example, a wildcard recipient entry — loses the
  distinction the operator actually wants to make.
- **Extraction depth varies per recipient.** For some recipients the
  invoice header is enough (totals into accounting); for others line
  items must be parsed (cost allocation, matching against existing
  purchase orders). The depth choice is a *per-recipient* property,
  not a global one, except in the multitenant case where there is no
  per-recipient context to attach it to.

The pipeline must also tolerate **directories without a config**
(existing per-file CLI usage from issue 001 stays unchanged) and
**non-invoice doc types** that are reserved in the schema today and
implemented in follow-up issues (`receipt`, `delivery_note`,
`purchase_order`).

## Decision

Introduce `ireco.config.json` as the canonical per-directory
configuration file for `ptx-ireco`, with the schema described below
and authored by the new `ptx-ireco init` wizard (issue #002).

### File location and lifecycle

- The file lives at the **root of the working directory** as
  `./ireco.config.json`. There is no recursive lookup; only the cwd
  is consulted.
- The file is **optional**. When absent, the pipeline behaves exactly
  as before ADR-0004 — purely per-file.
- The file is **versioned** via a top-level `version` integer. v1 is
  what this ADR specifies. Loading a higher version produces a clear
  "unsupported config version" error rather than a partial parse.
- Writes from the wizard are **atomic** (write-temp + rename) so a
  crash mid-write cannot corrupt an existing file.

### Schema (v1)

```json
{
  "$schema": "https://cassandragargoyle.example/ireco/config-1.0.json",
  "version": 1,
  "doc_types": ["invoice"],
  "io": {
    "input_dir": "./in",
    "output_dir": "./out"
  },
  "invoice": {
    "tenancy": "known",
    "recipients": [
      {
        "id": "example-buyer",
        "name": "PŘÍKLADOVÁ a.s.",
        "ico": "00000019",
        "dic": "CZ00000019",
        "extraction": {
          "depth": "items",
          "orders": {
            "source": "local",
            "path": "./orders/example-buyer/*.json"
          }
        }
      }
    ]
  }
}
```

Normative rules:

- `version`: integer, must be `1` for this ADR.
- `doc_types`: non-empty array of
  `"invoice" | "receipt" | "delivery_note" | "purchase_order"`. Only
  `invoice` is implemented; the other three are *reserved* — accepted
  by the schema and the wizard, but the pipeline raises a typed
  `NotImplementedError` (or exits non-zero) when asked to process
  them.
- `io.input_dir`, `io.output_dir`: strings, paths (absolute or
  relative to the config file). Their presence on disk is **not**
  enforced at write time — directories are populated later in the
  workflow.
- `invoice` is required iff `"invoice"` is in `doc_types`.
- `invoice.tenancy`: enum `"multitenant" | "known"`.
  - `"multitenant"` (= unknown / mixed recipients):
    `recipients` is absent or empty; `invoice.extraction` is required
    at the `invoice` level (one global depth + optional orders).
  - `"known"`: `recipients` contains 1..N entries; per-recipient
    `extraction` is required on every entry; top-level
    `invoice.extraction` is forbidden.
- Recipient entry:
  - `id`: short kebab-case slug, unique within the file.
  - `name`: human-readable string.
  - `ico`: 8-digit Czech IČO (digit count enforced; checksum
    deferred — see below).
  - `dic`: optional, format `^[A-Z]{2}[0-9A-Z]+$` if present.
  - `extraction.depth`: `"header" | "items"`.
  - `extraction.orders` is allowed only when `depth == "items"` and
    is itself optional. When present:
    - `source`: enum, currently only `"local"` (reserved enum value
      `"http"` for a future remote source).
    - `path`: glob string, syntactically validated; matching files
      need not exist at write time.

A formal JSON Schema document at `docs/schemas/ireco-config-1.0.json`
is the authoritative validator. The example in this ADR validates
against it.

### Why two tenancy modes instead of "everything is a list"

A "list with N entries, where N may be zero or any number" superficially
unifies the two cases but loses an essential distinction:

- In `known` mode, a recipient outside the configured list is a
  **signal of error** (mis-routed invoice, wrong directory) and the
  matcher should refuse or flag it.
- In `multitenant` mode, *any* recipient is acceptable and the
  matcher's job is purely to label the document, not to gatekeep.

Encoding the mode explicitly lets the matcher make this decision
without re-deriving it from list cardinality. It also makes the
wizard's UX honest: a one-recipient directory is `known/N=1`, not
"multitenant with one entry".

### Why depth lives on the recipient, not globally

For `known` tenancy, two recipients in the same directory may legit
need different depths — e.g. a holding company that wants header-only
for one subsidiary and full line items for another. Putting `depth`
on the recipient makes that representable without a second config
file. For `multitenant` tenancy there *is* no recipient slot, so a
single `invoice.extraction` block on the `invoice` object carries the
same shape (`depth` and optional `orders`).

### Pipeline integration

When `./ireco.config.json` is present:

- `ptx-ireco parse|extract|run` use `io.input_dir` / `io.output_dir`
  as defaults; explicit `-o` and positional arguments still win.
- For invoices in `known` mode, step 2 runs a recipient match against
  `invoice.recipients[]` (by `dic` first, falling back to `ico`, then
  `name`) and attaches the matched `recipient_id` to the VIM output.
  The exact placement of `recipient_id` in VIM is deferred to the
  implementer in issue #002 (top-level `document.recipient_id` vs. a
  new `semantic.entity` of type `recipient_link`); whichever is
  picked must be reflected in VIM-side docs.
- For `multitenant` mode, no `recipient_id` is attached; existing
  behavior is preserved.

When `./ireco.config.json` is absent, the pipeline behaves as it did
before this ADR — issue 001's acceptance criteria still pass without
modification.

### Authoring: interactive vs. machine

The schema supports both authoring paths via a single command:

- `ptx-ireco init` — interactive wizard. Section-by-section edit when
  a config already exists; full flow when not. Refuses to start on
  non-TTY stdin (and prints a hint pointing at `--from-file`).
- `ptx-ireco init --from-file <path>` — non-interactive validate +
  write. Suitable for CI and for the testing methodology's "prepare
  test data and scenarios" step.

Both paths share the same JSON Schema validator and the same atomic
write step.

## Alternatives considered

- **Embed the config inside `pyproject.toml` (`[tool.ptx-ireco]`).**
  Rejected: a working directory is not necessarily a Python project,
  and many target directories will hold only PDFs and outputs. The
  config also needs to evolve independently of the package metadata.
- **YAML or TOML for the config file.**
  Rejected for v1: the pipeline already standardizes on JSON
  (`.vim.json`, JSON model assets under `models/`), and JSON Schema
  tooling for validation is mature. YAML's superset semantics
  (timestamps, anchors) are more surface than this config needs.
- **One unified `recipients` list with a sentinel for the unknown /
  multitenant case** (e.g. `id: "*"`).
  Rejected: see *Why two tenancy modes* — wildcard-as-recipient
  conflates "any recipient is fine" with "this specific recipient",
  and the matcher logic for the two cases is genuinely different.
- **Global `extraction.depth` on the `invoice` object, with
  recipient overrides.**
  Rejected for `known` mode: simpler when all recipients agree, but
  collapses the override case into a second hidden mode and forces
  consumers to apply per-recipient overlay logic. Putting `depth` on
  the recipient is a flat representation with no overlay.
- **Auto-create `io.input_dir` / `io.output_dir` during the wizard.**
  Rejected: surprising side effect; the wizard is config authoring,
  not filesystem provisioning. A warning when paths don't exist is
  enough.
- **IČO checksum validation in v1.**
  Deferred: the modulo-11 IČO check is well-known but not core to the
  config's correctness — a typo'd IČO surfaces at recipient match
  time, and the schema's 8-digit constraint catches the most common
  errors. Add later if it becomes a real source of bugs.
- **Recipient name aliases / variant spellings** (`s.r.o.` vs. `spol.
  s r.o.`).
  Deferred to a follow-up issue. The matcher prefers `dic`/`ico` over
  `name`, so alias support is an optimization for fallback matching,
  not a correctness requirement for v1.

## Consequences

### Positive

- **Operator intent is captured in version control.** The directory's
  purpose (which doc types, which recipients, what depth) is a file,
  not tribal knowledge encoded in shell history.
- **Tester acceptance protocols have a stable artifact to point at.**
  Issue #002's tests can pin a fixture `ireco.config.json` and assert
  pipeline behavior end-to-end.
- **Backwards compatible.** Directories without `ireco.config.json`
  keep working as in ADR-0003.
- **Forward extensible.** Reserved enum values (`receipt`,
  `delivery_note`, `purchase_order`, `orders.source: "http"`) and the
  top-level `version` integer give future doc types and remote
  sources a clear place to land without breaking v1 consumers.
- **Clean tenancy semantics.** The `multitenant` vs. `known` split
  makes the matcher's gatekeeping role explicit instead of derived.

### Negative

- **One more file to author.** Operators must run `ptx-ireco init`
  (or hand-write the JSON) before getting the new conveniences. The
  wizard plus `--from-file` keeps the cost low, but it is not zero.
- **Two authoring paths to test.** Interactive and non-interactive
  flows must produce the same on-disk output for equivalent inputs.
  Mitigated by sharing the validator and the writer between paths.
- **Config drift.** A config that pins `recipients[]` can grow stale
  if the operator's tenant list changes and they forget to re-run
  `init --update`. The matcher's "unknown recipient" path in `known`
  mode surfaces this — but only after a real document is processed.

### Neutral

- **The same shape generalizes to other doc types.** When `receipt`
  or `delivery_note` extraction is implemented, each gets its own
  top-level key (`receipt`, `delivery_note`, …) parallel to
  `invoice`, with whatever sub-shape that doc type needs. The
  bimodal-tenancy idea may or may not apply per type.
- **Order matching** is a separately implemented feature; the schema
  only records *where to look* (`extraction.orders.path`). The
  matcher itself is a follow-up.

## References

- [Issue #002](../issues/done/002-init-wizard.md) — `ptx-ireco
  init` directory wizard
- [ADR-0001](0001-invoice-profile-design.md) — invoice profile
  design (consumed by step 2)
- [ADR-0002](0002-invoice-template-layer.md) — template layer
- [ADR-0003](0003-flexy-pipeline-two-step.md) — two-step pipeline
  that this config drives
- VIM Format Specification —
  [`../../../portunix-architecture/docs/architecture/components/plugin-vim/vim-format.md`](../../../portunix-architecture/docs/architecture/components/plugin-vim/vim-format.md)
  (sibling repo) — relevant for the `recipient_id` placement
  question deferred to issue #002
