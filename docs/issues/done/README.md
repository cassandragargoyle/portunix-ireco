# Issues - portunix-ireco — Done

This directory archives **completed** issues (✅ Implemented, ❌ Closed, or ➡️ Moved).
Active issues and the full workflow live in the parent [`docs/issues/README.md`](../README.md).

## No overview table here

The canonical issue list lives on GitHub:

- **Closed issues** → <https://github.com/cassandragargoyle/portunix-ireco/issues?q=is%3Aissue+is%3Aclosed>
- Each archived issue keeps its full write-up in this directory as `NNN-name.md`, where
  `NNN` matches its **GitHub issue number**.

## Archiving workflow

When an issue reaches a terminal status (✅ Implemented, ❌ Closed, or ➡️ Moved):

```bash
git mv docs/issues/NNN-name*.md docs/issues/done/
gh issue close N --repo cassandragargoyle/portunix-ireco
```
