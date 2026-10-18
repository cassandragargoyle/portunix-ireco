# Flexy Document Pipeline

Two mandatory steps with a `.vim.json` file as the boundary between
them ([ADR-0003](../adr/0003-flexy-pipeline-two-step.md)), plus an
optional third step for invoice ISDOC export
([ADR-0007](../adr/0007-isdoc-export.md)):

```text
source document ──▶ Step 1: PARSE ──▶ *.vim.json
                                         │ (physical + structural [+ toc])
                                         ▼
                    Step 2: EXTRACT  ──▶ *.vim.json (semantic layer added)
                                         │
                                         ▼ (optional, runtime-only)
                    Step 3: EXPORT   ──▶ *.isdoc + *.isdoc.provenance.json
                                         (or *.isdocx ZIP with embedded PDF)
```

Step 3 is **read-only** over `.vim.json`; it never modifies the
input. See [docs/cli/export.md](../cli/export.md) for the export
surface.

## Invariant

The output of step 1 is also the input of step 2; **it is the same file
shape**. The only difference is which layers are populated:

| Layer        | After step 1            | After step 2          |
|--------------|-------------------------|-----------------------|
| `physical`   | populated               | populated (unchanged) |
| `structural` | populated               | populated (unchanged) |
| `toc`        | optional                | optional (unchanged)  |
| `semantic`   | empty (`entities: []`)  | populated             |

## CLI

The pipeline ships with a `ptx-ireco` console script (defined in
`pyproject.toml`) that exposes three subcommands:

```bash
# Step 1: parse a PDF into a .vim.json (physical + structural).
ptx-ireco parse samples/invoice/flowii-FA_26050001.pdf \
    -o samples/invoice/flowii-FA_26050001.pdf.vim.json

# Step 2: read .vim.json, populate the semantic layer, write back.
# Default writes back into the same file (--in-place).
ptx-ireco extract samples/invoice/flowii-FA_26050001.pdf.vim.json

# Convenience: step 1 + step 2.
ptx-ireco run samples/invoice/flowii-FA_26050001.pdf \
    -o samples/invoice/flowii-FA_26050001.pdf.vim.json

# Step 3 (optional): .vim.json → ISDOC 6.0.2 (XML or ISDOCX bundle).
ptx-ireco export samples/invoice/flowii-FA_26050001.pdf.vim.json \
    --format isdoc --profile standard
```

`--models <dir>` overrides the project root used to locate
`models/invoice/{templates,profiles,extraction}/`. By default the CLI
resolves models relative to the current working directory.

## Step 1 — Parse (PDF → VIM)

Wraps [`ptx_reco.vim`](https://github.com/cassandragargoyle/portunix-reco)
via `ptx_ireco.pipeline.parse.parse_pdf`. The wrapper:

1. Registers the upstream `TextBlockExtractor` (and any optional
   barcode / table / graphics / toc extractors that import cleanly).
2. Runs `ExecutionEngine.process()` against the PDF bytes.
3. Converts the resulting `VimDocument` dataclass tree to a JSON-ready
   dict.
4. **Forces `layers.semantic.entities` back to `[]`** so the contract
   "step 1 emits no semantic data" holds even if a future ptx_reco
   build starts populating headers automatically.

A non-text PDF (or a PDF that produces zero blocks) raises
`RuntimeError`; no `.vim.json` is written. Image-only PDF pages can be
recovered with the optional OCR fallback — see
[`docs/cli/parse.md`](../cli/parse.md) for the `--ocr` flags and
prerequisites (issue 007).

> **Upstream parser status.** As of this writing, the Python
> `text_block_extractor` in `ptx_reco` is `redesign-required` — it uses
> a different clustering algorithm than the original Java vim-parser
> (PDFBox vs pdfplumber, character-callback vs page-bulk). The two
> parsers can produce **different structural-block boundaries** on the
> same PDF. The flexylayouts shipped under `models/invoice/extraction/`
> were authored against the Java parser's structure (which is the
> reference VIM file shipped under `samples/invoice/`); when running
> end-to-end against a live PDF, expect lower extraction recall until
> the Python parser graduates from `redesign-required`. The pipeline
> contract (semantic written into the same file, in-place,
> overwrite-on-rerun) is independent of which parser produced the
> input.

## Step 2 — Extract (VIM → semantic)

Implemented in `ptx_ireco.pipeline.extract.extract_file`. The order of
operations is fixed:

1. **Template fingerprint match** ([ADR-0002](../adr/0002-invoice-template-layer.md))
   over `models/invoice/templates/*.json`. The highest-scoring template
   that clears its `match_threshold` wins; its `country` and optional
   `flexylayout_id` are used downstream.
2. **Country detection fallback**: if no template matches, scan the
   document for Czech-style anchors (`IČO:`, `DIČ:`, `DUZP`,
   `Variabilní symbol`, `Česká republika`). If still no country, the
   pipeline raises `ExtractionError`.
3. **Profile resolution** ([ADR-0001](../adr/0001-invoice-profile-design.md))
   by `issue_date`. The resolver picks the file under
   `models/invoice/profiles/<country>/` whose
   `valid_from <= issue_date < valid_to` (or no `valid_to`).
4. **Flexylayout selection**: explicit `flexylayout_id` from the
   matched template, otherwise the lexicographically first
   `*.json` under `models/invoice/extraction/<country>/`.
5. **Flexylayout execution**: each entity declaration anchors itself
   on a structural block, then pulls field values via regex / line
   index. Entities carry the anchor block's `id` as `source_block`
   plus a `confidence` value declared in the flexylayout.
6. **Write-back**: the entities replace `layers.semantic.entities`
   in the input file (or `-o` target). Other `layers.semantic` keys
   (`payments`, `stemming`) are preserved if present.

### Idempotency

`extract` **overwrites** `layers.semantic.entities` on each run. Re-running
against an already-extracted file produces the same content (modulo
template / profile / flexylayout changes). No partial corruption: on
error, the input file is left untouched (the writer is atomic — temp
file + rename).

## Failure modes

| Failure                                  | Behaviour                                            |
|------------------------------------------|------------------------------------------------------|
| Step 1: PDF unreadable / no blocks       | `RuntimeError`, no output file                       |
| Step 2: no template, no CZ anchors       | `ExtractionError`, exit code 2                       |
| Step 2: no profile valid for `issue_date`| `ExtractionError`, exit code 2                       |
| Step 2: no flexylayout for country       | `ExtractionError`, exit code 2                       |
| Step 2: required entity anchor missing   | `FlexyExtractionError` → `ExtractionError`           |
| Step 2: optional entity anchor missing   | Skipped silently — other entities still emitted      |

## See also

- [`models/invoice/extraction/README.md`](../../models/invoice/extraction/README.md)
  — flexylayout JSON schema and per-country layouts.
- [`models/invoice/README.md`](../../models/invoice/README.md) — invoice
  model layers (templates / core / profiles / extraction).
- ADRs: [0001](../adr/0001-invoice-profile-design.md),
  [0002](../adr/0002-invoice-template-layer.md),
  [0003](../adr/0003-flexy-pipeline-two-step.md).
