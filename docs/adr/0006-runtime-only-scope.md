# ADR-0006: `portunix-ireco` is a runtime; authoring tools live in `portunix-reco-studio`

- **Status**: Accepted
- **Date**: 2026-05-10
- **Deciders**: zdendaku
- **Scope**: top-level scope and project boundary of `portunix-ireco` —
  what kinds of code, commands, and artifacts belong in this repository
  vs. in sibling repositories.
- **Relates to**:
  - [ADR-0003](0003-flexy-pipeline-two-step.md) — two-step parse →
    extract pipeline (runtime).
  - [ADR-0004](0004-ireco-config-schema.md) — `ireco.config.json` v1
    schema. The *shape* of the file is unchanged; the *authoring side*
    is what moves out of this repo.
  - [ADR-0005](0005-ireco-plugin-split.md) — worker/watcher plugin
    split. ADR-0005's text says *"Wizard (`init`) stays in the driver
    CLI"*. **This ADR supersedes that statement.** The wizard moves
    to `portunix-reco-studio`; the driver CLI in `portunix-ireco`
    keeps `parse`, `extract`, `run` and loses `init`.
  - `portunix-reco-studio` issue
    INT-037 (private repository)
    — the migration ticket on the receiving side.

## Context

`portunix-ireco` started as a single CLI (`ptx-ireco`) bundling both
the runtime pipeline (`parse / extract / run`) and the design-time
authoring tool (`init`, the `ireco.config.json` wizard introduced by
issue #002 / ADR-0004). Issue #003 / ADR-0005 then split the runtime
into two Portunix plugins (`ptx-ireco-worker`, `ptx-ireco-watcher`)
plus the thin driver CLI, but kept the wizard inside the driver.

In parallel, `portunix-reco-studio` exists explicitly as the
**design-time toolkit** of the Portunix recognition family. Its README
states: *"a design-time toolkit for building data extraction artifacts
(templates, rules, OCR configurations) from various input documents …
The artifacts produced here are consumed by runtime products such as
**portunix-reco** and **portunix-ireco** …"*.

The placement of the `ireco.config.json` wizard inside `portunix-ireco`
was therefore an architectural mis-placement — already noted as an
incident on this project — and is being corrected via the cross-repo
migration tracked in `portunix-reco-studio` INT-037.

This ADR captures the broader principle that follows from that
correction, so that future contributions don't reintroduce the same
mix-up.

Three forces shape the decision:

1. **Lifecycle separation.** Authoring artifacts (configs, templates,
   rules, OCR profiles) is an iterative, human-driven, occasional
   activity. Running the pipeline against those artifacts is an
   automated, repeated, often headless activity. Bundling them in one
   binary forces every runtime install to ship wizard UX, prompt
   libraries, schema-edit machinery, and interactive-only code paths
   it never executes.

2. **Deployment shape.** A typical production deployment of
   `portunix-ireco` is a Portunix plugin running headless against a
   watched directory — no TTY, no human, no wizard. Including
   authoring code there enlarges the attack surface and the install
   footprint for no operational benefit.

3. **Family-level coherence.** Portunix already has a runtime
   recognition product (`portunix-reco`) and a design-time studio
   (`portunix-reco-studio`). A second runtime (`portunix-ireco`)
   bundling its own authoring UI is asymmetric with the family it
   joined; symmetric placement makes the project boundary obvious to
   future contributors.

## Decision

**`portunix-ireco` contains runtime code only.** All design-time
authoring tools — wizards, schema-edit UIs, template/profile
generators, anything whose output is a configuration artifact later
read by a runtime — belong in `portunix-reco-studio`.

### What stays in `portunix-ireco`

The runtime side of every artifact this repo *consumes*:

- **The two-step parse → extract pipeline** (ADR-0003) and its Python
  API (`ptx_ireco.worker.api.pipeline`).
- **The plugin binaries** (`ptx-ireco-worker`, `ptx-ireco-watcher`)
  and their Portunix manifests (`plugin-worker.json`,
  `plugin-watcher.json`) per ADR-0005.
- **The driver CLI** `ptx-ireco`, restricted to runtime subcommands
  (`parse`, `extract`, `run`). The current `init` subcommand is
  removed (or replaced by a one-line breadcrumb pointing at
  `portunix-reco-studio` — see "Migration & deprecation" below).
- **Loading and validating** `ireco.config.json` at pipeline startup.
  The runtime needs to refuse to start on a malformed config; that
  validation step lives here. Whether the validator code is a
  vendored copy or a small shared library is decided in INT-037 via
  the studio-side ADR (see Q1 of INT-037).
- **Recipient match at extract time** (`recipient_match.py`). It is
  a runtime concern — it operates on OCR'd invoice text — and
  belongs with the extractor, not with the wizard's write-time
  normalization.
- **Models layout under `models/`** (templates, profiles, extraction
  rules consumed at runtime). The *authoring* of those assets that
  ireco-specific tooling might offer (none today) would move out;
  the *consumption* layout stays.
- **VIM-format reading and writing** at the runtime boundary. The
  format specification itself lives in the sibling
  `portunix-architecture` repo; ireco implements the runtime
  bindings.
- **Runtime-side documentation**: ADRs for runtime architecture,
  CLI reference for `parse|extract|run`, deployment and operational
  guides.

### What moves to `portunix-reco-studio`

The authoring side of `ireco.config.json` (per INT-037):

- Interactive wizard (`wizard.py`).
- JSON Schema canonical home and `$id` ownership.
- Validator implementation (write-time use; the runtime keeps either
  the same code as a vendored copy or a small reduced loader — to be
  decided in INT-037).
- `--from-file` non-interactive write path.
- Wizard-side tests and fixtures.
- Authoring documentation (`docs/cli/init.md` ports to the studio).

### What is *not* covered by this ADR

- **The schema specification itself** (ADR-0004). The shape of
  `ireco.config.json` v1 is unchanged. ADR-0004 stays the source of
  truth for the *shape*; the studio becomes the source of truth for
  the *authoring side* and for any future shape evolution beyond v1.
  ADR-0004 will gain a one-line footer note pointing here and at
  INT-037.
- **Future doc-type runtimes** (`receipt`, `delivery_note`,
  `purchase_order`). When their runtime extractors land, they land in
  this repo; their authoring UI (templates, recipient lists, mapping
  rules) lands in the studio. The split rule is the same.
- **`portunix-reco`'s own scope.** `portunix-reco` is independently
  a runtime; its relationship to the studio is governed by its own
  ADRs. This ADR only declares ireco's side.

### Decision rule for future contributions

A new feature for `portunix-ireco` belongs **here** iff it satisfies
all of the following:

1. It runs as part of a `parse / extract / run` invocation, or as a
   pre-flight check the runtime needs at startup.
2. It can run **headless** — no TTY, no interactive prompts, no
   editor UI.
3. Its inputs are either pipeline data (PDFs, `.vim.json`) or a
   pre-existing artifact authored elsewhere; it does not produce a
   reusable artifact intended for human editing.

If a feature fails any of (1)–(3), it is an authoring concern and
belongs in `portunix-reco-studio`. The studio may then expose it via
its CLI, MCP server, or VS Code extension as appropriate.

### Migration & deprecation

For users of the existing `ptx-ireco init` command:

- **Phase 1** (INT-037 land in studio, additive): both repos can
  author the file. No user-visible breakage.
- **Phase 2** (`portunix-ireco` strip): `ptx-ireco init` is replaced
  by a one-line breadcrumb that prints
  `"ptx-ireco init has moved. Use 'ptx-reco-studio ireco-config init'
  (see portunix-reco-studio INT-037)."` and exits non-zero.
- **Phase 3** (one release later): the breadcrumb command itself is
  removed. The deprecation note remains in `CHANGELOG.md` and in the
  `--help` output of the driver CLI.

The runtime side (`parse / extract / run` reading
`ireco.config.json`) is unchanged across all three phases.

## Consequences

### Positive

- **Clear project boundary.** A contributor reading this ADR knows
  where to put a new feature without guessing.
- **Smaller runtime install.** Wizard, prompt machinery, and
  authoring fixtures don't ship with the headless plugin binaries.
- **Symmetric with the rest of the family.** ireco's relationship to
  the studio mirrors reco's relationship to the studio: studio
  authors, runtimes consume.
- **Easier to keep `portunix-ireco` plugin-only.** ADR-0005's plugin
  shape is reinforced — the driver CLI is purely a façade over the
  worker's Python API, with no design-time concerns left to host.
- **Authoring UX can iterate independently.** The studio can ship
  wizard improvements, MCP exposure, and a future VS Code command
  without needing a runtime release.
- **Tester clarity.** Acceptance protocols for runtime issues can
  ignore wizard UX entirely; acceptance protocols for authoring
  issues live next to the studio's own protocols.

### Negative

- **Two repos to coordinate** for any cross-cutting change to the
  config (e.g. a v2 schema). Mitigation: the schema's source of
  truth is in the studio after INT-037; this repo only consumes it.
  Cross-cutting changes go through one cross-repo issue (the INT-037
  pattern) rather than churning ADRs in both places.
- **One more cross-repo dependency at install time** for users who
  want to author configs without already running the studio.
  Mitigation: studio is pip-installable as `ptx-reco-studio` and
  has a CLI; an authoring-only install does not require the VS Code
  extension or the gRPC server.
- **ADR-0005's wizard placement is overruled.** Resolved by
  marking ADR-0005 *Superseded in part by ADR-0006* in this repo's
  ADR README, and by leaving an explicit cross-reference here.

### Neutral

- **`recipient_match.py` stays here** (runtime concern), even though
  the wizard previously called it for write-time normalization. The
  studio gains its own write-time normalization helper (per INT-037
  Q2) — duplication is small and the divergence in concerns
  (precision/recall vs. UX hygiene) justifies it.
- **CHANGELOG impact.** The driver CLI's `init` subcommand removal
  is a breaking change at the CLI surface, but a non-event for any
  caller that already moved to the studio.

## Alternatives considered

- **Keep the wizard in `portunix-ireco` "because it knows the most
  about ireco's config".**
  Rejected: locality of knowledge isn't a placement rule when the
  artifact is itself shared across repos. The schema lives wherever
  it lives; both repos read it. What matters is *who runs the tool
  that produces the artifact*, and that is a design-time activity.
- **Move the *runtime* config loading into the studio too** (the
  studio publishes a "config service" both wizard and runtime call).
  Rejected: a runtime that needs a sibling package merely to parse
  its own startup config violates the "headless plugin" property
  ADR-0005 establishes. Runtimes must boot from a checked-out
  filesystem alone.
- **Create a third repo `portunix-ireco-tools` for authoring-only
  pieces.**
  Rejected: there is already a design-time home in the family
  (`portunix-reco-studio`). A second authoring repo splinters the
  family without solving anything the studio doesn't already solve.
- **Leave the wizard in `portunix-ireco` and just hide it from the
  Portunix plugin manifest.**
  Rejected: a hidden command is still shipped code, still tested,
  still maintained, and still ships on every plugin install.
  Hiding solves UX, not scope.

## Open questions

These are deliberately deferred to INT-037 / its ADR on the studio
side, listed here so contributors know where to look:

1. **Schema distribution mechanics** — vendored copy in this repo,
   imported package, or fetched URL? See INT-037 Q1.
2. **`recipient_match.py` split** — confirmation that runtime keeps
   matching, studio gets a separate write-time normalizer. See
   INT-037 Q2.
3. **Driver CLI breadcrumb wording / exit code** for the deprecation
   phase. Implementer's call; document in `CHANGELOG.md`.

## References

- [ADR-0003](0003-flexy-pipeline-two-step.md) — two-step pipeline
  (runtime).
- [ADR-0004](0004-ireco-config-schema.md) — `ireco.config.json` v1
  schema specification.
- [ADR-0005](0005-ireco-plugin-split.md) — worker/watcher plugin
  split (runtime architecture). Wizard-placement statement
  superseded by this ADR.
- `portunix-reco-studio` —
  README and INT-037 migration issue (private repository).
- VIM Format Specification —
  [`../../../portunix-architecture/docs/architecture/components/plugin-vim/vim-format.md`](../../../portunix-architecture/docs/architecture/components/plugin-vim/vim-format.md)
  (sibling repo).
