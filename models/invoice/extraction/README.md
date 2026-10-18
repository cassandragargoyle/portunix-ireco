# Invoice Extraction Layer (Flexylayouts)

Flexylayouts drive **step 2** of the flexy pipeline: they map raw,
structural-block evidence (`layers.structural.blocks`) onto VIM
`SemanticEntity` records (`layers.semantic.entities`). See
[`docs/pipeline/README.md`](../../../docs/pipeline/README.md) for the
end-to-end picture and [ADR-0003](../../../docs/adr/0003-flexy-pipeline-two-step.md)
for the design rationale.

## Directory layout

```text
models/invoice/extraction/
├── README.md
└── <country-iso3>/         # lowercase, e.g. cze, deu, svk
    └── <flexylayout-id>.json
```

A template can pin a specific flexylayout by setting
`"flexylayout_id": "<file-stem>"` (no `.json`); otherwise the resolver
picks the lexicographically first file under the country directory.

## Schema (informal)

```jsonc
{
  "id": "cze-invoice-generic",
  "version": "1.0",
  "country": "CZE",
  "description": "...",
  "entities": [
    {
      "type": "invoice_header",          // SemanticEntity.type
      "anchor": { ... },                 // see below
      "confidence": 0.95,                // SemanticEntity.confidence
      "required": false,                 // optional, default false
      "fields": [
        { "name": "...", "from": "...", ... }
      ]
    }
  ]
}
```

### Anchor strategies

| Strategy                             | Meaning                                                  |
|--------------------------------------|----------------------------------------------------------|
| `{"any_block_contains": "<sub>"}`    | First block whose joined header+content has substring    |
| `{"block_with_header": "<sub>"}`     | First block whose `header` contains substring            |
| `{"block_after_header": "<sub>"}`    | Block immediately after the one whose header matches     |
| `{"any_block_regex": "<rx>"}`        | First block whose joined text matches the regex          |

Anchor failure means the entity is **skipped** (not an error) unless
`required: true`, in which case the pipeline aborts.

### Field rules

A field rule is `{"name": "...", "from": "<source>", ...}`. The `from`
value selects where to look:

| `from`                  | Required keys                              | Notes                                                       |
|-------------------------|--------------------------------------------|-------------------------------------------------------------|
| `"global"`              | `regex` (with capture group)               | Search the whole document text                              |
| `"anchor_block"`        | `regex`                                    | Search the anchor block's joined header+content             |
| `"anchor_block_line"`   | `index` (0-based)                          | Pull the Nth line from the anchor block's `content` array   |
| `"block_after_header"`  | `header_pattern` + (`regex` or `index`)    | Resolve a different anchor per field                        |

Optional keys on a field rule:

- `group` — regex capture group to return (default `1`).
- `transform` — apply a known transform: `cz_date_iso`,
  `normalize_amount`, `strip`.
- `static` — fallback value used if the regex did not capture anything.

### Mapping onto VIM `SemanticEntity`

Each entity declaration produces exactly one `SemanticEntity`:

```json
{
  "type": "<entity_def.type>",
  "source_block": "<anchor block id>",
  "fields": { "<rule.name>": "<extracted value>", ... },
  "confidence": <entity_def.confidence>
}
```

`source_barcode` is reserved for future barcode-anchored entities (e.g.
SPAYD payment) and is not used by the current generic flexylayout.

## Provided flexylayouts

| File                          | Country | Notes                                                                                  |
|-------------------------------|---------|----------------------------------------------------------------------------------------|
| `cze/cze-invoice-generic.json`| CZE     | Czech invoices with Flowii-style layout. Anchors on common Czech labels (IČO, DIČ, …). |

## Adding a new flexylayout

1. Create `models/invoice/extraction/<country>/<id>.json` following the
   schema above. UUIDv4 filenames are not required here — choose a
   short, human-meaningful id.
2. (Optional) Wire a template at `models/invoice/templates/<uuid>.json`
   with `flexylayout_id` pointing at the new file's stem.
3. Add an integration test under `tests/e2e/` against a checked-in
   sample VIM file.

## Related

- [ADR-0001](../../../docs/adr/0001-invoice-profile-design.md) —
  three-layer invoice model.
- [ADR-0002](../../../docs/adr/0002-invoice-template-layer.md) —
  template fingerprint matching.
- [ADR-0003](../../../docs/adr/0003-flexy-pipeline-two-step.md) —
  two-step pipeline.
