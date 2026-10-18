# Issue 002 — `ptx-ireco init` directory wizard for document processing config

- **Status**: done
- **GitHub**: [#2](https://github.com/cassandragargoyle/portunix-ireco/issues/2)
- **Closed**: 2026-05-09
- **Priority**: high
- **Area**: cli, config
- **Related**: [ADR-0004](../../adr/0004-ireco-config-schema.md) —
  authoritative schema and rationale for `ireco.config.json`;
  [ADR-0001](../../adr/0001-invoice-profile-design.md),
  [ADR-0002](../../adr/0002-invoice-template-layer.md),
  [ADR-0003](../../adr/0003-flexy-pipeline-two-step.md).
- **Branch**: `feature/issue-002-init-wizard`

## Goal

Add a CLI wizard that **creates or updates** an `ireco.config.json` file
in the current working directory. The config declares which document
types are processed in this directory, where input/output PDFs live,
and — for invoices — which recipients (tenants) the directory serves
and what depth of extraction each recipient requires.

```text
$ cd /some/customer/dir
$ ptx-ireco init
  → walks user through: doc types → I/O dirs → invoice tenancy mode →
    per-recipient extraction depth → optional order-matching source
  ⇒ writes ./ireco.config.json (or updates an existing one)
```

The same JSON shape MUST be loadable non-interactively via
`ptx-ireco init --from-file <path>` (validation + write, no prompts).

## Background

Today `ptx-ireco parse|extract|run` operates per-file with all knobs
passed on the command line. There is no per-directory contract that
states *what kind of work this directory does*: which doc types, which
recipient(s) the invoices belong to, and whether line items are needed.
That makes batch automation, CI, and tester reproducibility harder.

This issue introduces a directory-level configuration file plus the
wizard that authors it. The pipeline (`parse`/`extract`/`run`) is wired
to **read** `ireco.config.json` from the working directory when present
so that operators don't have to re-pass flags on every invocation.

## Scope

### In scope

1. **Config schema** — a JSON schema for `ireco.config.json` covering
   doc-type selection, I/O paths, invoice tenancy mode, recipients,
   per-recipient extraction depth, and optional order-matching source.
2. **`ptx-ireco init` command** — interactive wizard that:
   - Creates `ireco.config.json` when none exists.
   - Loads the existing file and offers section-by-section edit when
     one exists (per-section "keep / change" prompt; existing values
     shown as defaults).
   - Validates the result against the schema before writing.
   - Writes atomically (write to temp file, then `os.replace`).
3. **Non-interactive mode** — `ptx-ireco init --from-file <path>`
   reads a candidate JSON, validates against the schema, and writes
   it to `./ireco.config.json` without prompting. Exits non-zero on
   validation failure with a human-readable error pointing at the
   offending JSON path.
4. **Pipeline integration (invoices only)** — when the working
   directory contains a valid `ireco.config.json`:
   - `ptx-ireco parse|extract|run` reads `input_dir`/`output_dir` as
     defaults (still overridable on the CLI).
   - For invoices, the resolved recipient list is exposed to the
     extractor so step 2 can attach `recipient_id` metadata to the
     `semantic` layer (the matcher itself is implemented as a thin
     name/IČO/DIČ comparison against `recipients[]`; cross-doc
     recipient learning is OUT of scope).
5. **Wizard UX requirements** — see *Wizard flow* below; the prompts
   MUST be terminal-only (no GUI), tolerate `Ctrl-C` (no partial file
   left on disk), and degrade gracefully on non-TTY stdin (in that
   case the wizard refuses to start and points the user at
   `--from-file`).

### Out of scope

- Implementation of `receipt` / `delivery_note` / `purchase_order`
  extraction. The wizard reserves these as selectable doc types and
  records the choice in the config; the pipeline simply rejects them
  with `NotImplementedError` until follow-up issues land.
- Order-matching itself. The wizard captures the orders directory /
  glob; consuming it during extraction is a follow-up issue.
- Cross-directory or central registry of recipients. The recipient
  list lives only in this directory's `ireco.config.json`.
- Migration of existing per-file CLI usage; the new flags are purely
  additive.

## `ireco.config.json` schema (normative)

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

Schema rules the implementation MUST enforce:

- `version`: integer, currently `1` (forward-compat).
- `doc_types`: non-empty array of `"invoice" | "receipt" |
  "delivery_note" | "purchase_order"`. At least one MUST be present.
- `io.input_dir`, `io.output_dir`: strings, paths (absolute or
  relative to the config file). The wizard MUST NOT auto-create them
  but SHOULD warn if they don't exist on disk at write time.
- `invoice` is REQUIRED iff `"invoice"` is in `doc_types`.
- `invoice.tenancy`: `"multitenant" | "known"`.
  - `"multitenant"` (= unknown / mixed recipients):
    `recipients` MUST be absent or empty; `invoice.extraction` is
    REQUIRED at the `invoice` level (one global `depth`/`orders`
    block).
  - `"known"`: `recipients` MUST contain 1..N entries; per-recipient
    `extraction` is REQUIRED on every entry; top-level
    `invoice.extraction` MUST be absent.
- Recipient entry:
  - `id`: short kebab-case slug, unique within the file.
  - `name`: human-readable string.
  - `ico`: 8-digit Czech IČO string (validated as 8 digits; checksum
    not required for v1).
  - `dic`: optional, format `^[A-Z]{2}[0-9A-Z]+$` if present.
  - `extraction.depth`: `"header" | "items"`.
  - `extraction.orders` is REQUIRED iff `depth == "items"` AND the
    user opted in during the wizard. If absent, line-item extraction
    runs without order matching.
  - `extraction.orders.source`: currently only `"local"` (reserved
    enum for future `"http"`).
  - `extraction.orders.path`: glob string, validated as a syntactically
    valid glob; existence of matching files is NOT checked at write
    time (the directory may be populated later).

A formal JSON Schema document MUST be checked in at
`docs/schemas/ireco-config-1.0.json` and referenced from the config's
`$schema` field. The wizard validates against that document.

## Wizard flow (interactive, normative steps)

```text
Step 1  Select document types          → doc_types
Step 2  Input directory                 → io.input_dir
Step 3  Output directory                → io.output_dir
        (only if "invoice" ∈ doc_types)
Step 4  Invoice tenancy                 → invoice.tenancy
        ├─ multitenant
        │   Step 5a  Global extraction depth     → invoice.extraction.depth
        │   Step 6a  Match against orders? (y/n) → invoice.extraction.orders
        │            (asked only when depth == "items")
        └─ known
            Step 5b  How many recipients? (1..N)
            Step 6b  For each recipient i in 1..N:
                       id, name, ico, dic
                       extraction.depth (header | items)
                       if items: match against orders? path/glob
Step 7  Review summary, confirm write   → ireco.config.json
```

Update mode (config already exists):

- Load and parse the existing file. On parse/validation failure, the
  wizard MUST refuse to update and tell the user to fix or delete the
  file (does NOT silently overwrite).
- Present a section menu: `[1] doc types  [2] I/O paths
  [3] invoice tenancy  [4] recipients  [5] write & exit  [q] quit`.
- Each section uses existing values as defaults. `q` exits WITHOUT
  writing.

## Acceptance criteria

### A. Config schema and validation

- [ ] `docs/schemas/ireco-config-1.0.json` exists and validates the
      example block in this issue.
- [ ] All schema rules listed above are enforced; invalid configs are
      rejected with an error message that names the offending JSON
      path (e.g. `invoice.recipients[0].ico: must be 8 digits`).
- [ ] `version` mismatch (e.g. `2`) produces a clear "unsupported
      config version" error rather than a generic schema failure.

### B. `ptx-ireco init` — create flow

- [ ] Run in an empty directory: completes the full wizard flow, writes
      a valid `ireco.config.json`, exits 0.
- [ ] Selecting `multitenant` does NOT prompt for recipients and the
      resulting file has no `invoice.recipients` key.
- [ ] Selecting `known` with N=1 and N=3 both succeed and produce
      valid files.
- [ ] Choosing `depth=items` and answering "yes" to order matching
      records `extraction.orders.source: "local"` and the user-supplied
      `path`.
- [ ] Choosing `depth=header` does NOT prompt for orders.
- [ ] `Ctrl-C` at any prompt leaves no `ireco.config.json` (and no
      stale tempfile) in the working directory.

### C. `ptx-ireco init` — update flow

- [ ] Run with an existing valid `ireco.config.json`: section menu is
      shown, each section's existing values appear as defaults.
- [ ] Editing only one section preserves all other sections byte-equal
      where the schema allows ordering to be preserved (key order MAY
      be canonicalized; values for untouched sections MUST be
      preserved).
- [ ] Run against an invalid existing file: wizard refuses, prints the
      validation error and exits non-zero. The file on disk is NOT
      modified.
- [ ] Choosing `[q] quit` from the section menu exits 0 and does NOT
      modify the file on disk.

### D. `--from-file` non-interactive mode

- [ ] `ptx-ireco init --from-file good.json` validates and writes
      `./ireco.config.json`, exits 0.
- [ ] `ptx-ireco init --from-file bad.json` (schema-invalid) exits
      non-zero with a JSON-path-pointed error and does NOT write the
      output file.
- [ ] `--from-file` works on a non-TTY stdin (e.g. from CI). The
      interactive wizard, by contrast, refuses to start on non-TTY
      stdin and prints a hint pointing at `--from-file`.

### E. Pipeline integration (invoice only)

- [ ] When `ireco.config.json` is present in cwd, `ptx-ireco parse`
      and `ptx-ireco extract` use `io.input_dir` / `io.output_dir` as
      defaults; explicit `-o` / positional paths still win.
- [ ] When `invoice.tenancy == "known"`, `extract` emits a
      `recipient_id` field on the matched recipient inside the
      `semantic` layer (or in a clearly documented top-level
      `document.recipient_id`). Choice of placement MUST be reflected
      in the VIM-bound docs touched by this issue.
- [ ] When `invoice.tenancy == "multitenant"`, no `recipient_id` is
      attached and the existing extraction behavior is preserved.
- [ ] `doc_types` containing `receipt`, `delivery_note`, or
      `purchase_order` is *accepted* by the wizard but the pipeline
      raises `NotImplementedError` (or exits with code 3 and a clear
      message) when asked to process such a file.

### F. Tests

- [ ] Unit tests for: schema validation (good and bad fixtures, one
      per rule), wizard step transitions (using a scripted-input
      harness), atomic write behaviour (simulated crash mid-write
      leaves no partial file).
- [ ] Integration test: `ptx-ireco init --from-file fixtures/known-3.json`
      produces a file byte-equal to a checked-in expected output
      (modulo whitespace/key ordering as documented).
- [ ] Integration test: with a known-tenancy config in cwd, running
      `ptx-ireco extract` against the existing
      `samples/invoice/flowii-FA_26050001.pdf.vim.json` produces a
      semantic layer that includes the matched `recipient_id`
      (`example-buyer` or whatever the fixture defines).
- [ ] Regression test: running the existing two-step pipeline in a
      directory with NO `ireco.config.json` behaves exactly as before
      (issue 001 acceptance still passes).

### G. Documentation

- [ ] `docs/cli/init.md` (new) documents the wizard, the schema, and
      examples for both tenancy modes.
- [ ] `docs/schemas/ireco-config-1.0.json` is referenced from the CLI
      doc and from the schema file's own `$id`.
- [ ] `README.md` (root) gets a short section pointing at the new
      command.
- [ ] If a config-schema ADR is authored as part of this work, it is
      linked from this issue and from the CLI doc.

## Open architectural questions (please resolve before / during impl)

1. **Where does `recipient_id` live in VIM output** — top-level
   `document.recipient_id`, or as a `semantic.entity` of a new
   `recipient_link` type? Either is defensible (see ADR-0004); the
   implementer should pick one and update VIM-side docs (the spec
   lives in the sibling `portunix-architecture` repo per issue 001).
2. **Multi-locale recipient names** — the wizard accepts a single
   `name` string. Aliases (e.g. `"s.r.o."` vs `"spol. s r.o."`) are
   deferred per ADR-0004. If the implementer needs them for the
   matcher, propose a follow-up issue rather than expanding scope here.

## Implementation hints (non-binding)

- Reuse the existing CLI machinery in `src/ptx_ireco/cli.py` (argparse
  subparsers). `init` slots in alongside `parse` / `extract` / `run`.
- For schema validation pick a maintained library that emits JSON
  pointer paths in errors (`jsonschema` Draft 2020-12 is fine).
- For the section-edit menu in update mode, a tiny in-house prompt
  loop is enough — avoid adding a heavy TUI dependency for v1.
- Keep the wizard's IO layer behind a thin `Prompt` interface so unit
  tests can drive it deterministically with scripted answers.

## Definition of done

- All acceptance criteria above are checked.
- ADR-0004 (config schema) is moved from `Proposed` to `Accepted`
  status, or any deviation is captured in a superseding ADR.
- A tester acceptance protocol per ISSUE-DEVELOPMENT-METHODOLOGY.md is
  recorded under `docs/testing/acceptance-002.md` with `STATUS: PASS`.
- Branch is merged into `main` only after that protocol exists.
- This issue file is moved to `docs/issues/done/` and the
  status row is updated in `docs/issues/README.md` (per the methodology).

---

> **Authoring migrated to `portunix-reco-studio` INT-037 on 2026-05-10.**
> The wizard, validator (write-time), and `--from-file` writer that
> this issue produced are now part of the studio under
> `ptx_reco_studio.ireco_config` / `ptx-reco-studio ireco-config init`.
> The runtime side of `ireco.config.json` (loading and recipient
> matching during extraction) stays in this repo, unchanged. The
> wizard removal in this repo is tracked as issue
> [#005](005-remove-init-wizard-after-studio-migration.md).
