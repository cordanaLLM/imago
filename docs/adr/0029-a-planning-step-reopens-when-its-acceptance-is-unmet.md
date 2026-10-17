# 29. A Planning Step Reopens When Its Acceptance Is Unmet

Date: 2026-10-17

## Status

Accepted. Amends [ADR-0025](0025-forge-as-record-of-open-work-and-frozen-planning-graph.md) decisions 2 and 3.

## Context

ADR-0025 froze `planning/routing.json`: the overlay changes only to mark an open step done, with the pull request as evidence. It did not provide for the opposite case.

`step-nucleus-contract` was marked done on 2026-09-15 with evidence that names only imago-side code: the `pkg/kernel` decoder and verifier, the `imago kernel` CLI and `sync-kernel-manifest.yml`. Issue [#47](https://github.com/cordanaLLM/imago/issues/47) shows that the contract has never been crossed. The workflows could not start, `versions.json` `kernel.streams` is empty, and no nucleus release has been verified against the contract. [`planning/TODO.md`](../../planning/TODO.md) lists the contract as open. A graph that states done while the acceptance is unmet tells a reader the opposite of the forge.

The overlay had also fallen behind in the direction ADR-0025 allows. Issues [#80](https://github.com/cordanaLLM/imago/issues/80) and [#81](https://github.com/cordanaLLM/imago/issues/81) closed on 2026-10-17, while `step-lefthook-verify` and `step-app-hardening` still read open. No test compared the overlay with the table of carried steps in [`docs/tools/planning-graph.md`](../tools/planning-graph.md).

## Decision

1. **A step whose acceptance is unmet is reopened.** Its `done` field becomes `false`. Its `evidence` keeps what was delivered, states what is missing, and names the issue that carries it. No step is added. The graph stays a frozen record in every other respect. The maintainer decided this on 2026-10-17 (paraphrased: the graph stays honest rather than convenient; the step reads open until the first nucleus release crossing the contract is verified).
2. **`step-nucleus-contract` is carried by #47.** It closes when a nucleus release crosses the contract and imago verifies it.
3. **The overlay and the documentation agree by test.** `tests/test_planning_overlay.py` fails in three cases: an open step names no carrying issue, the table in `docs/tools/planning-graph.md` lists other open steps or other issues than the overlay, or the done count in that file differs from the overlay.

## Consequences

- **Positive**: the overlay states the same open work as the forge. `step-lefthook-verify` and `step-app-hardening` are done with their pull requests as evidence, and the reopened step names its issue.
- **Positive**: a step marked done or reopened in one file without the other fails the test suite.
- **Negative**: the test cannot see whether a carrying issue has closed, because the forge is not reachable offline. A closed issue whose step still reads open is caught only when the overlay is next edited, or by a reader.
- **Neutral**: `imago plan route` now lists `step-nucleus-contract` among the open steps. It has `needs_external_contract`, so the router ranks it behind local work.

## References

- [ADR-0021](0021-pinned-kernel-artifact-contract-with-nucleus.md): the kernel artifact contract with `cordanaLLM/nucleus`.
- [ADR-0025](0025-forge-as-record-of-open-work-and-frozen-planning-graph.md): the frozen planning graph.
- Fleet answer ledger, id `imago-47-nucleus-step`, 2026-10-17: reopen the step (paraphrased).
