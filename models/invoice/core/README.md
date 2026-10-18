# Core Invoice Model

Country-neutral semantic model based on **EN 16931**.

- `invoice.schema.json` — JSON Schema (Draft 2020-12) defining the canonical
  invoice structure. Field-level `$comment` entries reference EN 16931
  Business Terms (`BT-*`) and Business Groups (`BG-*`).

Country profiles in `../profiles/` extend this core with country-specific
required fields, identifiers, and validation rules.
