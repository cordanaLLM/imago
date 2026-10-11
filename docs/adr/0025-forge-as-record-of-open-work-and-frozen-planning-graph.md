# 25. The Forge as the Record of Open Work and a Frozen Planning Graph

Date: 2026-10-11

## Status

Accepted

## Context

[ADR-0019](0019-imago-fleet-migration-praetor-golusoris-planning-graph.md) tracked the migration to `cordanaLLM/imago` as a typed dependency graph under `planning/`, routed by `imago plan route`. The forge tracked the product in parallel: issues under milestones, checked on every pull request.

Two records of open work drifted apart:

- **The overlay went stale.** `planning/routing.json` listed `step-archetype-upstream` and `step-archetype-switch` as open for 26 days after [cordanaLLM/praetor#54](https://github.com/cordanaLLM/praetor/pull/54) and [#37](https://github.com/cordanaLLM/imago/pull/37) had delivered them.
- **Open steps had no issue.** Three open steps were visible only to a reader of `planning/`, so no milestone counted them.
- **Planned items had no home at all.** Accepted ADRs (0009, 0010, 0016, 0017, 0018) and principle 9.1 promise 18 items that neither the graph nor the forge listed.
- **The copied milestone file drifted.** `.github/milestones.json` named 30 flavors where the forge milestone names 44.

## Decision

1. **The forge is the record of open work.** Every open unit is an issue under a milestone. The maintainer decided this on 2026-10-11 (paraphrased: one source per fact; the open steps become issues, the in-repo graph is frozen as a migration record).
2. **The planning graph is frozen.** `planning/plan.json`, its projections and `planning/routing.json` stay as the record of the migration. No step is added. The overlay changes only to mark an open step done, with the pull request as evidence.
3. **The three open steps are carried by issues**: `step-lefthook-verify` by #80, `step-app-hardening` by #81 and `step-aegis-pair` by #46. The overlay names the issue in the `evidence` field.
4. **Planned items live under the milestone "Post-1.0 roadmap".** One issue per source records the promise and the state of the tree: #82 to #86 for the five ADRs, #87 for principle 9.1, #73 for an item of an earlier plan. Such an issue is a tracked home, not a scheduled unit; order and scope are decided after the 1.0 release.
5. **The router code stays.** `pkg/planning`, `imago plan validate`, `imago plan route` and the `route_plan` MCP tool are unchanged. Whether the fleet reuses the package is decided outside this repository. `AGENTS.md` no longer lists `imago plan route --ready` in the working sequence, because the ready set of open work is now the forge.
6. **`.github/milestones.json` is copied from the forge again**, including the new milestone and the note on the milestone that was closed without an issue.

## Consequences

- **Positive**: one place answers what is open. A milestone count is the count of open work.
- **Positive**: every public promise of an accepted ADR has an issue that states what exists.
- **Negative**: the overlay is updated by hand when one of the three issues closes. Three updates remain, and the file names the issue for each.
- **Negative**: nothing checks `.github/milestones.json` against the forge yet. A drift check is planned as its own unit.
- **Neutral**: ADR-0019 is not rewritten. Its decision 4 describes how the migration was tracked; this record states what holds from 2026-10-11 on.

## References

- [ADR-0019](0019-imago-fleet-migration-praetor-golusoris-planning-graph.md): the planning graph and its router.
- [`docs/tools/planning-graph.md`](../tools/planning-graph.md): the files, the routing policy and the table of carried steps.
- `GOVERNANCE.md`: milestones and the copied milestone file.
