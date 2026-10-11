# 22. Fail-Closed Provisioners and a Declared Rule Set for `main`

Date: 2026-10-11

## Status

Accepted

## Context

ADR-0019 adopted Praetor governance. The repository was then left on the engine build of the migration while the engine moved on. Re-adopting it on engine commit `bd40beae2969` (verified again with `14ceb92341ad`) measured three gaps between what the repository declares and what it does:

- **Provisioners hid failures.** The audit reported 104 HISS findings in 27 provisioners and scripts. 81 commands ended in `|| true`, most of them with `2>/dev/null` in front, so a package that the archive does not publish, a unit that does not exist or a download that failed left a build green and an image without the component its flavor names. 15 downloads carried no time limit. Two of the hidden failures were real: `hyperv-daemons` is not in the Ubuntu 26.04 index, and `spice-vdagent` ships no system unit that `systemctl enable` can act on.
- **`main` was protected by one check.** The forge carried classic branch protection with the single required check `required-checks`; signed commits were not enforced. `.github/rulesets/main.json` declared more than the forge enforced, and nothing compared the two.
- **The release workflow declares more than it does.** `.standards.yaml` declares SLSA Build Level 3, cosign enforcement and an SBOM; `release-matrix.yml` publishes images without a signature, an SBOM or provenance.

The engine runs the whole audit on every commit, so the re-adoption and the fixes land together.

## Decision

1. **A provisioner step that fails ends the build.** No command discards its exit status. Where the absence of something is a legitimate state, the script tests for it and says what it found: a unit is disabled only if `systemctl cat` knows it, an optional package is installed only if `apt-cache show` finds it, and the other branch prints one line to standard error. A kernel module that cannot load in the build environment is reported and stays listed in `modules-load.d`. Every download carries `--max-time`.
2. **`main` and `lts-*` are protected by the declared rule set.** `praetor-main-protection` requires signed commits, linear history, a pull request, resolved review threads and nine status checks under the strict up-to-date policy: `Detect Changed Paths`, `Secret & Privacy Leak Scan`, `CodeQL (go)`, `CodeQL (python)`, `Validate PR Milestone & Metadata`, `Documentation Governance`, `required-checks`, `Detect Security Scan Paths` and `Gitleaks History Scan`. Repository administrators may bypass it in a pull request only. The online audit compares the forge with this file and fails on a difference.
3. **A required check is a name some run reports.** Before the rule set is applied, each required name is compared byte for byte with the check runs the forge holds. A job that calls a reusable workflow is reported under a two-part name and can never satisfy a rule that names the calling job alone (cordanaLLM/praetor#1212); none of the nine is such a job.
4. **Public repository metadata does not change with governance.** `.standards.yaml` declares the description, homepage and topics exactly as the forge carries them, so applying the declaration writes the rule set and the labels and nothing else. Public metadata changes with the first release under the new names.
5. **A gap that cannot be closed now is a dated exception, not a lowered rule.** The supply-chain gap is declared as one HISS-11 exception for `.github/workflows/release-matrix.yml` with a reason and the expiry 2027-01-09. The audit prints it on every run and fails once it expires. The baseline is not re-recorded and the engine is not pinned back.
6. **Documentation is gated.** `make verify-all` (through `make docs-lint` and `make docs-figures`) and the `Documentation Governance` check verify the public Markdown and the figures.

## Consequences

- **Positive**: an image that builds contains what its flavor names; a missing package or unit is a red build with the name in the log.
- **Positive**: the protection of `main` is a reviewed file, and drift between the file and the forge fails the audit.
- **Negative**: a build that used to finish with a component missing now stops. A flavor whose upstream package is not published for the base release stays red until `versions.json` names a version that exists.
- **Negative**: between applying the rule set and landing this change, no other pull request can merge, because `Documentation Governance` is reported only by commits that carry `praetor-docs.yml`. Open pull requests are rebased after the landing.
- **Negative**: every commit that reaches `main` must be signed. Pull requests merge through the forge's squash merge, which signs the resulting commit with the forge's key (the head of `main` before this change, `987b95a`, is such a commit).
- **Neutral**: the release workflow still publishes unsigned images; the exception makes that visible and gives it a date.
