# `ptx-ireco export`

Step 3 of the pipeline: turn a populated `*.vim.json` (output of
`extract`) into an ISDOC 6.0.2 e-invoice artefact for Czech ERPs.
See [ADR-0007](../adr/0007-isdoc-export.md) for the design and
[issue 006](../issues/done/006-isdoc-export.md) for the
implementation contract.

## Synopsis

```bash
ptx-ireco export <file.vim.json>
                 [-o <out_dir>]
                 [--format isdoc|isdocx]              # default: isdoc
                 [--profile minimal|standard|full]    # default: standard
                 [--allow-incomplete]
                 [--source-pdf <file.pdf>]            # only for isdocx
                 [--models <models_path>]
                 [-v/--verbose]
```

## Outputs

The command always writes:

| File                            | Content                                              |
|---------------------------------|------------------------------------------------------|
| `<stem>.isdoc`                  | ISDOC 6.0.2 XML (deterministic, UTF-8, no pretty)    |
| `<stem>.isdoc.provenance.json`  | Sidecar mapping each XPath back to its source block  |

When `--format isdocx` is set, an additional ZIP container is
produced:

| File             | Content                                                     |
|------------------|-------------------------------------------------------------|
| `<stem>.isdocx`  | ZIP with `<stem>.isdoc` (deflate), `<stem>.pdf` (stored), `META-INF/manifest.xml` |

The PDF is **stored** without recompression; PDFs are already
compressed and re-deflating wastes CPU on the importing ERP.

## Completeness profiles

- `minimal` — emits only ISDOC-required and CZ-mandatory fields.
  Strips invoice lines and VAT breakdown. Useful for header-only
  imports.
- `standard` (default) — everything in `minimal` plus invoice lines
  and VAT breakdown. Matches what typical Czech AP modules import.
- `full` — every mapped BT/BG, including optional narrative,
  delivery information, and CZ-specific extras (variable symbol).

`required_in` in `field_map.json` (under
`models/invoice/exports/isdoc/cze/`) declares per-entry profile
inclusion; missing a required field in the chosen profile triggers a
`required` gate failure.

## Validation gates

The export runs four gates in order; **all** failures are aggregated,
not just the first:

1. **Required-field check** against the field-map filtered by
   profile.
2. **XSD validation** against the bundled `isdoc-invoice-6.0.2.xsd`.
3. **Business rules** — BR-CO-10 (Σ line nets = TaxExclusiveAmount),
   BR-CO-13 (TaxExclusiveAmount + TaxAmount = TaxInclusiveAmount),
   BR-CZ-IČO (8 digits + mod-11 checksum), BR-CZ-DIČ
   (`CZ\d{8,10}`), BR-CZ-CURRENCY (whitelist).
4. **Round-trip parse** — re-load the emitted XML and re-validate
   against the XSD, defending against escaping bugs.

By default, any failure aborts emission with exit code `4`. Pass
`--allow-incomplete` to write the artefacts anyway; failures are
returned in the JSON output and `WARN` is logged to stderr (exit
code stays `0` so pipelines can continue).

## Source-PDF discovery (`--format isdocx`)

When `--format isdocx` and `--source-pdf` is omitted, the CLI looks
in this order:

1. `<stem>.pdf` next to the input `.vim.json`.
2. `document.source` recorded inside the VIM file.

If neither resolves, the command exits `4` with the message
`"isdocx requires --source-pdf or a discoverable PDF"`.

## Exit codes

| Code | Meaning                                                            |
|------|--------------------------------------------------------------------|
| 0    | Success (or `--allow-incomplete` produced output despite failures) |
| 4    | Validation failure or input/options error                          |

## Examples

```bash
# Plain ISDOC XML alongside the input.
ptx-ireco export scan.vim.json

# ISDOCX bundle with a specific PDF.
ptx-ireco export scan.vim.json --format isdocx --source-pdf scan.pdf

# Minimal profile, write to a different directory.
ptx-ireco export scan.vim.json --profile minimal -o /tmp/out

# Tolerant export with verbose JSON summary including failures.
ptx-ireco export scan.vim.json --allow-incomplete -v
```

## Worker task

The same engine is exposed as a worker task type
`ireco.invoice.export` over the standard ireco-worker JSON
contract. See [`docs/cli/worker.md`](worker.md) for the request/
response shape used by all task types; the per-type fields for
`export` are:

```jsonc
{
  "task": "ireco.invoice.export",
  "input": {
    "vim_path": "/abs/scan.vim.json",
    "output_dir": "/abs/out",
    "options": {
      "format": "isdocx",
      "profile": "standard",
      "allow_incomplete": false,
      "models": "/abs/models",
      "source_pdf": "/abs/scan.pdf"
    }
  }
}
```

Validation failures map to `error.code = "VALIDATION_ERROR"` (an
ireco-local code added in issue 006; not pushed upstream into
ptx-reco). The full list of failures is attached as
`error.details`.

## Watcher chaining

Set `watcher.post_process: ["export-isdoc"]` in `ireco.config.json`
(or pass `--post-process export-isdoc` to `ptx-ireco-watcher`) to
run the export step automatically after a successful
`scan.processed` event. Per-handler options live under
`watcher.post_process_options.export-isdoc`. Failures emit a
`postprocess.failed` event; the parser's `.vim.json` is preserved
on disk regardless.

## Mapping tables

The export consumes JSON tables shipped under
`models/invoice/exports/isdoc/cze/`:

- `field_map.json` — BT/BG → ISDOC XPath mapping (see
  [`models/invoice/exports/isdoc/README.md`](../../models/invoice/exports/isdoc/README.md)).
- `tax_categories.json` — EN 16931 BT-118 → ISDOC
  `ClassifiedTaxCategory`.
- `unit_codes.json` — UN/ECE Rec.20 → ISDOC `UnitCode`.
- `currency_codes.json` — ISO 4217 whitelist used by the BR-CZ-CURRENCY
  rule.

Editing these tables today is a manual JSON edit; per ADR-0007 the
authoring surface eventually moves to `portunix-reco-studio`.

## Known limitations (v0.1)

- The shipped `field_map.json` is intentionally pragmatic — it
  covers the canonical CZ invoice shape (header, supplier, customer,
  one VAT band, totals) but does not yet emit fully XSD-conformant
  output for every CZ ERP variation. The engine is correct; the map
  is iterative. Use `--allow-incomplete` while the map is being
  filled in.
- Only document types `380` (invoice) and `381` (credit note) are
  in scope — `DocumentType` is a literal `1`. Other types return
  `VALIDATION_ERROR`.
- Only CZ is implemented. The module layout keeps `isdoc/` as a
  sibling under `export/` so XRechnung (DE), FatturaPA (IT), and
  UBL-PEPPOL (EU) can land later without disturbing this code.
