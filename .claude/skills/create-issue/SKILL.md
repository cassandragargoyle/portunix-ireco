---
name: create-issue
description: 'Create a new issue GitHub-first — the GitHub issue is created first (GitHub assigns the number), then the long-form write-up goes into docs/issues/NNN-*.md. Use when the user wants to create or file an issue, feature request or bug. Examples: "create an issue for …", "/create-issue OOM on large PDF".'
argument-hint: [short issue description]
allowed-tools: Read, Glob, Grep, Bash, AskUserQuestion, Write, Edit
user-invocable: true
---

# Create Issue (GitHub-first)

**IMPORTANT: NEVER add "Co-Authored-By: Claude <noreply@anthropic.com>" to code files or git commits.**

**Argument:** $ARGUMENTS

## Principle

**GitHub is the single source of truth for the issue list.** GitHub assigns the number
when the issue is created. The GitHub issue holds only the **basics** (title + short
description + link to the detail file). Details live in `docs/issues/NNN-*.md`, where
`NNN` = GitHub issue number zero-padded to three digits.

**Do not add overview tables** to any README and do not use `internal/` or `public/`
directories (retired).

The repository and its issues are **public**. Never put customer data, real company
identifiers (IČO, DIČ, addresses, bank accounts) from real documents, personal data,
credentials, internal hostnames, or links into private repositories into the GitHub body
or the detail file. Use fictional placeholders.

## STEP 1: Collect the input

From the argument / context (or via `AskUserQuestion` if missing) find out:

- **Title** — short, descriptive, English (without number; GitHub adds it)
- **Slug** — kebab-case for the file name (derive from the title, e.g. `large-document-oom`)
- **Type** → label: `bug` | `enhancement` | `documentation` | `testing`
- **Priority** → label: `critical` | `high` | `medium` | `low`
- **Short description** (1–3 sentences) — goes into the GitHub issue body
- **Detailed content** — goes into the local `.md` (problem, steps, acceptance criteria, tests)

All texts in **English** (project convention).

## STEP 2: Preflight — check `gh`

```bash
gh --version && gh auth status
```

If not logged in, stop and ask the user to run `gh auth login` (e.g. with the `!` prefix).

## STEP 3: Create the GitHub issue (GitHub assigns the number)

**STOP** — show the title, body and labels and ask for confirmation first. The issue is public.

```bash
REPO="cassandragargoyle/portunix-ireco"
gh issue create --repo "$REPO" \
  --title "<TITLE>" \
  --body "<SHORT DESCRIPTION>

📄 Full details: docs/issues/<NNN>-<slug>.md" \
  --label <type>,<priority>
```

`gh issue create` prints the URL — take the **number `N`** from it
(`.../issues/12` → `NNN=012` for the file name, `#12` on GitHub).

## STEP 4: Write the detail file

Create `docs/issues/<NNN>-<slug>.md` with the full content (template in
[ISSUE-MANAGEMENT.md](../../../docs/contributing/ISSUE-MANAGEMENT.md#detail-file-template)):

```markdown
# Issue #<N>: <Title>

## Summary

<1–3 sentences>

**Status**: 📋 Open
**Type**: <type>
**Priority**: <priority>
**Component**: <component>
**Created**: <YYYY-MM-DD>
**GitHub**: #<N>
**Related**: #<...>

## Problem Description

## Acceptance Criteria

1. ...

## Testing
```

## STEP 5: Put the exact link into the GitHub issue

```bash
URL="https://github.com/$REPO/blob/main/docs/issues/<NNN>-<slug>.md"
gh issue edit <N> --repo "$REPO" \
  --body "<SHORT DESCRIPTION>

📄 [Full details](${URL})"
```

> The link starts working once the file is on `main` on GitHub.

## STEP 6: Summary

```text
Issue #<N> created.

GitHub:  https://github.com/cassandragargoyle/portunix-ireco/issues/<N>
Detail:  docs/issues/<NNN>-<slug>.md
Type/Priority: <type> / <priority>

Next steps:
  /implement-issue <N>
```

## Notes

- **Never invent the number** — GitHub always assigns it. Issues and PRs share one counter.
- Archiving a finished issue: `gh issue close <N>` +
  `git mv docs/issues/<NNN>-*.md docs/issues/done/`.
- Full methodology: `docs/contributing/ISSUE-MANAGEMENT.md`.
