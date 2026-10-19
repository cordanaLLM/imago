# 36. Required Checks Count Run Time, Not Queue Time

Date: 2026-10-19

## Status

Accepted. Amends [ADR-0027](0027-pull-request-jobs-never-skip-path-filter-per-job.md) and [ADR-0035](0035-required-checks-wait-only-for-gate-workflows.md) in how long `required-checks` waits; what it waits for and what it accepts stay as they decided.

## Context

`required-checks` ran `lewagon/wait-on-check-action` under a job bound of 30 minutes. That bound started when the aggregator job started, so time a gate check spent queued for a runner counted against it.

On 2026-10-19 the runners of the repository were backed up. On pull request #182 the aggregator started at 03:04Z, five gate checks were still queued at 03:33Z, and the job was cancelled at 03:34Z (run 39190971221). Pytest started at 04:06Z and every gate check succeeded. Pull request #181 showed the same pattern (run 39182790940). Each time the required context went red although no check had failed, and only a rerun of the job turned it green.

## Decision

1. **A repository script waits.** `tools/ci/wait_gate_checks.py` replaces the action. It reads the check runs of the commit through an HTTPS-only opener, keeps the newest run per name, leaves out its own job and keeps the names the `KEEP_CHECKS` pattern matches (the ADR-0035 filter, unchanged). Once every gate check has completed, a conclusion other than `success` fails the wait (ADR-0027), as the action did.
2. **Queue time never counts.** Each gate check has its own clock of 30 minutes, which starts at its own `started_at` and runs only while the check is `in_progress`. A queued check run already reports its creation time as `started_at`, and the forge moves the value to the job start once a runner takes it (check run 117902985607: `started_at` 06:00:44Z, job created 05:20:52Z), so a check that is still queued has no clock running. 30 minutes is the largest `timeout-minutes` of any gate job, so a check that runs longer is stuck.
3. **A scalar outer bound stays.** The whole wait ends after 120 minutes of wall clock, so a check that never starts fails the wait instead of holding it open (HISS-02). 120 minutes leaves room for twice the longest measured backlog (62 minutes, Pytest on #182). The job bound is 125 minutes, just above the script's own bound.
4. **Tests hold the clocks.** `tests/test_wait_gate_checks.py` runs the script on a simulated forge and clock. A gate check queued for 40 minutes that then succeeds must pass. A gate check that never starts must fail at 120 minutes. A check that runs past its own 30 minutes, or ends in another conclusion, must fail. Each planted change to the clocks, the conclusion rule, the name filter or the job bound turns at least one test red.

## Consequences

- **Positive**: a runner backlog no longer turns the required context red. A failing or stuck check still fails it.
- **Positive**: as in the action, conclusions are judged only once every gate check has completed, so the CodeQL check of code scanning, which is updated in place while its analyses upload, is read at its final state (run 39198928256 failed on an early read before this rule was kept).
- **Negative**: the wait logic is repository code now, about 170 lines, and moves with the API instead of with an action release.
- **Neutral**: the job checks out the repository to run the script and reads check runs with `checks: read`.

## References

- [ADR-0027](0027-pull-request-jobs-never-skip-path-filter-per-job.md) and [ADR-0035](0035-required-checks-wait-only-for-gate-workflows.md).
- Runs 39190971221 (#182) and 39182790940 (#181): `required-checks` cancelled after 30 min while gate checks were still queued.
- Run 39204073732 (#182, first version of the script): five gate checks created at 05:20Z and still queued were failed as running longer than 30 min at 05:51Z, because the clock read `started_at` of queued check runs.
- GitHub REST API, "List check runs for a Git reference" (`GET /repos/{owner}/{repo}/commits/{ref}/check-runs`).
