# Document Models

This directory contains models (flexible layouts) for individual document types
processed by `portunix-ireco`.

Each subdirectory represents one document type and defines its structure,
expected fields, and extraction rules.

## Document Types

- [`invoice/`](invoice/) — invoice document model

## Adding a New Document Type

1. Create a new subdirectory named after the document type (lowercase, kebab-case)
2. Add a `README.md` describing the document type and its purpose
3. Define the model files (schema, layout, extraction rules)

## Related

- Real-world sample documents are stored in `samples/` (gitignored)
