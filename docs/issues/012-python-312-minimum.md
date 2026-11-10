# Issue #12: Python Minimum 3.11 Does Not Match ptx-reco (Requires 3.12)

## Summary

`pyproject.toml` and the plugin manifests declare Python 3.11 as the minimum, but `ptx-reco`
requires Python 3.12. `uv lock` fails on the Python 3.11 split. The minimum is raised to 3.12.

**Status**: 🔄 In Progress
**Type**: Bug
**Priority**: Low
**Component**: `pyproject.toml`, `plugin-worker.json`, `plugin-watcher.json`, `CONTRIBUTING.md`,
`README.md`, `uv.lock`, `scripts/setup-venv.sh` (removed)
**Created**: 2026-11-10
**GitHub**: #12
**Related**: cassandragargoyle/portunix-reco#61 (observation O19 of its acceptance),
cassandragargoyle/portunix-reco-studio#95 (same change)

## Problem Description

`ptx-reco` declares `requires-python = ">=3.12"` since its first commit. This project declares
`>=3.11`, so `uv lock` resolves a split for Python 3.11 and fails:

```text
Because the requested Python version (>=3.11) does not satisfy Python>=3.12 and
ptx-reco==0.3.13 depends on Python>=3.12, we can conclude that ptx-reco==0.3.13 cannot be used.
```

The plugin manifests declare `"python_min_version": "3.11"`, so Portunix would accept a system
on which `ptx-reco` cannot be installed.

## Changes

| File | Change |
| ---- | ------ |
| `pyproject.toml` | `requires-python = ">=3.12"`, black `target-version = ["py312"]`, mypy `python_version = "3.12"` |
| `plugin-worker.json`, `plugin-watcher.json` | `"python_min_version": "3.12"` |
| `CONTRIBUTING.md` | Python 3.12+; note on `uv.lock` drift from the sibling `../portunix-reco` checkout (acceptance O2) |
| `pyproject.toml` | `[dependency-groups] dev = ["ptx-ireco[dev]"]`, so a plain `uv sync` installs the dev tools (as in `portunix-reco`) |
| `scripts/setup-venv.sh` | Removed (acceptance O1): its examples showed `3.11`, and it only wrapped `uv venv` + `uv sync`; `portunix-reco` has no such script |
| `CONTRIBUTING.md`, `README.md` | Set up with a plain `uv sync`, run the CLI with `uv run` (as in `portunix-reco`) |
| `uv.lock` | Regenerated: no Python 3.11 split (`tomli` removed); `ptx-reco` dependencies of `portunix-reco` `main` (incl. `certifi`, `pypdf>=6.21.4` from portunix-reco#123); `dev` group |

The archived issue files in `docs/issues/done/` keep 3.11, as they record the state of their time.

## Acceptance Criteria

1. `uv lock` succeeds.
2. No file outside `docs/issues/done/` declares Python 3.11 as the minimum.
3. All tests pass.

## Testing

```bash
uv lock --check
uv run --frozen pytest -q
```

Result on 2026-11-10: `uv lock` succeeds, 312 tests pass.
