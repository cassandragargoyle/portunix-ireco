# Acceptance Protocol — Issue #002

**Issue**: `ptx-ireco init` directory wizard for document processing config
**Branch**: `feature/issue-002-init-wizard`
**Tester**: zdendaku (QA / Test Engineer role)
**Date**: 2026-05-09
**Testing OS**: Ubuntu 25.10 "Questing Quokka" (Linux 6.17.0-23-generic) — host (no container)
**Python**: 3.12.13 (.venv)

## Test Summary

- Total test scenarios: 86 (78 automated pytest + 8 manual CLI)
- Passed: 86
- Failed: 0
- Skipped: 0

## Test Results

### Functional Tests

#### A. Config schema and validation

- [x] **A.1** Schema document validates the example block in the issue
      (`test_example_in_issue_validates`).
- [x] **A.2** Invalid configs are rejected with messages naming the
      offending JSON path — verified across 23 unit tests covering
      every schema rule (e.g.
      `invoice.recipients[0].ico: must be 8 digits`).
- [x] **A.3** `version` mismatch produces an explicit "unsupported
      config version N (this build understands version 1)" error
      (`test_version_must_be_one`, manual T6).

#### B. `ptx-ireco init` — create flow

- [x] **B.1** Empty-dir create produces a valid `ireco.config.json`
      and exits 0 (`test_wizard_creates_multitenant_header`).
- [x] **B.2** `multitenant` skips the recipients prompt and the
      written file has no `invoice.recipients` key
      (`test_wizard_creates_multitenant_header`,
      `test_wizard_creates_multitenant_items_with_orders`).
- [x] **B.3** `known` with N=1 and N=3 both succeed
      (`test_wizard_known_with_one_recipient`,
      `test_wizard_known_with_three_recipients`).
- [x] **B.4** `depth=items` + "yes" records
      `extraction.orders.source: "local"` and the user-supplied path.
- [x] **B.5** `depth=header` does not prompt for orders
      (`test_wizard_header_does_not_prompt_for_orders` — assertion is
      that no extra answer is consumed from the scripted queue).
- [x] **B.6** `Ctrl-C` (simulated by raising `KeyboardInterrupt` from
      the prompt) leaves no file and no stale tempfile in the working
      directory (`test_wizard_ctrl_c_leaves_no_partial_file`).

#### C. `ptx-ireco init` — update flow

- [x] **C.1** Update mode shows the section menu with existing values
      as defaults (`test_wizard_update_io_only_preserves_other_sections`).
- [x] **C.2** Editing one section preserves other sections
      byte-equivalent in semantics (`test_wizard_update_io_only_preserves_other_sections`
      asserts `after["doc_types"] == original["doc_types"]` and
      `after["invoice"] == original["invoice"]`).
- [x] **C.3** Existing invalid file is refused; on-disk content
      unchanged; non-zero exit
      (`test_wizard_refuses_invalid_existing_config`).
- [x] **C.4** `[q] quit` exits cleanly without modifying the file
      (`test_wizard_update_quit_preserves_file`).

#### D. `--from-file` non-interactive mode

- [x] **D.1** `init --from-file good.json` validates and writes
      `./ireco.config.json`, exits 0
      (`test_from_file_writes_byte_equal_canonical_form`, manual T2).
- [x] **D.2** Schema-invalid input exits non-zero and does NOT write
      the output file
      (`test_from_file_rejects_invalid_and_does_not_write`,
      `test_from_file_rejects_unsupported_version`).
- [x] **D.3** `--from-file` works on non-TTY stdin (verified by
      pytest's monkeypatched cwd, where stdin is not a TTY); the
      interactive wizard refuses to start on non-TTY stdin and prints
      the documented hint pointing at `--from-file` (manual T4).

#### E. Pipeline integration (invoice only)

- [x] **E.1** When `ireco.config.json` is present, `parse` and
      `extract` use `io.input_dir` / `io.output_dir` as defaults;
      explicit `-o` still wins (manual T5).
- [x] **E.2** `tenancy=known` matched recipient is attached as
      `document.recipient_id` in the VIM output
      (`test_known_tenancy_attaches_recipient_id` against the Flowii
      sample — buyer IČO `00000019` resolves to `example-buyer`).
      Placement chosen: top-level `document.recipient_id` (issue #002
      open question 1; rationale documented in `docs/cli/init.md`
      "Pipeline integration" section).
- [x] **E.3** `tenancy=multitenant` adds no `recipient_id`; existing
      extraction behavior is preserved
      (`test_no_options_means_no_recipient_id`).
- [x] **E.4** `doc_types` containing reserved values
      (`receipt`/`delivery_note`/`purchase_order`) is accepted by
      schema/wizard but the pipeline exits with code `3` and a clear
      message (manual T3 — both `extract` and `run` exit 3).

#### F. Tests

- [x] **F.1** Unit tests cover schema validation (23 cases), wizard
      step transitions via scripted prompt harness (10 cases), and
      atomic write incl. simulated mid-write crash (9 cases).
- [x] **F.2** Integration test produces a file equivalent to the
      checked-in expected output
      (`test_from_file_writes_byte_equal_canonical_form`).
- [x] **F.3** Integration test with a known-tenancy config in cwd
      against the existing `flowii-FA_26050001.pdf.vim.java.json`
      sample produces a result with the matched `recipient_id`
      (`test_known_tenancy_attaches_recipient_id`).
- [x] **F.4** Regression: existing two-step pipeline tests
      (`test_extract_flowii_sample` etc.) continue to pass with no
      `ireco.config.json` present; no behavior change without a
      config.

#### G. Documentation

- [x] **G.1** `docs/cli/init.md` documents the wizard, schema, and
      examples for both tenancy modes (141 lines).
- [x] **G.2** `docs/schemas/ireco-config-1.0.json` is referenced from
      the CLI doc and carries an `$id` field.
- [x] **G.3** Root `README.md` gained an `init` section pointing at
      `docs/cli/init.md`.
- [x] **G.4** ADR-0004 status flipped from `Proposed` to `Accepted`.

### Regression Tests

- [x] All 35 pre-existing tests (parse, extract, profile_resolver,
      template_match, flexy_engine) continue to pass unchanged.
- [x] `extract_file()` keeps its prior call signature; the new
      `options` parameter is keyword-only and defaults to `None`,
      preserving every existing call site.
- [x] When `ireco.config.json` is absent, `parse`/`extract`/`run`
      behave exactly as before — no `recipient_id` is attached and no
      defaults are pulled from any config.
- [x] Cross-platform compatibility: `os.replace` provides POSIX-atomic
      rename, best-effort atomic on Windows; no platform-specific
      paths used. (Linux verified here; Windows verification deferred
      to `tester-windows` if requested by the architect.)

### Manual CLI scenarios

| ID  | Scenario                                                       | Result |
|-----|----------------------------------------------------------------|--------|
| T1  | Full pytest suite (78 tests, regression + new)                 | PASS   |
| T2  | `init --from-file` writes byte-equal canonical content         | PASS   |
| T3  | Reserved doc_type triggers exit code 3 in `extract` and `run`  | PASS   |
| T4  | Wizard refuses non-TTY stdin with documented hint              | PASS   |
| T5  | `parse` reads `io.output_dir` from config; explicit `-o` wins  | PASS   |
| T6  | Invalid config (bad version) on `extract` triggers exit 4      | PASS   |
| T7  | Documentation files present and cross-linked                   | PASS   |
| T8  | Pytest timing: 78 tests in 0.29s                               | PASS   |

## Final Decision

**STATUS**: PASS

All acceptance criteria A–G are met. All 78 automated tests pass. All 8
manual CLI scenarios pass. No regressions in pre-existing behavior. The
implementation matches the schema and wizard flow specified in the
issue and ADR-0004; the deferred VIM placement question for
`recipient_id` is resolved as `document.recipient_id` (top-level), with
the choice documented in `docs/cli/init.md`.

**Approval for merge**: YES
**Date**: 2026-05-09
**Tester signature**: zdendaku (QA/Test Engineer role)
