---
name: commit
description: Create a git commit for current changes.
argument-hint: "[commit message]"
disable-model-invocation: true
---

# Commit

Optional argument: **$ARGUMENTS** (commit message override)

**IMPORTANT:**

- NEVER include AI-generated markers in commit messages
- DO NOT add "Generated with Claude Code" or similar markers
- DO NOT add "Co-Authored-By: Claude <noreply@anthropic.com>"
- Keep commit messages clean and professional

## Instructions

1. **Analyze changes** — run `git status` and `git diff --staged` and `git diff` to understand what changed
2. **Check recent commits** — run `git log --oneline -10` to follow existing commit message style
3. **Stage relevant files** — add changed/new files by name (avoid `git add -A`)
   - Do NOT stage files containing secrets (.env, credentials, etc.)
4. **Draft commit message** — follow the repository's conventional commit style:
   - Format: `type(scope): description`
   - Types: feat, fix, refactor, test, docs, chore
   - Keep first line under 72 characters
   - Add body if needed for context
5. **If $ARGUMENTS is provided** — use it as the commit message instead of drafting one
6. **Create the commit** — use HEREDOC format for the message
7. **Verify** — run `git status` after commit to confirm success
