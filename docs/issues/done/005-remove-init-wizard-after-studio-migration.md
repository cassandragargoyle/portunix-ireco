# Issue 005 — Remove `ptx-ireco init` wizard (authoring migrated to studio)

- **Status**: ✅ done
- **GitHub**: [#5](https://github.com/cassandragargoyle/portunix-ireco/issues/5)
- **Created**: 2026-05-10
- **Closed**: 2026-05-10
- **Priority**: high
- **Area**: cli, config, cleanup
- **Branch**: `feature/issue-005-remove-init-wizard` (merged + deleted)
- **Acceptance protocol**: [`docs/testing/acceptance-005.md`](../../testing/acceptance-005.md) — STATUS: PASS
- **Related**:
  - Sibling studio issue INT-037 (private repository) — moved authoring of `ireco.config.json` to `portunix-reco-studio`
  - [ADR-0004](../../adr/0004-ireco-config-schema.md) — schema
    specification (stays in this repo as the authoritative spec; the
    schema itself is unchanged, only the *authoring tool* moved)
  - This issue's predecessor
    [#002](002-init-wizard.md) — the wizard whose authoring
    side is now removed here

## Goal

Now that the `ireco.config.json` authoring tooling lives in
`portunix-reco-studio` (per studio INT-037, merged 2026-05-10), this
repo should no longer ship the wizard. `portunix-ireco` becomes a
**pure runtime consumer** of the file:

- Continues to **load and validate** `ireco.config.json` on
  `parse|extract|run` exactly as today.
- No longer **authors** the file. Users are pointed at
  `ptx-reco-studio ireco-config init` instead.

## Scope

### In scope

1. **Remove the wizard module.**
   - Delete `src/ptx_ireco/config/wizard.py`.
   - Delete `tests/unit/test_config_wizard.py`.

2. **Replace `ptx-ireco init` with a deprecation breadcrumb.**
   - Keep the subcommand visible in `--help` so `ptx-ireco init`
     doesn't error out as an unknown command.
   - On invocation it prints a single line pointing at the studio
     replacement and exits with a non-zero status (per studio INT-037
     acceptance criterion D.2).
   - Remove the `--from-file <path>` flag (the writer it called is
     gone with the wizard module).

3. **Trim wizard imports from CLI.**
   - In `src/ptx_ireco/cli/main.py`, remove imports of
     `Prompt`, `WizardAborted`, `WizardOptions`, `run_wizard`,
     `write_from_file` and the `WizardAborted`/`InvalidConfigError`
     branches that are no longer reachable from `_cmd_init`.

4. **Update `ptx_ireco.config.__init__` docstring.**
   - Remove the bullet that advertises
     `ptx_ireco.config.wizard`. The package now exposes only
     loader + validator + recipient matcher.

5. **Footer note in ADR-0004.**
   - Append a short "Authoring moved to `portunix-reco-studio` in
     INT-037 on 2026-05-10" status entry. The schema spec itself is
     unchanged; only the location of the *authoring tool* is.

6. **Footer note in done/002-init-wizard.md.**
   - Append "Authoring migrated to `portunix-reco-studio` INT-037 on
     2026-05-10" so a reader looking at the original issue is
     redirected to the new home.

### Out of scope

- Schema changes (still v1, byte-equal across both repos).
- Removing or moving `loader.py`, `validator.py`, `schema.py`,
  `recipient_match.py` — they all stay in this repo because runtime
  needs them.
- Removing the vendored `docs/schemas/ireco-config-1.0.json` — the
  runtime validator references it; CI byte-equality is enforced
  studio-side via `test_schema_byte_equal_to_ireco_runtime`.

## Acceptance criteria

- [ ] `src/ptx_ireco/config/wizard.py` does not exist.
- [ ] `tests/unit/test_config_wizard.py` does not exist.
- [ ] `ptx-ireco init` (any args, including `--from-file <whatever>`)
      prints a one-line pointer at the studio command and exits
      non-zero.
- [ ] `ptx-ireco --help` still lists `init` (so users see the
      breadcrumb instead of "unknown command").
- [ ] `ptx-ireco parse|extract|run` still load + validate
      `ireco.config.json` correctly. Issue #002 runtime acceptance
      bullets (E1–E4) still pass.
- [ ] `tests/unit/test_config_validator.py`, `test_config_loader.py`,
      `test_recipient_match.py` all pass unchanged.
- [ ] ADR-0004 has a "migration to studio" footer.
- [ ] `done/002-init-wizard.md` has the same footer.
- [ ] No leftover wizard imports anywhere in `src/`.

## Tester verification path

1. `pytest tests/` — full suite green; the suite no longer collects
   the wizard test file.
2. `ptx-ireco init` → prints pointer, exits non-zero.
3. `ptx-ireco init --from-file anything.json` → also prints pointer
   (the flag is gone; argparse should reject it with usage text, or
   the stub ignores it — either is fine, as long as nothing tries to
   write a config).
4. `ptx-ireco parse <pdf>` against an existing `ireco.config.json` in
   cwd still picks up the I/O paths. (Smoke run.)
5. Acceptance protocol at `docs/testing/acceptance-005.md` —
   STATUS: PASS — before merge to main.
