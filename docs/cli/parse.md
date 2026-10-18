# `ptx-ireco parse` — Step 1 (PDF → `.vim.json`)

Parses a PDF into a `.vim.json` containing the `physical` +
`structural` (and optional `toc`) layers. The `semantic` layer is left
empty so [`ptx-ireco extract`](../pipeline/README.md) can populate it
later. See [ADR-0003](../adr/0003-flexy-pipeline-two-step.md) for the
boundary contract.

## Synopsis

```text
ptx-ireco parse <pdf> [-o <out.vim.json>]
                      [--ocr | --no-ocr]
                      [--ocr-language <code>]
                      [--ocr-dpi <int>]
                      [--ocr-min-ink-ratio <float>]
                      [--ocr-mode printed]
                      [-v]
```

If an `ireco.config.json` is present in the cwd, `io.output_dir` is
used as the default output directory (the explicit `-o` value still
wins).

## OCR fallback (issue 007)

Image-only PDF pages (scans, photos of paper) carry no text layer that
pdfplumber can read. When `--ocr` is enabled, an OCR plugin from
`ptx_reco` runs **per page** and contributes blocks for pages where:

1. pdfplumber produced no text blocks, **and**
2. the rendered page bitmap passes a configurable ink-ratio gate
   (default ≥ 0.5 % non-white pixels after Otsu binarization).

The gate is what prevents 300-DPI Tesseract from being spawned on
truly blank scans.

### Flags

| Flag                       | Default     | Notes                                                                                  |
|----------------------------|-------------|----------------------------------------------------------------------------------------|
| `--ocr` / `--no-ocr`       | follow cfg  | Master switch. `--no-ocr` forces OFF even when the config enables it.                  |
| `--ocr-language <code>`    | `eng`       | Tesseract language code(s), `+`-separated (`eng`, `eng+ces`, `eng+ces+slk`).           |
| `--ocr-dpi <int>`          | `300`       | Render DPI for the OCR pass. Minimum 72.                                               |
| `--ocr-min-ink-ratio <f>`  | `0.005`     | Skip pages whose non-white pixel fraction is below this. `0` disables the guard.       |
| `--ocr-mode printed`       | `printed`   | OCR mode. Only `printed` is supported in v1; handwritten/checkbox are reserved.        |

### Precedence

CLI flag > `parse.ocr` in `ireco.config.json` > built-in default.

### Discoverability hint

If you run `ptx-ireco parse <pdf>` **without** `--ocr` and the parsed
PDF contains at least one page with no structural blocks, a one-line
hint is written to stderr:

```text
WARN: 3/12 pages have no extracted text. Re-run with --ocr to recover them.
```

The hint is informational; the parse itself still succeeds (or fails
with `RuntimeError` for fully blank PDFs, same as before issue 007).

### Prerequisites

OCR requires three host-provided pieces:

1. **Tesseract** on `PATH` — `apt install tesseract-ocr` (Debian/Ubuntu),
   `brew install tesseract` (macOS), or the official Windows installer.
2. **Tesseract language data** for every code you pass via
   `--ocr-language` — e.g. `apt install tesseract-ocr-ces
   tesseract-ocr-slk` for Czech/Slovak.
3. **`pdf2image`** Python package **plus Poppler** — `pip install
   pdf2image` and `apt install poppler-utils`.

If any of these is missing, the OCR plugin reports a `PluginResult`
failure with the verbatim error from the underlying library; the
parse still completes for any pages where pdfplumber found text on
its own, but image-only pages stay empty.

### Configuration via `ireco.config.json`

```jsonc
{
  "version": 1,
  "doc_types": ["invoice"],
  "io": { "input_dir": "./in", "output_dir": "./out" },
  "invoice": { "tenancy": "multitenant", "extraction": { "depth": "header" } },

  "parse": {
    "ocr": {
      "enabled": true,
      "language": "eng+ces",
      "dpi": 300,
      "min_ink_ratio": 0.005,
      "mode": "printed"
    }
  }
}
```

When `parse.ocr` is absent, parse behavior is unchanged from pre-007
(no OCR plugin import; image-only PDFs raise `RuntimeError`).

## Examples

```bash
# Text-only PDF, OCR off (default).
ptx-ireco parse invoice.pdf -o invoice.vim.json

# Scanned PDF, English-only OCR.
ptx-ireco parse scan.pdf -o scan.vim.json --ocr

# Czech invoice scans with a stricter blank-page guard.
ptx-ireco parse scan.pdf -o scan.vim.json \
    --ocr --ocr-language eng+ces --ocr-min-ink-ratio 0.01

# Force OCR off even when the config enables it.
ptx-ireco parse scan.pdf -o scan.vim.json --no-ocr
```

## Exit codes

| Code | Meaning                                                                          |
|------|----------------------------------------------------------------------------------|
| `0`  | Parse completed (output written).                                                |
| `2`  | Bad CLI usage (e.g. `-o` missing when no `ireco.config.json` is present).        |
| `4`  | `ireco.config.json` failed schema validation.                                    |

A `RuntimeError` from the upstream parser (zero structural blocks) is
**not** caught by the CLI — it terminates the process with the usual
Python traceback. With `--ocr` enabled, that path is reachable only
when every page is below the ink-ratio gate (i.e. the PDF is blank).
