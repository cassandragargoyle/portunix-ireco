# Git Workflow for portunix-ireco

## Overview

This document describes the Git workflow and branching strategy for portunix-ireco.
The repository lives on GitHub (see [GITHUB-WORKFLOW.md](GITHUB-WORKFLOW.md)); the
full issue lifecycle is described in
[ISSUE-DEVELOPMENT-METHODOLOGY.md](ISSUE-DEVELOPMENT-METHODOLOGY.md).

## Branch Structure

### Main Branch

- `main` - The only long-lived branch. It always contains tested code that passed
  an acceptance protocol. There is no `develop` branch.

### Supporting Branches

Every change is made on a short-lived branch off `main`, named after its GitHub
issue. `NNN` is the issue number zero-padded to three digits (`#8` → `008`):

- `feature/NNN-short-name` - New features and enhancements
- `fix/NNN-short-name` - Bug fixes

## Workflow Process

### 1. Feature or Fix Development

```bash
# Start from an up-to-date main
git switch main
git pull origin main
git switch -c feature/008-short-name

# Work on the change
git add <files>
git commit -m "feat(8): short description"
git push -u origin feature/008-short-name
```

### 2. Testing and Merge

1. The tester checks out the branch, runs the tests, and creates the acceptance
   protocol `docs/testing/acceptance-NNN.md`.
2. Only with **PASS** status the branch is merged into `main`, directly or through
   a Pull Request (`gh pr create`).
3. The issue file is archived to `docs/issues/done/` and the GitHub issue is closed.
4. The branch is deleted after the merge.

The developer **must not** merge into `main` before the tester approves.

### 3. Critical Hotfixes

A critical hotfix uses a normal `fix/NNN-short-name` branch. It may bypass the
regular testing phase only with architect approval; a retroactive acceptance
protocol is required within 24 hours.

### 4. Releases

```bash
# On main, after all included issues are merged
# 1. Bump the version in pyproject.toml ([project].version)
git commit -am "chore: release v0.2.0"
git tag -a v0.2.0 -m "Release version 0.2.0"
git push origin main --tags
```

## Commit Guidelines

### Message Format

```text
<type>(<issue-number>): <description>

<body>

<footer>
```

The scope is the GitHub issue number without padding (`feat(8): …`). Changes that
do not belong to an issue omit the scope (`docs: …`).

### Types

- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `style` - Code formatting
- `refactor` - Code restructuring
- `test` - Adding tests
- `chore` - Maintenance tasks

### Examples

```bash
git commit -m "feat(7): add per-page OCR fallback for scanned PDFs"
git commit -m "fix(8): anchor relative models.path at the config file"
git commit -m "docs(8): close issue — archive to done/"
git commit -m "docs: use zero-padded issue numbers in branch names"
```

### Attribution

Do not add `Co-Authored-By` lines for AI tools to commits.

## Pull Request Process

### Requirements

- [ ] Branch is up to date with `main`
- [ ] All tests pass (`uv run pytest`)
- [ ] Code follows the [Python style guide](CODE-STYLE-PYTHON.md)
- [ ] Documentation is updated (`docs/cli/`, `docs/adr/`, issue file)
- [ ] Acceptance protocol `docs/testing/acceptance-NNN.md` shows **PASS**
- [ ] No customer data, real company identifiers, or personal data (public repository)

### Template

```markdown
## Description
Brief description of changes

Closes #N

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] E2E tests pass
- [ ] Acceptance protocol: docs/testing/acceptance-NNN.md

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
```

## Git Configuration

### User Setup

The repository is public. Use your GitHub noreply e-mail address to keep your
personal address out of the history:

```bash
git config user.name "Your Name"
git config user.email "<id>+<user>@users.noreply.github.com"
```

### Aliases

```bash
git config --global alias.st status
git config --global alias.co checkout
git config --global alias.br branch
git config --global alias.unstage 'reset HEAD --'
git config --global alias.last 'log -1 HEAD'
```

### Hooks

```bash
#!/bin/bash
# Pre-commit hook
set -e
uv run black --check src tests
uv run isort --check-only src tests
uv run flake8 src tests
uv run pytest tests/unit -q
```

## Best Practices

### Do

- Write clear commit messages with the issue number
- Keep commits atomic and focused
- Rebase feature branches on `main` before merging
- Use meaningful branch names
- Review your own changes before requesting review

### Don't

- Commit directly to `main`
- Merge without a PASS acceptance protocol
- Push broken code
- Mix multiple issues in one branch
- Use generic commit messages
- Force push to shared branches

## Troubleshooting

### Common Issues

```bash
# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes)
git reset --hard HEAD~1

# Fix commit message
git commit --amend -m "New message"

# Merge conflicts
git status
# Edit conflicted files
git add <files>
git commit
```

---

*Follow this workflow to maintain clean Git history and efficient collaboration.*
