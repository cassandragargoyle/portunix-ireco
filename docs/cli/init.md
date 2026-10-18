# `ptx-ireco init`

Create or update an `ireco.config.json` in the current working directory.
The config declares which document types are processed there, where
input/output PDFs live, and — for invoices — which recipients (tenants)
the directory serves and what depth of extraction each one needs.

The schema is defined in
[`docs/schemas/ireco-config-1.0.json`](../schemas/ireco-config-1.0.json)
and discussed in [ADR-0004](../adr/0004-ireco-config-schema.md).

## Usage

```bash
# Interactive wizard
ptx-ireco init

# Non-interactive (CI / batch)
ptx-ireco init --from-file path/to/candidate.json
```

The wizard refuses to start on a non-TTY stdin and points the user at
`--from-file` instead. Both paths share the same JSON Schema validator
and the same atomic write step (write-temp + rename), so a crash mid
write never leaves a partial file on disk.

## Wizard flow

```text
Step 1  Document types          → doc_types
Step 2  Input directory          → io.input_dir
Step 3  Output directory         → io.output_dir
        (only if "invoice" ∈ doc_types)
Step 4  Invoice tenancy          → invoice.tenancy
        ├─ multitenant
        │   Step 5a  Global extraction depth   → invoice.extraction.depth
        │   Step 6a  Match against orders?     → invoice.extraction.orders
        └─ known
            Step 5b  Recipient count
            Step 6b  Per recipient: id, name, IČO, DIČ,
                     extraction depth, optional orders glob
Step 7  Review summary, confirm write → ./ireco.config.json
```

When `ireco.config.json` already exists, the wizard runs in **update
mode**: it shows a section menu (`[1]` doc types · `[2]` I/O paths ·
`[3]` invoice tenancy · `[4]` recipients · `[5]` write & exit · `[q]`
quit) with current values shown as defaults. `q` exits without writing.
An existing file that fails validation is **never** silently overwritten
— the wizard refuses to update and asks the user to fix or delete it
first.

## Tenancy modes

`multitenant` is for directories that ingest invoices addressed to many
companies. There is no per-recipient slot, so `invoice.extraction`
carries a single global `depth` (and optional `orders`).

`known` is for directories whose recipients are a fixed list — typically
one accounting firm processing for a known set of clients. Each
recipient has its own `extraction` so two tenants in the same directory
can use different depths (e.g. `header` for one, `items` for another).

For a complete rationale of why these are separate modes (rather than a
single list with sentinel entries) see
[ADR-0004](../adr/0004-ireco-config-schema.md#why-two-tenancy-modes-instead-of-everything-is-a-list).

## Examples

### Multitenant, header only

```json
{
  "$schema": "https://cassandragargoyle.example/ireco/config-1.0.json",
  "version": 1,
  "doc_types": ["invoice"],
  "io": {"input_dir": "./in", "output_dir": "./out"},
  "invoice": {
    "tenancy": "multitenant",
    "extraction": {"depth": "header"}
  }
}
```

### Known tenants, per-recipient depth

```json
{
  "$schema": "https://cassandragargoyle.example/ireco/config-1.0.json",
  "version": 1,
  "doc_types": ["invoice"],
  "io": {"input_dir": "./in", "output_dir": "./out"},
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
          "orders": {"source": "local", "path": "./orders/example-buyer/*.json"}
        }
      },
      {
        "id": "acme-cz",
        "name": "ACME CZ s.r.o.",
        "ico": "12345678",
        "extraction": {"depth": "header"}
      }
    ]
  }
}
```

## Pipeline integration

When `ireco.config.json` is present in the working directory:

- `parse` / `extract` / `run` use `io.input_dir` / `io.output_dir` as
  defaults; explicit `-o` / positional paths still win.
- For invoices in `known` mode, the configured recipients are matched
  against the parsed buyer (DIČ → IČO → name, case-insensitive). A
  successful match attaches `document.recipient_id` to the VIM output;
  no match leaves it unset (callers can still inspect the buyer entity).
- For `multitenant` mode no `recipient_id` is attached and existing
  extraction behavior is preserved.
- Reserved doc types (`receipt`, `delivery_note`, `purchase_order`) are
  accepted by the schema and the wizard but the pipeline exits with
  code `3` and a clear message until those extractors land.

## Exit codes

| Code | Meaning                                                          |
|------|------------------------------------------------------------------|
| 0    | Success (including a clean wizard quit without writing).         |
| 1    | Wizard aborted (`Ctrl-C`, EOF on stdin, declined write prompt).  |
| 2    | Generic config error (e.g. missing input file).                  |
| 3    | A reserved doc type was declared and the pipeline refused it.    |
| 4    | The config file is present but invalid (or has bad version).     |
