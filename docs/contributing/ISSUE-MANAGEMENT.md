# Issue Management for portunix-ireco

## Purpose

This document defines the process for creating, tracking, and archiving issues in the
portunix-ireco project.

> **GitHub is the single source of truth for the issue list.** There are **no overview
> tables** in `docs/issues/README.md` or `docs/issues/done/README.md` — a shared Markdown
> table edited by everyone causes merge conflicts. Status, assignee, and labels live on
> GitHub; the repository keeps only the long-form write-up per issue.

## GitHub-First Workflow

The issue is **created on GitHub first**, so **GitHub assigns the number `N`**. The GitHub
issue carries only the *basics* (title + a short description + a link to the detail
file). The full write-up lives in the repository at `docs/issues/NNN-name.md`, where the
filename number **equals the GitHub issue number** (zero-padded to three digits).

1. **Create the GitHub issue** (GitHub assigns `N`):

   ```bash
   gh issue create --repo cassandragargoyle/portunix-ireco \
     --title "Short descriptive title" \
     --body "Short description. Full details: docs/issues/NNN-name.md" \
     --label enhancement,medium
   ```

2. **Write the detail file** `docs/issues/NNN-name.md` (problem, acceptance criteria,
   testing, related issues). Use `N` in the filename and in the `# Issue #N:` heading.

3. **Update the GitHub body** with a working link to the detail file once `N` is known:

   ```bash
   gh issue edit N --repo cassandragargoyle/portunix-ireco --body "Short description.

   📄 [Full details](https://github.com/cassandragargoyle/portunix-ireco/blob/main/docs/issues/NNN-name.md)"
   ```

4. **Reference `N`** in branches and commits: `feature/NNN-name` (zero-padded, `#8` → `feature/008-name`), `feat(N): …`, `fixes #N`.

5. **Archive on completion**: `gh issue close N` and
   `git mv docs/issues/NNN-name*.md docs/issues/done/`.

The `create-issue` skill (`/create-issue`) automates steps 1–3.

> **Numbering note.** GitHub issues and pull requests share one counter, so numbers may
> skip where a PR consumed one. Never invent a number — always take the one GitHub returns.

### Legacy Numbering

Issues 001 … 007 were created before the move to GitHub and lived in
`docs/issues/internal/` (active) and `docs/issues/internal/done/` (archive). They were
mirrored to GitHub 1:1, so **issue `NNN` = `#N`**. The `internal/` and `public/`
directories are retired. Existing mentions such as `feature/issue-007-ocr-step` in
acceptance protocols and commits stay as they are.

### Public Content

The repository and its GitHub issues are **public**. Issue write-ups and GitHub bodies
must not contain customer data, real company identifiers (IČO, DIČ, addresses, bank
accounts) taken from real documents, personal data, credentials, internal hostnames, or
links into private repositories. Use fictional placeholders in examples.

## File Structure

```text
docs/
├── issues/
│   ├── README.md                  # Process notes only — NO overview table
│   ├── NNN-name.md                # Active issue write-up (NNN = GitHub issue number)
│   ├── NNN-name-verbatims.md      # Verbatim user requirements (optional)
│   └── done/                      # Archived (✅ Implemented / ❌ Closed / ➡️ Moved)
│       ├── README.md
│       └── NNN-*.md
└── testing/
    ├── plan-NNN.md                # Tester plan (optional)
    └── acceptance-NNN.md          # Tester acceptance protocol
```

## File Naming

Issue filenames use **lowercase kebab-case** only, matching the rule in
[NAMING-CONVENTIONS.md](NAMING-CONVENTIONS.md).

- **Pattern**: `NNN-<slug>.md`
- **`NNN`**: the GitHub issue number, zero-padded to three digits (`#7` → `007`)
- **`<slug>`** — strict rules:
  - lowercase ASCII letters only (`a`–`z`) and digits (`0`–`9`)
  - words separated by a single hyphen `-`
  - no uppercase, no spaces, no underscores, no diacritics, no dots
    other than the `.md` extension, no other punctuation
  - derived from the issue title by lowercasing, stripping punctuation
    and diacritics, and replacing whitespace with `-`

Examples:

- OK: `012-isdoc-export-for-credit-notes.md`
- NOT OK: `012-ISDOC-Export.md` (uppercase)
- NOT OK: `012_isdoc_export.md` (underscores)

## Detail File Template

```markdown
# Issue #N: Title

## Summary

1–3 sentences.

**Status**: 📋 Open
**Type**: Bug | Enhancement | Feature | Task
**Priority**: Critical | High | Medium | Low
**Component**: <module or path>
**Created**: YYYY-MM-DD
**GitHub**: #N
**Related**: #...

## Problem Description

## Acceptance Criteria

1. ...

## Testing
```

## Status Values

- 📋 Open — needs work
- 🚧 In Progress — actively worked on (GitHub label `in-progress`)
- ✅ Implemented — completed (file in `done/`, GitHub issue closed as completed)
- ❌ Closed — closed without implementation (file in `done/`, closed as not planned)
- ➡️ Moved — moved to another project (file in `done/`)
- ⏸️ On Hold — temporarily paused

## Labels

- **Type**: `bug`, `enhancement`, `documentation`, `testing`
- **Priority**: `critical`, `high`, `medium`, `low`
- **Status**: `in-progress`

Always assign one type label and one priority label. Create a missing label only when it
is needed by more than one issue.

## Claiming an Issue

GitHub also holds the assignee. Before starting work, check the issue is open and not
assigned to someone else, then assign it to yourself:

```bash
gh issue view N --repo cassandragargoyle/portunix-ireco --json state,assignees
gh issue edit N --repo cassandragargoyle/portunix-ireco --add-assignee @me
```

## Integration with Development Workflow

### Branches

- `feature/NNN-short-name` for features and enhancements
- `fix/NNN-short-name` for bug fixes

`NNN` is the GitHub issue number zero-padded to three digits (`#8` → `fix/008-short-name`),
matching the issue file name.

### Commit Messages

```text
feat(N): short summary
fix(N): short summary
docs(N): close issue — archive to done/
```

Use `refs #N` or `closes #N` in the commit body or PR description to link the GitHub issue.

### Pull Requests

```markdown
**Related Issues:** Fixes #N

**Description:** Brief description of changes

**Acceptance:** docs/testing/acceptance-NNN.md
```

See [ISSUE-DEVELOPMENT-METHODOLOGY.md](ISSUE-DEVELOPMENT-METHODOLOGY.md) for the phased
development, testing, and acceptance process.

---

*Last updated: 2026-10-18 — moved from `internal/` + README tables to GitHub-first numbering*
