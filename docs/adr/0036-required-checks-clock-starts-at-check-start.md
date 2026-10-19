# 36. Required Checks Count Run Time, Not Queue Time

Date: 2026-10-19

## Status

Accepted. Amends [ADR-0027](0027-pull-request-jobs-never-skip-path-filter-per-job.md) and [ADR-0035](0035-required-checks-wait-only-for-gate-workflows.md) in how long `required-checks` waits; what it waits for and what it accepts stay as they decided.

## Context

`required-checks` ran `lewagon/wait-on-check-action` under a job bound of 30 minutes. That bound started when the aggregator job started, so time a gate check spent queued for a runner counted against it.

On 2026-10-19 the runners of the repository were backed up. On pull request #182 the aggregator started at 03:04Z, five gate checks were still queued at 03:33Z, and the job was cancelled at 03:34Z (run 39190971221). Pytest started at 04:06Z and every gate check succeeded. Pull request #181 showed the same pattern (run 39182790940). Each time the required context went red although no check had failed, and only a rerun of the job turned it green.

## Decision

1. **A repository script waits.** `tools/ci/wait_gate_checks.py` replaces the action. It reads the check runs of the commit through the API, keeps the newest run per name, leaves out its own job and keeps the names the `KEEP_CHECKS` pattern matches (the ADR-0035 filter, unchanged). A check that completed with any conclusion other than `success` fails the wait (ADR-0027).
2. **Queue time never counts.** Each gate check has its own clock of 30 minutes, which starts at its own `started_at`. A check that is still queued has no clock running. 30 minutes is the largest `timeout-minutes` of any gate job, so a check that runs longer is stuck.
3. **A scalar outer bound stays.** The whole wait ends after 120 minutes of wall clock, so a check that never starts fails the wait instead of holding it open (HISS-02). 120 minutes leaves room for twice the longest measured backlog (62 minutes, Pytest on #182). The job bound is 125 minutes, just above the script's own bound.
4. **Tests hold the clocks.** `tests/test_wait_gate_checks.py` runs the script on a simulated forge and clock. A gate check queued for 40 minutes that then succeeds must pass. A gate check that never starts must fail at 120 minutes. A check that runs past its own 30 minutes, or ends in another conclusion, must fail. Each planted change to the clocks, the conclusion rule, the name filter or the job bound turns at least one test red.

## Consequences

- **Positive**: a runner backlog no longer turns the required context red. A failing or stuck check still fails it.
- **Negative**: the wait logic is repository code now, about 170 lines, and moves with the API instead of with an action release.
- **Neutral**: the job checks out the repository to run the script and reads check runs with `checks: read`.

## References

- [ADR-0027](0027-pull-request-jobs-never-skip-path-filter-per-job.md) and [ADR-0035](0035-required-checks-wait-only-for-gate-workflows.md).
- Runs 39190971221 (#182) and 39182790940 (#181): `required-checks` cancelled after 30 min while gate checks were still queued.
- GitHub REST API, "List check runs for a Git reference" (`GET /repos/{owner}/{repo}/commits/{ref}/check-runs`).
