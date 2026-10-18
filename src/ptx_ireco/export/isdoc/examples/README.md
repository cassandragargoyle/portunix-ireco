# ISDOC reference samples

Vendored example documents from the upstream SPIS / MVČR
distribution, retained as a developer reference.

| File                          | What it shows                                    |
|-------------------------------|--------------------------------------------------|
| `doklad.isdoc`                | Plain ISDOC XML invoice — useful as a reference  |
|                               | shape when adjusting `field_map.json`.           |
| `doklad_s_prilohami.isdocx`   | ISDOCX ZIP container (XML + attachments) — shows |
|                               | the canonical ISDOCX layout that Pohoda / Money  |
|                               | / ABRA importers expect.                         |

These files are **not** required at runtime and are not packaged
into the wheel (the `[tool.setuptools.package-data]` entry in
`pyproject.toml` only lists `*.xsd`). Treat them as documentation.

When a future PR ships an ISDOC writer change, sanity-check the
output against these references using `xmllint` or any diff tool —
they're known-conformant documents from the licensor.

License: same as the upstream ISDOC distribution
(see [`../schemas/README.md`](../schemas/README.md)).
