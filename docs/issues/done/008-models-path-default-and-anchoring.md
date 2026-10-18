# Issue #8: models.path Default and Example Are Wrong; Worker and Watcher Resolve a Relative Path Differently

## Summary

`models.path` in `ireco.config.json` is the root that contains `models/invoice/`, and
without the key the root is the current working directory. The watcher documentation and
the schema describe the default as "cwd ./models" and show `"path": "./models"`, which the
runtime reads as `./models/models/invoice/`. A relative `models.path` is also anchored at
the config file by `ptx-ireco-watcher` but at the current working directory by
`ptx-ireco-worker`.

**Status**: ✅ Implemented
**Type**: Bug
**Priority**: Low
**Component**: `docs/cli/watcher.md`, `docs/cli/worker.md`,
`docs/schemas/ireco-config-1.0.json`, `ptx_ireco.watcher.config`,
`ptx_ireco.cli.worker_main`, `ptx_ireco.config.schema`
**Created**: 2026-10-18
**Closed**: 2026-10-18 — acceptance: [`docs/testing/acceptance-008.md`](../../testing/acceptance-008.md) (STATUS PASS)
**GitHub**: #8
**Related**: #3 (worker), #4 (watcher)

## Problem Description

### How the runtime reads `models.path`

- `ModelPaths.default(root)` (`pipeline/extract.py`) builds
  `root/models/invoice/{templates,profiles,extraction}`
- `cli/worker_main._resolve_repo_root`: `--models` flag, then `models.path`, then
  `Path.cwd()`; a relative value is returned as is, so it is resolved against the current
  working directory
- `watcher/config.WatchConfig._resolve_models_path`: a relative value is anchored at the
  directory of the config file

So the default root is the current working directory (models in `./models/invoice/`),
and `"path": "./models"` points to `./models/models/invoice/`.

### Places that say something else

| Place | Text | Problem |
| --- | --- | --- |
| `docs/cli/watcher.md:79-80` | `"models": { // optional; defaults to cwd ./models` and `"path": "./models"` | Wrong default; the example reads `./models/models/invoice/` |
| `docs/cli/watcher.md:94` | `models.path` default `cwd ./models`, "anchored at the config file" | Wrong default; the anchoring is true for the watcher only |
| `docs/schemas/ireco-config-1.0.json:122` | `"Optional location of the models tree. Absent → cwd ./models."` | Wrong default |
| `src/ptx_ireco/config/schema.py:36` | `MODELS_DEFAULT_PATH = "./models"` | Not used anywhere, and the value is wrong |
| `docs/cli/worker.md:64-65` | "this `models` section is reserved for issue 004; until then, use the flag" | Out of date: the worker reads `models.path` |

### Reproduction

Run from an empty directory `other/`, with the config in `cfgdir/ireco.config.json`:

```python
from argparse import Namespace
from pathlib import Path
from ptx_ireco.pipeline.extract import ModelPaths
from ptx_ireco.watcher.config import WatchConfig
from ptx_ireco.cli.worker_main import _resolve_repo_root

ModelPaths.default(_resolve_repo_root(Namespace(models=None), {})).templates
# -> other/models/invoice/templates
ModelPaths.default(_resolve_repo_root(Namespace(models=None), {"models": {"path": "./models"}})).templates
# -> other/models/models/invoice/templates
WatchConfig._resolve_models_path("./m", Path("cfgdir/ireco.config.json"))
# -> cfgdir/m          (watcher: anchored at the config file)
Path(_resolve_repo_root(Namespace(models=None), {"models": {"path": "./m"}})).resolve()
# -> other/m           (worker: anchored at the current working directory)
```

The same `ireco.config.json` with a relative `models.path` therefore finds the models in
one place when the watcher runs the pipeline and in another place when the worker is
started by hand from another directory.

### Downstream

`portunix-reco-studio` keeps a byte-equal copy of `docs/schemas/ireco-config-1.0.json`;
it takes over the corrected description after this issue is merged. Its own
`ireco-config` CLI page already describes the runtime behavior as it is today.

## Acceptance Criteria

1. One anchoring rule for a relative `models.path` in the worker and the watcher —
   proposed: the directory of the config file (as the watcher does today); a path given
   with `--models` stays relative to the current working directory
2. `docs/cli/watcher.md` (comment, example, table) and the description in
   `docs/schemas/ireco-config-1.0.json` state the real default (the current working
   directory, models in `./models/invoice/`) and the anchoring rule; the example does not
   use `"./models"`
3. `MODELS_DEFAULT_PATH` is removed, or used with a correct value
4. `docs/cli/worker.md` describes `models.path` without the "reserved for issue 004" text
5. Tests cover the default root and a relative `models.path` for both the worker and the
   watcher

## Testing

- Unit tests for `_resolve_repo_root` and `WatchConfig._resolve_models_path` with an
  absolute, a relative and a missing `models.path`, run from a directory other than the
  directory of the config file
- The reproduction above gives the same root for the worker and the watcher
- The examples of `docs/cli/watcher.md` validate against the schema
- markdownlint
