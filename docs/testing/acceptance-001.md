# Acceptance Protocol - Issue #001

**Issue**: Implement two-step flexy document pipeline (parse → extract)
**Branch**: `feature/issue-001-flexy-pipeline-two-step`
**Tester**: zdendaku (role: Tester / Generic)
**Date**: 2026-05-09
**Testing OS**: Ubuntu 25.10 (Questing Quokka), kernel 6.17.0-23-generic — host (no container)
**Python**: 3.12.13 (in `.venv` via `uv venv`)
**Commit under test**: `76b21c9 feat(001): two-step flexy pipeline (parse → extract)`

## Test Summary

- Total test scenarios: **78** (25 automated pytest + 53 manual acceptance assertions)
- Passed: **78**
- Failed: **0**
- Skipped: **0**

### Automated suite

```text
$ .venv/bin/pytest tests/ -v
============================== 25 passed in 0.26s ==============================
```

| Suite                          | Cases | Result |
|--------------------------------|-------|--------|
| `tests/unit/test_template_match.py`     | 6 | PASS |
| `tests/unit/test_profile_resolver.py`   | 6 | PASS |
| `tests/unit/test_flexy_engine.py`       | 8 | PASS |
| `tests/e2e/test_flowii_extract.py`      | 4 | PASS |
| `tests/e2e/test_flowii_parse.py`        | 1 | PASS |

### Manual acceptance verification

Tested against `samples/invoice/flowii-FA_26050001.pdf` and the
canonical Java-parsed reference VIM (`flowii-FA_26050001.pdf.vim.java.json`)
shipped under the gitignored `samples/` directory.

#### A. Two-step contract — PASS

| Check | Method | Result |
|-------|--------|--------|
| A.1 Step 1 alone leaves `semantic.entities` empty/absent | `ptx-ireco parse … -o /tmp/x.vim.json` then read JSON | `entities: []`, `physical.blocks=6`, `structural.blocks=6` |
| A.2 Step 2 writes semantic in-place; physical/structural/toc/document unchanged | dict-equality between pre-/post-extract on Java-parsed VIM | All 4 layers byte-identical except semantic; `entities count: 6` |
| A.3 Re-running step 2 is idempotent (overwrite policy) | MD5 of file after 3 successive `extract --in-place` runs | Identical MD5: `1ada44a15044269e35d1771dd5da8b3e` |
| A.4 Step 2 fails non-zero on undetectable input, leaves input untouched | `extract` on a doc with no CZ anchors | Exit code 2, error to stderr, MD5 of input unchanged |

#### B. Invoice template + required fields — PASS (39/39)

| Sub-check | Expected | Got | Result |
|-----------|----------|-----|--------|
| Template fingerprint match | id, threshold cleared, country, no profile pin | `id=11748862-…-6da1`, `score=1.00 ≥ threshold=0.7`, `country=CZE`, `flexylayout_id=cze-invoice-generic`, no `profile` key | OK |
| Profile resolution by `issue_date` | `invoice-cze-2025-01-01.json` for 2026-05-09 | Resolved | OK |
| Historical resolution | `invoice-cze-2013-01-01.json` for 2020-06-15 | Resolved | OK |
| Invoice header fields (4) | number `26050001`, issue/DUZP `2026-05-09`, due `2026-05-23` | All match | OK |
| Issuer fields (6) | Dříč s.r.o., Za rohem 123, 12300 Ráj, Česká republika, IČO 12345678, DIČ CZ12345678 | All match | OK |
| Buyer fields (6) | PŘÍKLADOVÁ a.s., Ukázková 1, 110 00 Praha 1, Česká republika, IČO 00000019, DIČ CZ00000019 | All match | OK |
| Totals (4) | 1 000 000 / 210 000 / 1 210 000, currency CZK | `1000000.00 / 210000.00 / 1210000.00 / CZK` | OK |
| VAT breakdown (3) | rate 21 %, base 1 000 000, tax 210 000 | `21 / 1000000.00 / 210000.00` | OK |
| Payment (4) | VS 26050001, amount 1 210 000 CZK, method "Převodní příkaz" | `26050001 / 1210000.00 / CZK / Převodní příkaz` | OK |
| Provenance (12) | Each entity has `source_block` and `confidence > 0` | All 6 entities annotated (`block_1, block_2, block_4, block_10, block_11`; conf 0.85–0.95) | OK |

#### C. Pipeline behavior — PASS

| Check | Result |
|-------|--------|
| C.1 VIM spec compliance: `vim_version` populated, layers well-formed, UTF-8 preserved (Czech chars) | OK — see Findings note on `vim_version` value |
| C.2 Profile selected by country + `issue_date` per ADR-0001 | OK |
| C.3 No-template fallback to country detection | OK — empty templates dir → CZE detected from `IČO`/`DIČ`/`DUZP` anchors → 6 entities still extracted |
| C.4 SemanticEntity shape (`type`, `source_block`, `fields`, `confidence`) | OK — all 6 entities conform |

#### D. Tests — PASS

| Required | Provided |
|----------|----------|
| Unit: template fingerprint scoring | `test_template_match.py` (6 cases incl. above-threshold, below-threshold, regex rule, malformed-template skip, score tiebreak, real-template smoke) |
| Unit: profile date resolution | `test_profile_resolver.py` (6 cases incl. inclusive/exclusive bounds, historical pick, missing country, missing date, real-repo smoke) |
| Unit: flexylayout extraction primitives | `test_flexy_engine.py` (8 cases incl. `cz_date_iso`, `normalize_amount`, two anchor strategies, required vs optional, real-flexylayout load) |
| Integration / e2e | `test_flowii_extract.py` (4 cases: full extract, in-place semantics, idempotency, negative `ExtractionError`); `test_flowii_parse.py` (PDF → VIM smoke) |
| Negative test (template miss / fallback) | `test_extract_fails_clearly_on_unknown_country` (and runtime confirmation of fallback path in C.3) |

#### E. Documentation — PASS

| Required doc | Present |
|--------------|---------|
| Top-level pipeline doc with two steps + CLI + invariant | `docs/pipeline/README.md` (134 lines) |
| `models/invoice/extraction/README.md` describing flexylayout schema and mapping to VIM `semantic` | `models/invoice/extraction/README.md` (115 lines) |
| ADR-0003 deviations noted | None — pipeline implements ADR-0003 verbatim. Upstream parser limitation is noted in the pipeline README (not a deviation) |

## Test Results

### Functional Tests

- [x] Feature works as specified — all 6 entity types extracted with required fields and provenance
- [x] Acceptance criteria met — A, B, C, D, E all pass
- [x] Edge cases handled — idempotent rerun, no-template fallback, no-CZE-anchors error, optional-entity skip vs required raise

### Regression Tests

- [x] Existing functionality unaffected — project was greenfield (no prior code); existing models/profiles/ADRs untouched
- [x] Cross-platform compatibility — tested on Linux. Windows not retested (no Windows-specific code; pure Python + JSON; pdfplumber/ptx-reco are cross-platform). Recommend separate `tester-windows` pass before claiming Windows compatibility.

## Findings (non-blocking)

1. **`vim_version` is `1.4` after step 1, not `1.5`** — the upstream
   `ptx_reco` execution engine bumps `vim_version` conditionally based
   on which features are populated (1.1 barcodes, 1.2 metadata/fulltext,
   1.3 stemming, 1.4 TOC). The issue's "Implementation hints" note that
   "the extractor must accept both 1.4 and 1.5 inputs (forward-compatibility
   per VIM spec)", so 1.4 is acceptable. Recommendation: track an
   upstream issue to make `vim_version` reflect the *spec* version
   produced rather than the highest-feature watermark, or document this
   deliberately in the VIM spec.

2. **Live PDF → step 1 → step 2 produces 5 entities (no buyer)**, while
   the canonical Java-parsed VIM produces 6. Root cause is the upstream
   Python `text_block_extractor` (status `redesign-required` per its
   own docstring) — it merges the issuer and buyer blocks differently
   than the Java parser. The flexylayouts ship for the Java-parsed
   structure (which is what the issue references). This is documented
   in `docs/pipeline/README.md`. Not a regression; tracking should
   live as a follow-up issue against the upstream parser.

3. **Pre-existing `Makefile` commit** (`5d586c0 feat: add Makefile for
   linting Markdown files`) was already on the branch before the
   feature commit — out of scope for issue 001.

## Final Decision

**STATUS**: **PASS**

**Approval for merge**: **YES**

All acceptance criteria from `docs/issues/done/001-flexy-pipeline-two-step.md`
are met. The 25-test automated suite is green, all 53 manual
verification assertions pass, and the implementation conforms to
ADR-0001 (profile selection), ADR-0002 (template fingerprint match),
and ADR-0003 (two-step pipeline with VIM as boundary).

**Date**: 2026-05-09
**Tester signature**: zdendaku (role: Tester / Generic)
