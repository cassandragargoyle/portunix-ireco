# ISDOC export mapping tables

Per ADR-0007, the ISDOC export consumes its mapping rules from this
directory at runtime. Authoring these tables belongs to
`portunix-reco-studio` (see follow-up issue noted in ADR-0007); until
that lands, the tables ship statically here.

## Files (per country)

```
cze/
├── tax_categories.json   — EN 16931 BT-118 → ISDOC ClassifiedTaxCategory
├── unit_codes.json       — UN/ECE Rec.20 → ISDOC UnitCode
├── currency_codes.json   — ISO 4217 whitelist accepted by CZ ERPs
└── field_map.json        — BT/BG → ISDOC XPath mapping table
```

## `field_map.json` shape

Top-level keys:

- `version` — table revision (string, semver-ish).
- `isdoc_version` — target ISDOC schema version (string, e.g.
  `"6.0.2"`).
- `namespace` — XML namespace URI for the emitted ISDOC.
- `root_element` — local name of the root element (`Invoice`).
- `fields` — ordered array. Order is significant: it must match the
  ISDOC XSD's element ordering inside the root.

Each `fields[*]` entry is one of three shapes:

### Scalar (one BT, single value)

```json
{
  "bt": "BT-1",
  "entity_type": "invoice_header",
  "field": "invoice_number",
  "isdoc_xpath": "/Invoice/ID",
  "cardinality": "1",
  "required_in": ["minimal", "standard", "full"],
  "transform": "iso_date"
}
```

`entity_type` + `field` resolve against
`layers.semantic.entities[?type=<entity_type>].fields[<field>]` in
the input VIM document. (This differs from the ADR-0007 sketch which
used a single `semantic_path`; the sketch was speculative — the
actual semantic shape produced by the extractor is keyed by entity
type, not a dotted path. The mapper README in ADR-0007's
implementation amendments tracks this.)

### Group (BG, repeating child structure)

```json
{
  "bg": "BG-25",
  "entity_type": "invoice_line",
  "isdoc_xpath": "/Invoice/InvoiceLines/InvoiceLine",
  "cardinality": "0..n",
  "required_in": ["standard", "full"],
  "children": [
    {"isdoc_xpath": "ID", "field": "id", "bt": "BT-126"},
    {"isdoc_xpath": "InvoicedQuantity", "field": "quantity",
     "bt": "BT-129", "transform": "decimal3"}
  ]
}
```

One element is appended per matching VIM entity instance. Children's
`isdoc_xpath` is **relative** to the group element.

### Literal (constant, no semantic source)

```json
{
  "isdoc_xpath": "/Invoice/CurrRate",
  "value": "1",
  "cardinality": "1",
  "required_in": ["minimal", "standard", "full"]
}
```

Used for ISDOC elements that are XSD-required but have no
counterpart in the EN 16931 BT/BG model (or that ireco does not yet
extract — e.g. `UUID`, `VATApplicable`).

## Transforms

`transform` runs the value through one of the named pure functions
in `ptx_ireco.export.isdoc.codes`:

| Name              | Effect                                              |
|-------------------|-----------------------------------------------------|
| `decimal2`        | Two-decimal lexical form (handles `12 345,67`).     |
| `decimal3`        | Three-decimal lexical form.                          |
| `iso_date`        | Normalise CZ `DD.MM.YYYY` to `YYYY-MM-DD`.          |
| `iso_currency`    | `Kč` → `CZK`, `€` → `EUR`, otherwise upper-case.    |
| `country_alpha2`  | Country name → ISO 3166-1 alpha-2 code.              |
| `czech_ico`       | Validate 8-digit IČO + mod-11 check.                 |
| `czech_dic`       | Validate `CZ\d{8,10}` format.                        |

## Profiles

`required_in` lists the profiles in which the entry is **required**.
Missing it in a profile that requires it triggers a `required` gate
failure during export.

`emit_in` (optional) restricts emission to the listed profiles even
when the value is present. Useful for fields that ERPs reject in
`minimal` mode.

If neither key is present, the entry is treated as optional in every
profile (emitted only when the value is non-empty).

## Adding a new country

1. Create `models/invoice/exports/isdoc/<iso3>/` (e.g. `svk/`).
2. Drop the four JSON files following the same shape.
3. Add unit tests covering the new transforms (if any).
4. Update the country selector in `ptx_ireco.export.isdoc.api`
   (currently CZ-only).

When studio gains an editor for these tables (per ADR-0007), the
shape above is the contract it must produce.
