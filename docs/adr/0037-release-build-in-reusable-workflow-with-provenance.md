# 37. Release Build in Reusable Workflow with SLSA v1 Build Level 3 Provenance

Date: 2026-10-19

## Status

Accepted. Closes the HISS-11 exception declared in `.standards.yaml` for `.github/workflows/release-matrix.yml`.

## Context

`.standards.yaml` declares SLSA Build Level 3 under `supply_chain.slsa_level: 3`. The build and signing jobs lived in the trigger workflow `.github/workflows/release-matrix.yml`, which signed `SHA256SUMS` with cosign but published no build provenance, so the measured level was 0. This gap was tracked as a dated category A exception under rule HISS-11 in `.standards.yaml`.

GitHub artifact attestations provide SLSA v1 Build Level 3 provenance only when the build runs inside a reusable workflow called by the trigger workflow, per GitHub's documentation "Using artifact attestations and reusable workflows to achieve SLSA v1 Build Level 3".

## Decision

1. **Build and sign move to a reusable workflow.** A new reusable workflow, `.github/workflows/release-build.yml` (`on: workflow_call`), encapsulates `build-matrix` and `sign` jobs. The caller workflow `.github/workflows/release-matrix.yml` retains only triggers, input choices, and concurrency controls, delegating execution to `release-build.yml` via a single `release` job.
2. **Attest build provenance.** In the `build-matrix` job, after `make build` and compression and before uploading release assets, `actions/attest@v4` generates cryptographically signed in-toto SLSA provenance over that flavor's checksum file `checksums-${FLAVOR}.sha256`.
3. **Verify before release.** The `build-matrix` job verifies the attestation bundle with `gh attestation verify` against the flavor's CycloneDX SBOM before uploading release assets.
4. **Publish attestation bundle.** The attestation bundle is uploaded as a permanent release asset `provenance-<flavor>.sigstore.json` alongside the flavor's image and metadata assets.
5. **Update signing identities.** Cosign verification binds to the reusable workflow identity `https://github.com/${GITHUB_REPOSITORY}/.github/workflows/release-build.yml@${GITHUB_REF}`, matching the certificate emitted by GitHub's OIDC issuer.
6. **HISS-11 exception removal.** The HISS-11 exception entry for `release-matrix.yml` in `.standards.yaml` is deleted.

## Consequences

- **Positive**: Every release asset carries signed SLSA v1 build provenance from the layout GitHub documents for Build Level 3, verifiable with `gh attestation verify` against GitHub's attestation store or the release asset `provenance-<flavor>.sigstore.json`. The first published release is the first run of the new path; until then the wiring is covered by `tests/test_release_provenance.py` only.
- **Positive**: The HISS-11 supply-chain exception in `.standards.yaml` is resolved and removed.
- **Negative (breaking for verifiers)**: The Cosign OIDC certificate identity changes from `.github/workflows/release-matrix.yml@refs/tags/<tag>` to `.github/workflows/release-build.yml@refs/tags/<tag>`. Downstream verifiers must update their `--certificate-identity` flags.
- **Neutral**: Check run names for image builds and release signing change to `release / Build Image (<flavor>)` and `release / Sign the Release Checksums`. The `KEEP_CHECKS` filter in `required-aggregator.yml` is updated to exclude both forms.

## References

- GitHub documentation: "Using artifact attestations and reusable workflows to achieve SLSA v1 Build Level 3".
- SLSA Specification: Source Levels for Security Artifacts, Version 1.0 (Build Level 3).
- [ADR-0022](0022-fail-closed-provisioners-and-declared-main-protection.md): Fail-Closed Provisioners and Declared Main Protection (HISS-11 exception entry).
- [ADR-0035](0035-required-checks-wait-only-for-gate-workflows.md): Required Checks Wait Only for Gate Workflows.
