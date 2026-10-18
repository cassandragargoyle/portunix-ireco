# Issues - portunix-ireco

This directory contains the long-form write-ups for issues, feature requests, and
development planning for portunix-ireco.

## No overview table here

The canonical issue list lives on GitHub — that is the single source of truth for
status, assignee, and labels:

- **Open / active issues** → <https://github.com/cassandragargoyle/portunix-ireco/issues>
- **Closed / done issues** → <https://github.com/cassandragargoyle/portunix-ireco/issues?q=is%3Aissue+is%3Aclosed>

This directory keeps the **long-form write-up** for each issue as `NNN-name.md`, where
`NNN` is the **GitHub issue number** (zero-padded to three digits). Active issues sit
directly in this directory, archived ones in [`done/`](done/). Verbatim requirement logs
(`NNN-name-verbatims.md`) sit next to their issue file and move with it.

## Numbering

Issues are **GitHub-first**: the number is assigned by GitHub when the issue is created,
and the local file adopts that exact number. GitHub issues and pull requests share one
counter, so numbers may skip where a PR consumed one.

> **Legacy note.** Before the move to GitHub, issues 001 … 007 lived in `internal/` and
> `internal/done/`. They were mirrored to GitHub 1:1, so **issue `NNN` = GitHub `#N`**
> (e.g. `007` = `#7`). The `internal/` and `public/` directories are retired.

## Creating a new issue

Use the `create-issue` skill (`/create-issue`), or do it by hand:

1. **Create the GitHub issue first** — GitHub assigns the number `N`:

   ```bash
   gh issue create --repo cassandragargoyle/portunix-ireco \
     --title "Short descriptive title" \
     --body "Short description. Full details: docs/issues/NNN-name.md" \
     --label enhancement,medium
   ```

   Keep the GitHub body minimal — a short summary plus a link to the detail file.

2. **Write the detail file** `docs/issues/NNN-name.md` with the full context, acceptance
   criteria, and implementation notes.

3. **Reference the number** in branches and commits: `feature/NNN-name` (zero-padded, `#8` → `feature/008-name`), `feat(N): …`,
   `fixes #N`.

No table to update — GitHub is the list of record.

## Archiving a completed issue

When an issue reaches a terminal status (✅ Implemented, ❌ Closed, ➡️ Moved):

1. Update the status in the issue file.
2. Move the file (and its verbatims file, if any):
   `git mv docs/issues/NNN-name*.md docs/issues/done/`.
3. Close the GitHub issue: `gh issue close N`.

See [ISSUE-MANAGEMENT.md](../contributing/ISSUE-MANAGEMENT.md) for the full process.
