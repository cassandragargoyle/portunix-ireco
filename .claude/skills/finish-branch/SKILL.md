---
name: finish-branch
description: Finish work on a feature branch - merge into the main branch, clean up the branch and optionally update the issue status.
disable-model-invocation: true
---

# Finish Branch

**IMPORTANT: NEVER add "Co-Authored-By: Claude <noreply@anthropic.com>" to code files or git commits.**

## STEP 1: Get the context

Ask me for:

1. The feature branch name (or use the current branch)
2. The target branch for the merge (usually `main`)

Verify that the branch exists and contains commits.

## STEP 2: Merge and cleanup

> **What is a PR (Pull Request)?** A request to integrate changes from a feature branch into the main branch. It is used for code review in teams. For solo development you can merge directly.

> **IMPORTANT — Quality Gate:** According to
> [ISSUE-DEVELOPMENT-METHODOLOGY.md](../../../docs/contributing/ISSUE-DEVELOPMENT-METHODOLOGY.md)
> you MUST NOT merge into `main` without an existing tester acceptance protocol
> (`docs/testing/acceptance-<NNN>.md` with status `PASS`). Before the merge, verify
> that the protocol exists and has `STATUS: PASS` and `Approval for merge: YES`.

Ask the user for the preferred approach:

### Option A: Direct merge (after tester approval)

Find the source branch (the branch the feature branch was created from) and run the merge:

```bash
git checkout <source-branch>    # usually main
git merge feature/<N>-<description>
git branch -d feature/<N>-<description>
```

**STOP** - Wait for confirmation before running the merge.

### Option B: Pull Request (for team collaboration)

Prepare the PR description:

- **Summary**: What this PR does
- **Motivation**: Why (link to the issue)
- **Changes**: List of changes
- **Testing**: Steps to verify (with a link to the acceptance protocol)

Create the PR with `gh pr create`.

## STEP 3: Update the issue (optional)

Ask the user: "Is the issue fully completed with this?"

### If YES

1. Edit the issue file `docs/issues/<NNN>-<slug>.md`:
   - Change `**Status**` to `✅ Implemented`
   - Add the closing date

2. Archive the file (and its verbatims file) into `done/` (keeps the git history).
   There are no README tables to update — the issue list lives on GitHub:

   ```bash
   git mv docs/issues/<NNN>-<slug>*.md docs/issues/done/
   ```

3. Commit the status change together with the move (one commit):

   ```text
   docs(<NNN>): close issue — archive to done/
   ```

4. Close the GitHub issue (`<N>` = number without zero padding):

   ```bash
   gh issue close <N> --repo cassandragargoyle/portunix-ireco \
     --comment "Implemented, acceptance: docs/testing/acceptance-<NNN>.md"
   gh issue edit <N> --repo cassandragargoyle/portunix-ireco --remove-label in-progress
   ```

### If NO

Skip the status update. The issue stays open for more work.

## STEP 4: Summary

Show a summary:

- Merge done into branch: `<name>`
- Feature branch deleted: yes/no
- Issue status updated: yes/no/skipped
- Next steps (if any)
