---
name: implement-issue
description: Guide for implementing an issue - from reading the assignment through creating a branch, implementing the code and committing, up to the merge into main and closing the issue.
disable-model-invocation: true
---

# Implement Issue

**IMPORTANT: NEVER add "Co-Authored-By: Claude <noreply@anthropic.com>" to code files or git commits.**

## STEP 0: Check the role

Check the current role in `CLAUDE.local.md`. If the role is not **Developer**:

1. Tell the user that implementation requires the Developer role
2. Offer to switch the role with the `/role developer` command
3. **STOP** - Do not continue until the Developer role is active

## STEP 1: Get the issue

Ask me for the GitHub issue number (e.g. `7` or `#7`). Wait for my answer.

## STEP 2: Confirm understanding

After I give you the issue:

1. Read the issue file `docs/issues/<NNN>-*.md` (active issues, `<NNN>` = number
   zero-padded to three digits). If it is not there, try `docs/issues/done/<NNN>-*.md` —
   it may be an already closed issue. Check the GitHub state and assignee with
   `gh issue view <N> --repo cassandragargoyle/portunix-ireco --json state,assignees,title`
2. Restate the issue in your own words
3. Explain the required code changes
4. Ask me for confirmation

**STOP** - Wait for my explicit confirmation before you continue.

## STEP 3: Create a branch

Create a git branch following the project convention (see
[ISSUE-DEVELOPMENT-METHODOLOGY.md](../../../docs/contributing/ISSUE-DEVELOPMENT-METHODOLOGY.md)):
`feature/<NNN>-<short-description>` or `fix/<NNN>-<short-description>`

- `<NNN>` is the GitHub issue number zero-padded to three digits (`#12` → `012`)
- Use lowercase letters and hyphens for the description (kebab-case)
- Example: `feature/012-isdoc-credit-notes`

Then assign the issue and mark it as in progress:

```bash
gh issue edit <N> --repo cassandragargoyle/portunix-ireco --add-assignee @me --add-label in-progress
```

Show the git command before you run it.

## STEP 4: Implementation

- Make all code changes in one continuous phase
- Do NOT ask questions unless something is really ambiguous
- Modify only relevant files
- Follow the project coding style

At the end, give a summary:

- Modified files
- Added methods/classes
- Removed code
- Key decisions

Ask me what I want:

- a) Accept as is
- b) Change specific parts
- c) Redo completely

**STOP** - Wait for my approval before you continue.

## STEP 5: Commit

Prepare the commit message:

```text
<type>(<issue-id>): <short summary>

- key change 1
- key change 2
```

Allowed types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

**STOP** - Ask me to confirm the commit message before committing.

## STEP 6: Merge and cleanup

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

### Option B: Pull Request (for team collaboration)

Prepare the PR description:

- **Summary**: What this PR does
- **Motivation**: Why (link to the issue)
- **Changes**: List of changes
- **Testing**: Steps to verify (with a link to the acceptance protocol)

## STEP 7: Update and archive the issue

1. Edit the issue file `docs/issues/<NNN>-<slug>.md`:
   - Change `**Status**` to `✅ Implemented`
   - Add the closing date

2. Archive the file (and its verbatims file) into `done/` (keeps the git history).
   There are no README tables to update — the issue list lives on GitHub:

   ```bash
   git mv docs/issues/<NNN>-<slug>*.md docs/issues/done/
   ```

3. Commit the status change together with the move (one commit). `git mv` stages only
   the move, so stage the edited file again before the commit:

   ```bash
   git add docs/issues/done/<NNN>-<slug>*.md
   ```

   ```text
   docs(<NNN>): close issue — archive to done/
   ```

4. Close the GitHub issue (`<N>` = number without zero padding):

   ```bash
   gh issue close <N> --repo cassandragargoyle/portunix-ireco \
     --comment "Implemented, acceptance: docs/testing/acceptance-<NNN>.md"
   gh issue edit <N> --repo cassandragargoyle/portunix-ireco --remove-label in-progress
   ```

5. Point the "Full details" link in the GitHub issue body to `done/`. The old link
   `blob/main/docs/issues/<NNN>-<slug>.md` returns 404 once the archive commit is on
   `main` on GitHub, so do this after the push or after the PR merge:

   ```bash
   REPO="cassandragargoyle/portunix-ireco"
   gh issue view <N> --repo "$REPO" --json body --jq .body \
     | sed 's#blob/main/docs/issues/<NNN>-#blob/main/docs/issues/done/<NNN>-#' \
     | gh issue edit <N> --repo "$REPO" --body-file -
   ```

   Check that the new link works (HTTP 200):

   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" \
     "https://github.com/$REPO/blob/main/docs/issues/done/<NNN>-<slug>.md"
   ```
