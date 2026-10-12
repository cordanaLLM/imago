# 26. Required Checks Accept Only Detector-Decided Skips

Date: 2026-10-12

## Status

Accepted

## Context

The rule set in `.github/rulesets/main.json` requires the `required-checks` job of `.github/workflows/required-aggregator.yml` ([ADR-0022](0022-fail-closed-provisioners-and-declared-main-protection.md)). That job waits for every other check on the commit and fails if one failed.

It passed `allowed-conclusions: success,skipped` to the wait action for every check. A skipped check therefore counted as passed whatever skipped it:

- **A wrong condition.** A job whose `if:` is false on pull requests never runs and still passes.
- **A failed dependency.** A job skipped because a job it needs failed passes, unless that dependency is itself required.
- **A path filter.** Seven jobs of `ci.yml` and two of `security-scans.yml` skip on pull requests when their change detector reports that no path they test changed. These skips are intended.

Only the third kind is a decision that the job is not affected. The other two hide a check that did not run.

## Decision

1. **A skip counts as passed only for the jobs a change detector gates.** `required-aggregator.yml` lists them by check name in `MAY_SKIP`. A job qualifies when it needs the job `changes` of its workflow and its `if:` is an alternation (`||`) of event-name comparisons and `needs.changes.outputs.<filter> == 'true'` terms.
2. **Every other check must succeed.** The first wait step ignores the listed names and allows only `success`. The second wait step matches the listed names exactly and allows `success` or `skipped`.
3. **A test holds the list.** `tests/test_required_aggregator.py` derives the qualifying jobs from all workflows and fails when `MAY_SKIP` differs. It also refuses planted conditions (no detector, `always()`, `&&`, negation) and runs the step that turns the list into the inputs of the wait action.
4. **The planted case stays in the pull request history.** The pull request that introduced this decision first added a workflow with an always-skipped job that no detector gates; the old aggregator passed it and the new one failed it.

## Consequences

- **Positive**: a check that silently stops running fails the required check instead of passing it.
- **Positive**: a detector-gated job that fails still fails the required check; only its skip is accepted.
- **Negative**: a new detector-gated job needs its name added to `MAY_SKIP`; the test names the missing job.
- **Neutral**: a failed change detector fails the required check by itself, since the detector jobs are not listed and must succeed.

## References

- [ADR-0022](0022-fail-closed-provisioners-and-declared-main-protection.md): the declared rule set that requires `required-checks`.
- `tests/test_required_aggregator.py`: the list check and the planted conditions.
