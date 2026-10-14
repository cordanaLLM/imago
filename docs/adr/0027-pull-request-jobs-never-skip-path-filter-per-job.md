# 27. Pull Request Jobs Never Skip; Each Job Filters Its Own Paths

Date: 2026-10-14

## Status

Accepted. Supersedes [ADR-0026](0026-required-checks-accept-only-detector-decided-skips.md).

## Context

[ADR-0026](0026-required-checks-accept-only-detector-decided-skips.md) let `required-checks` accept a skip from the jobs a change detector gates. Each of `ci.yml` and `security-scans.yml` ran a `changes` job; ten jobs needed it and skipped through a job `if:` when no path they test changed.

The engine audit (HISS-18, praetor `docs/guides/workflow-triggers.md`) reported 17 jobs that ran on a draft pull request. Its rule for a job a pull request starts:

- **The first step is the draft step** `Stop on a draft pull request`, which fails the job on a draft. The workflow restarts on `ready_for_review`, and the new run reports the same check on the same commit.
- **No `needs` on such a job.** A job that needs a draft-stopped job is skipped, and the forge reports that skip as success.
- **No job condition that a draft or a path decides.** A skipped job reports success, which a required check accepts.

The detector shape breaks the second and third rule by design. The engine also derives the required contexts of `.github/rulesets/main.json` from the workflows: a job that reports on every pull request is required by name, and a job with a condition is not (praetor `internal/forge/workflow_checks.go`, `requiredJob`).

## Decision

1. **Every job a pull request starts begins with the draft step**, carries no job condition and no `needs`, and its workflow lists `ready_for_review` among the `pull_request` types.
2. **A path-filtered job filters inside itself.** After the draft step and the checkout it runs `dorny/paths-filter` (pinned by commit) on `.github/path-filters.yml` with step id `filter`, then a notice step, and gates every later step on `github.event_name != 'pull_request' || steps.filter.outputs.<job id> == 'true'`. A step that already had a condition keeps it as the left conjunct. A push or a scheduled run reads no filter and runs every step.
3. **One filter file.** `.github/path-filters.yml` holds one filter per filtered job, named after the job id, built from anchored blocks. Every filter includes the filter file and the job's own workflow.
4. **The `changes` jobs are removed**, and with them the contexts `Detect Changed Paths` and `Detect Security Scan Paths`.
5. **`required-checks` accepts no skip.** `MAY_SKIP` and the second wait step are removed; one wait step allows `success` only.
6. **The rule set requires the jobs by name.** `.github/rulesets/main.json` lists the 19 contexts the engine derives from the workflows; the online audit compares the forge with it. No required context names a toolchain version: the Go job is `Go Build & Unit Tests`, so a toolchain bump from the update bot, which cannot change the live rule set, never renames a required check.
7. **Tests hold the shape.** `tests/test_required_aggregator.py` checks every pull request job for the draft step, no condition, no `needs` and the `ready_for_review` trigger, and refuses planted jobs. `tests/test_path_filters.py` checks every filtered job's steps and gates, the filter keys against the filtered jobs, and every pattern against a tracked file, and refuses planted jobs.

## Consequences

- **Positive**: no required check can pass by being skipped; the aggregator needs no list of names.
- **Positive**: the engine audit reports no HISS-18 finding, and a draft pull request shows every gate red with the draft notice instead of running the work.
- **Negative**: a filtered job with nothing to check still starts a runner for the checkout and the filter, where the detector used to start one runner per workflow. The cost per pull request is recorded in the pull request that introduced this decision.
- **Negative**: renaming a job changes a required context; the rename and `.github/rulesets/main.json` change in the same pull request, and the engine audit fails until they agree.
- **Neutral**: the `semgrep` and `trivy` filters keep the path list of the old detector, which omits `cmd/**` and `pkg/**`; widening it is a separate change.

## References

- [ADR-0022](0022-fail-closed-provisioners-and-declared-main-protection.md): the declared rule set; its list of required contexts is replaced by point 6.
- [ADR-0026](0026-required-checks-accept-only-detector-decided-skips.md): the superseded skip list.
- `tests/test_required_aggregator.py`, `tests/test_path_filters.py`: the shape checks and the planted jobs.
