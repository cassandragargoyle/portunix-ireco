# Contributing to portunix-ireco

Thank you for considering a contribution. This file is the entry point —
the full set of guidelines lives under
[`docs/contributing/`](docs/contributing/).

`portunix-ireco` is a Python project (package `ptx-ireco`) that adds
invoice extraction on top of
[portunix-reco](https://github.com/cassandragargoyle/portunix-reco)
(package `ptx-reco`).

## Quick Start

1. **Pick or open an issue** — browse
   [open issues](https://github.com/cassandragargoyle/portunix-ireco/issues)
   or open a new one describing the change you want to make. Non-trivial
   changes should have an issue first so the scope can be agreed on
   before code is written. Issues are **GitHub-first**: the GitHub issue
   is created first (GitHub assigns the number `N`), and the long-form
   write-up lives in `docs/issues/NNN-name.md` (`NNN` = `N` zero-padded
   to three digits). See
   [ISSUE-MANAGEMENT.md](docs/contributing/ISSUE-MANAGEMENT.md).

2. **Fork and clone** — `ptx-reco` is resolved from a sibling checkout
   (`[tool.uv.sources]` in `pyproject.toml` points to `../portunix-reco`),
   so clone both repositories next to each other:

   ```bash
   git clone https://github.com/cassandragargoyle/portunix-reco.git
   git clone https://github.com/<your-user>/portunix-ireco.git
   cd portunix-ireco
   ```

3. **Create a branch** following the project convention (issue number
   zero-padded to three digits, `#8` → `008`):

   ```bash
   git switch -c feature/NNN-short-name   # features and enhancements
   git switch -c fix/NNN-short-name       # bug fixes
   ```

4. **Set up the development environment** — Python 3.11+ and
   [uv](https://docs.astral.sh/uv/):

   ```bash
   ./scripts/setup-venv.sh                # creates .venv via uv
   uv pip install -e ".[dev]"             # package + dev tools
   ```

   Optional, for OCR of scanned PDFs (issue #7): Tesseract and Poppler
   on `PATH`, plus the `pdf2image` Python package. Tests that need them
   are marked `requires_tesseract` / `requires_pdf2image` and are skipped
   when the prerequisite is missing.

5. **Build and test** — always run tools through `uv run`:

   ```bash
   uv run pytest                          # full test suite (tests/unit + tests/e2e)
   uv run pytest tests/unit               # unit tests only
   uv run pytest --cov=ptx_ireco          # with coverage (target: 80 %)
   uv run black --check src tests         # formatting (line length 120)
   uv run isort --check-only src tests    # import order
   uv run flake8 src tests                # style
   uv run mypy src                        # type checks
   make lint-md                           # Markdown lint (markdownlint-cli2)
   ```

6. **Commit and push** using Conventional-Commit-style messages with the
   issue number as scope: `feat(N): …`, `fix(N): …`, `docs(N): …`,
   `test(N): …`. Push the branch to your fork (or to `origin` if you
   have write access).

7. **Open a Pull Request** into `main`. A branch is merged only after a
   tester has created an acceptance protocol
   `docs/testing/acceptance-NNN.md` with **PASS** status — see
   [ISSUE-DEVELOPMENT-METHODOLOGY.md](docs/contributing/ISSUE-DEVELOPMENT-METHODOLOGY.md).

## Ground Rules

- All code, comments, commit messages, and PR descriptions are written in
  **English**. Other languages are welcome in private team communication;
  documents under `.translated/` carry temporary localized copies, and
  permanent companion files (`README.cs.md`, `README.sk.md`) point back
  at the English source as the authoritative version.
- Follow existing conventions — explore the codebase before introducing
  new patterns. See the
  [Python style guide](docs/contributing/CODE-STYLE-PYTHON.md).
- Write tests for new features and bug fixes. See
  [TESTING-PYTHON.md](docs/contributing/TESTING-PYTHON.md) and
  [TESTING_METHODOLOGY.md](docs/contributing/TESTING_METHODOLOGY.md).
- **The repository is public.** Do not commit customer documents, real
  company identifiers taken from real documents, personal data,
  credentials, internal hostnames, or absolute local paths. Sample
  invoices under `samples/` must contain fictional party data only.
- Do not add `Co-Authored-By` attributions for AI tools in commits.
- Do not add `Generated with [Claude Code]` (or similar AI-tool)
  signatures to source files.

## Detailed Guidelines

The `docs/contributing/` directory contains the full set of project
standards:

- [Issue Management](docs/contributing/ISSUE-MANAGEMENT.md) — GitHub-first
  issues and `docs/issues/` write-ups
- [Issue Development Methodology](docs/contributing/ISSUE-DEVELOPMENT-METHODOLOGY.md)
  — developer / tester roles and the acceptance protocol
- [GitHub Workflow](docs/contributing/GITHUB-WORKFLOW.md) and
  [Git Workflow](docs/contributing/GIT-WORKFLOW.md)
- [Bug Reporting](docs/contributing/BUG-REPORTING.md)
- [Naming Conventions](docs/contributing/NAMING-CONVENTIONS.md)
- [Terminology](docs/contributing/TERMINOLOGY.md)
- [AI Assistants](docs/contributing/AI-ASSISTANTS.md) — using Claude
  Code and other AI assistants on this codebase
- [Translation Workflow](docs/contributing/TRANSLATION-WORKFLOW.md)
- [`.gitignore` Guidelines](docs/contributing/GITIGNORE.md)
- [Tools Recommendations](docs/contributing/TOOLS-RECOMMENDATIONS.md)

Architectural decisions are recorded in [`docs/adr/`](docs/adr/);
CLI commands are documented in [`docs/cli/`](docs/cli/).

## Reporting Bugs and Requesting Features

- **Bugs** — open an issue using the bug reporting guidelines in
  [BUG-REPORTING.md](docs/contributing/BUG-REPORTING.md). Include:
  - The `ptx-ireco` version (from `pyproject.toml`) and the `ptx-reco`
    version in use
  - OS and Python version (and Tesseract / Poppler versions for OCR
    problems)
  - The command you ran (`ptx-ireco parse`, `extract`, `run`, worker or
    watcher) and the relevant `ireco.config.json` settings
  - Steps to reproduce, ideally with a **fictional** sample invoice
  - Expected vs. actual behavior
  - Relevant logs or error output (with personal and company data
    removed)
- **Feature requests** — open an issue describing the use case and the
  motivation. For substantial changes, propose an ADR in
  [`docs/adr/`](docs/adr/) alongside the request.

## Security

For security-sensitive reports, please **do not open a public issue**.
Instead, contact the maintainers privately — see the
[CassandraGargoyle team](https://github.com/cassandragargoyle) page for
contact options.

## License

By contributing to portunix-ireco you agree that your contributions
will be licensed under the [MIT License](LICENSE). Project governance —
maintainer, contributors, and succession — is described in
[GOVERNANCE.md](GOVERNANCE.md).
