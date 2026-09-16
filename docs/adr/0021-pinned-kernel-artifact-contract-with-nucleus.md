# 21. Pinned Kernel Artifact Contract with cordanaLLM/nucleus

Date: 2026-09-15

## Status

Accepted

## Context

`cordanaLLM/nucleus` is the kernel forge that produces the kernel artifacts this image forge consumes (planning step `step-nucleus-contract`, requirement `req-nucleus-contract`). Until this decision the two repositories were coupled by loose `repository_dispatch` payloads:

- `sync-kernel-manifest.yml` wrote `kernel.streams.<stream>.version` into `versions.json` straight from the `kernel_release_published` payload, fell back to a default stream and version when the payload was incomplete, verified nothing, and `versions.schema.json` had no `kernel` property, so the write was outside the Single Source of Truth contract (ADR-0001).
- `dispatch-kernel-requirements.yml` sent nucleus a fixed triple (`drivers`, `runtimes`, `kubernetes.version`) that nucleus does not read; its `verify-requirements.yml` checks a hard-coded symbol list.

Two upstream facts fix the shape of the replacement. `nucleus` publishes GitHub Releases with `*.deb`, a UKI `.efi`, CycloneDX and SPDX SBOMs, `SHA256SUMS`, and a keyless cosign bundle `SHA256SUMS.bundle` (`cosign sign-blob --bundle`), signed by its `publish-release.yml` workflow identity. `cordanaLLM/Aegis-OS` defines the kernel requirement payload `aegis.p01-nucleus.kernel-requirement.v1` (`build/kernel-requirement.json` at `5148ab27bb4c9d32759e8739b97c05d9b423b912`): a correlation id, architectures, an ABI floor, and a feature list where each `CONFIG_*` symbol carries a required state, a probe method, and the requirement it serves. No nucleus release exists yet, so no real digest can be pinned today.

The planning acceptance criteria are explicit: a pinned artifact with a valid digest is consumed; a tampered artifact digest is rejected; an empty kernel requirement list is rejected explicitly.

## Decision

1. **Artifact contract owned by the consumer.** `pkg/kernel` defines `imago.nucleus.kernel-artifact.v1`: `provider`, `stream`, `version`, `kernel.release`, `kernel.config_digest` (`sha256:` over the shipped `kernel-<stream>.config`), 1..64 `artifacts` with safe basenames, 64-hex `sha256`, and bounded `size`, `checksums` (`SHA256SUMS` and its digest), and `provenance` (`repository`, `tag`, 40-hex `revision`, `bundle`, `signer_identity` under `https://github.com/<provider>/`). Decoding is strict: unknown fields, trailing data, and documents above 1 MiB are rejected; every error is correlated by `<stream>@<version>` and field. `nucleus` generates `kernel-<stream>.manifest.json` in this shape in `publish-release.yml`, uploads it with the other assets, and extends its dispatch payload to `{"stream", "version", "tag"}`.
2. **Division of verification.** `cosign verify-blob` in `sync-kernel-manifest.yml` is the only signature check: it verifies `SHA256SUMS.bundle` against the certificate identity prefix derived from `kernel.provider` in `versions.json` and the GitHub Actions OIDC issuer. The Go verifier (`kernel.Verify`, exposed as `imago kernel artifact verify`) checks what cosign does not: the `SHA256SUMS` digest, that every listed artifact appears in `SHA256SUMS` with the same digest, is a regular file of the declared size, and hashes to the declared SHA-256 under a 512 MiB bounded read; that the bundle file and signer fields are present; and that the manifest matches the payload (`--expect-stream`, `--expect-version`, `--expect-tag`) and the provider and contract pinned in `versions.json`. Failures are typed sentinels (`ErrDigestMismatch`, `ErrSizeMismatch`, `ErrMissingArtifact`, `ErrChecksumEntry`, `ErrMissingBundle`); an unlisted extra file is reported, not rejected. Cosign verification is not reimplemented in Go.
3. **Pin before consumption.** `versions.json` gains a typed `kernel` section (`provider`, `contract`, `dispatch_event`, `streams`), validated by `pkg/manifest` and `versions.schema.json`; each stream pins `version`, `artifact_digest` (the `sha256:` digest of `SHA256SUMS`), and `provenance.tag/revision/bundle`. The workflow writes a stream only after steps 1 and 2 pass, validates the schema, and proposes a pull request that adds only `versions.json`. A payload without `stream`, `version`, and `tag` is refused; the default-version fallback is deleted. `streams` is committed empty because no release exists to pin.
4. **Aegis-shaped requirement.** `imago` keeps its own requirement in `kernel/requirement.json` in the Aegis shape (correlation id `imago-kernel-requirement-0001`, `required-by` ids naming flavor tiers) and vendors the Aegis fixtures under `pkg/kernel/testdata/`. The decoder enforces the exact schema id, a 1..128-character correlation id, 1..8 unique architectures, a dotted numeric `abi.minimum-release`, 1..512 features with unique `CONFIG_[A-Z0-9_]+` symbols, `state` in `built-in`/`module`, a probe from the package-level allow-list (`kernel-config`, `lsm-list`, `btf-vmlinux`, `powercap`, `iommu-groups`; extension is a one-line change), and a bounded `required-by`. An empty feature list is rejected with `ErrEmptyRequirement`. `dispatch-kernel-requirements.yml` validates the file and dispatches its path, `sha256`, and commit rather than the file's content or a fixed symbol list.

## Consequences

- **Positive**: a kernel artifact reaches an image build only through a stream pinned in `versions.json` after signature, checksum, digest, size, and provenance verification; the bounds (1 MiB documents, 64 artifacts, 512 MiB per artifact, 1024 checksum lines, 4096 directory entries) keep the verifier within HISS-02/03.
- **Positive**: the requirement imago sends upstream is the same document shape Aegis-OS sends, so nucleus needs one consumer for both, and the probe vocabulary is shared.
- **Negative**: the dispatch payload shape is a breaking change; a nucleus release published without `kernel-<stream>.manifest.json` or without `tag` in its payload is refused by `sync-kernel-manifest.yml` until the nucleus-side change is merged.
- **Negative**: `kernel.streams` stays empty until the first nucleus release passes verification; consumers of `versions.json` cannot assume a pinned kernel exists.
- **Neutral**: nucleus's `verify-requirements.yml` still evaluates its fixed symbol list; consuming the Aegis payload shape on the nucleus side is tracked there and does not weaken the downstream verification decided here.
