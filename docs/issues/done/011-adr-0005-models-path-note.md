# Issue #11: ADR 0005 Shows the Old models.path Example and Default

## Summary

ADR 0005 still shows `"models": { "path": "./models" }` and suggests the default
"cwd `./models`". Since #8 the default root is the current working directory (models in
`./models/invoice/`), and a relative `models.path` is anchored at the directory of the
config file. The ADR gets a short "superseded in part" note that points to #8.

**Status**: ✅ Implemented
**Type**: Documentation
**Priority**: Low
**Component**: `docs/adr/0005-ireco-plugin-split.md`
**Created**: 2026-10-18
**Closed**: 2026-10-18 — acceptance: [`docs/testing/acceptance-011.md`](../../testing/acceptance-011.md) (STATUS PASS)
**GitHub**: #11
**Related**: #8 (finding F1 in `docs/testing/acceptance-008.md`)

## Problem Description

`models.path` is the root that contains `models/invoice/`. Issue #8 fixed the default and
the anchoring rule in the runtime, in `docs/cli/watcher.md`, `docs/cli/worker.md` and in
`docs/schemas/ireco-config-1.0.json`. ADR 0005 was not in the scope of #8 and still says
the old thing:

| Place | Text | Problem |
| --- | --- | --- |
| `docs/adr/0005-ireco-plugin-split.md:207-208` | `"path": "./models"  // root containing models/invoice/{templates,profiles,extraction}` | The runtime reads this as `./models/models/invoice/` |
| `docs/adr/0005-ireco-plugin-split.md:318-320` | precedence "`--models` flag → `models.path` → cwd `./models`" | The default root is cwd (models in `./models/invoice/`); a relative `models.path` is anchored at the config file |

An ADR is a record of a decision, so the decision text stays as it is. The ADR already
uses a "superseded in part" note in its `Status` line for ADR-0006; the same pattern is
used here.

### Downstream (not part of this issue)

`portunix-reco-studio` keeps a byte-equal copy of `docs/schemas/ireco-config-1.0.json`
and must take over the corrected descriptions from #8 (finding F2 in
`docs/testing/acceptance-008.md`). That work belongs to the `portunix-reco-studio`
repository.

## Acceptance Criteria

1. The `Status` line of ADR 0005 has a "superseded in part" note for the `models.path`
   default and anchoring, with a link to #8 and to `docs/cli/watcher.md`
2. The example at lines 207-208 has a short comment or note that marks it as outdated
   and gives the correct meaning (root that contains `models/invoice/`)
3. The precedence text at lines 318-320 has a short note with the real default
   (cwd, models in `./models/invoice/`) and the anchoring rule
4. The original decision text is not rewritten

## Testing

- `npx markdownlint-cli2 docs/adr/0005-ireco-plugin-split.md` — no new findings
  (note: `docs/adr/**` is excluded in the default glob; lint the file explicitly)
- `grep -rn '"path": "./models"' docs` outside `docs/issues/` shows only the ADR example
  with its outdated note
- Links in the new notes resolve
