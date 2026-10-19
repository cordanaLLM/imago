# 35. Required Checks Wait Only for Gate Workflows

Date: 2026-10-19

## Status

Accepted. Amends point 5 of [ADR-0027](0027-pull-request-jobs-never-skip-path-filter-per-job.md).

## Context

`required-checks` waits for every other check on its commit and allows `success` only (ADR-0027). A workflow that runs on `workflow_dispatch` or `schedule` reports its check runs on the head of the ref it runs on. A manual `release-matrix.yml` build of one flavor on `main` therefore adds `Build Image (<flavor>)` to the head of `main`, and that job runs up to 240 minutes.

On 2026-10-18 the push run of `required-checks` on `bf068b6` (run 39169372316) waited for `Build Image (k3s-server-generic)` from release-matrix run 39169553684. After 30 minutes its job bound ended it as cancelled. The required context on that commit stayed red although every gate check had passed. `ce2ac0e` shows the same cancelled context (run 39096311174, also 30 minutes). A manual build that fails would also turn the head of `main` red, although no change on `main` caused it.

## Decision

1. **The wait step keeps only gate checks.** Gate workflows are the ones started by `push`, `pull_request` or `merge_group`. The wait step's `check-regexp` is a negative lookahead that leaves out the job names of every other workflow: `Build Image (`, `Sign the Release Checksums`, `Build, Boot, and Release Aegis OS Image` and `Verify and Pin Kernel Release from nucleus`. Each name is anchored, so a gate check whose name only starts the same way is still waited for.
2. **The workflows decide the list.** `tests/test_required_aggregator.py` reads each workflow's triggers and fails in either of two cases:
   - the filter drops a job of a gate workflow or a required context of `.github/rulesets/main.json`;
   - the filter keeps a job of a workflow that no gate event starts.

   A new dispatch-only workflow therefore needs its job name in the filter, in the same pull request.
3. **Everything else in ADR-0027 holds.** The aggregator still allows `success` only, accepts no skip, and sets neither `ignore-checks` nor `check-name`.

## Consequences

- **Positive**: a manual or scheduled build on `main` no longer cancels or fails the required context of the head commit. That build still reports its own result in its own run.
- **Negative**: renaming a job of a dispatch-only workflow changes the filter; the test fails until both agree.
- **Neutral**: a push to `main` while the aggregator waits still replaces the waiting run (`cancel-in-progress`). The older commit then keeps a cancelled context, as before this decision.

## References

- [ADR-0027](0027-pull-request-jobs-never-skip-path-filter-per-job.md): the no-skip aggregator this record amends.
- Runs 39169372316 (`required-checks`, cancelled after 30 min) and 39169553684 (`release-matrix`, `k3s-server-generic`).
- `lewagon/wait-on-check-action` v1.9.1, `app/services/github_checks_verifier.rb`: `check-regexp` keeps a check whose name the Ruby pattern matches.
