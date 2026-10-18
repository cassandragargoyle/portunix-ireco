# GitHub Workflow for portunix-ireco

`portunix-ireco` is developed directly on **GitHub** — it is the single source of truth for code,
issues, and pull requests. There is no separate internal server and no sync/publish scripts.

> History: the project was previously developed on a self-hosted Gitea server with issues tracked
> in `docs/issues/internal/`. On 2026-10-18 the current state was imported to GitHub as a new root
> commit (without the Gitea history) and the issues were mirrored 1:1 (`007` = `#7`). The Gitea
> repository is kept as a read-only archive.

## Everyday Development

```bash
# Work on a branch off main (N = GitHub issue number)
git switch -c feature/N-short-name

# Commit as you go
git add .
git commit -m "feat(N): short description"

# Push the branch to GitHub
git push -u origin feature/N-short-name
```

Merge into `main` only after the tester acceptance protocol shows PASS — see
[ISSUE-DEVELOPMENT-METHODOLOGY.md](ISSUE-DEVELOPMENT-METHODOLOGY.md). Merge directly or through
a Pull Request (`gh pr create`).

## Remotes

```text
origin -> https://github.com/cassandragargoyle/portunix-ireco   (development + issues)
```

## Public Repository

The repository is public. Do not commit customer documents, real company identifiers taken
from real documents, personal data, credentials, internal hostnames, or absolute local paths.
Sample invoices under `samples/` must contain fictional party data only.

## Issues

Issues are GitHub-first — see [ISSUE-MANAGEMENT.md](ISSUE-MANAGEMENT.md) and the
`/create-issue` skill.
