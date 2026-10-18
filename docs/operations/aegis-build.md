# Aegis OS Image Build and Release Operations

This guide covers operational dispatch, execution monitoring, verification, and artifact consumption for the Aegis OS image build pipeline defined in `.github/workflows/aegis-build.yml` ([ADR-0033](../adr/0033-aegis-build-workflow.md)).

---

## 1. Overview

The `aegis-build` workflow provides an automated, fail-closed executor for `cordanaLLM/Aegis-OS` images:

1. **Preflight Lineage Verification**: Verifies the input request hash and proves that `request.revision` (`61f2fe1...`, the reviewed-definitions baseline) is an ancestor of the target `aegis-revision`.
2. **KVM Virtualisation Check**: Asserts read/write availability on `/dev/kvm` after mkosi environment configuration; fails closed without TCG fallback.
3. **Hermetic Image Build**: Invokes mkosi v27.1 on `aegis/build` to construct disk images, unified kernel images (UKIs), extracted kernels, initramfs, and dm-verity root hashes.
4. **Single-Boot Hardware-Assisted Verification**: Executes QEMU (`q35`, `accel=kvm`) with non-Secure-Boot OVMF, a software TPM 2.0 socket daemon (`swtpm`), and SMBIOS Type 11 kernel argument injection (`io.systemd.stub.kernel-cmdline-extra=console=ttyS0`) to capture console evidence without image mutation.
5. **Keyless Attestation**: Signs `SHA256SUMS` using Sigstore Cosign via GitHub Actions OIDC identity tokens.
6. **Contract Emission & Publishing**: Emits `imago.p01.product-result.v1` referencing the Cosign bundle and boot evidence, and publishes an immutable GitHub pre-release tagged `aegis-<correlation-id>`.

---

## 2. Dispatching the Workflow

The workflow triggers exclusively via `workflow_dispatch`.

### Prerequisites

- GitHub CLI (`gh`) authenticated with repository access.
- Target Aegis git commit revision (40 lowercase hexadecimal characters).
- Expected SHA-256 hash of `aegis/build/product-input.json` at that revision (64 lowercase hexadecimal characters).

### Command

Derive both inputs from the Aegis commit to build, then dispatch from `main` (any other ref is refused):

```bash
rev=$(gh api repos/cordanaLLM/Aegis-OS/commits/main --jq .sha)
req=$(gh api "repos/cordanaLLM/Aegis-OS/contents/build/product-input.json?ref=${rev}" \
  -H "Accept: application/vnd.github.raw" | sha256sum | cut -d' ' -f1)
gh workflow run aegis-build.yml --repo cordanaLLM/imago --ref main \
  -f aegis-revision="${rev}" -f request-sha256="${req}"
```

### Monitoring Progress

Monitor the dispatched run using `gh run watch`:

```bash
gh run list --workflow=aegis-build.yml --limit 1
gh run watch
```

---

## 3. Preflight Checks & Refusal Invariants

The preflight tool (`tools/aegis/check_request.py`) enforces four mandatory checks before any build steps commence:

| Check | Tool / Mechanism | Refusal Condition |
| :--- | :--- | :--- |
| **Hex Syntax** | Regex validator | `aegis-revision` is not 40 lowercase hex digits; `request-sha256` is not 64 lowercase hex digits. |
| **Integrity** | Streaming SHA-256 | `aegis/build/product-input.json` does not match `request-sha256`. |
| **Manifest Contract** | `imago aegis validate` | Schema violations, out-of-bound retry policies, or unknown fields in `product-input.json`. |
| **Lineage Proof** | `git merge-base --is-ancestor` | The reviewed `request.revision` is not an ancestor of `aegis-revision`. |

---

## 4. Released Artifacts & Naming

Every release publishes to tag `aegis-<correlation-id>` with `--prerelease --latest=false`. Releases never clobber existing tags.

The pre-release contains:

- `aegis-os.raw`: Bootable raw GPT disk image.
- `aegis-os.efi`: Unified Kernel Image (UKI).
- `aegis-os.vmlinuz`: Kernel binary extracted from the UKI.
- `aegis-os.initrd`: Initramfs extracted from the UKI.
- `aegis-os.roothash`: dm-verity root hash.
- `boot-evidence.json`: Boot verification metadata conforming to `imago.aegis.boot-evidence.v1`.
- `serial.log`: Complete guest serial console output captured during single-boot testing.
- `SHA256SUMS`: Checksums covering all seven assets listed above.
- `SHA256SUMS.bundle`: Sigstore Cosign keyless signature bundle covering `SHA256SUMS`.
- `result.json`: Imago product-result payload conforming to `imago.p01.product-result.v1`.

A failed run publishes nothing. Its step `Keep the Boot Evidence of a Failed Run` keeps `serial.log`, `boot-failure.json` and, if present, `boot-evidence.json` as the run artifact `aegis-boot-failure-<run attempt>` for three days. `boot-failure.json` follows `imago.aegis.boot-failure.v1`: correlation id, the reason `boot_once.py` stopped, the deadline, the serial log digest (null when QEMU wrote no log) and the runner image. Read it with `gh run download <run id> --repo cordanaLLM/imago --name aegis-boot-failure-1`.

---

## 5. Downstream Verification (Aegis M11)

Consumers verify the release using the pinned Cosign toolchain and Imago CLI:

```bash
# 1. Download release metadata
TAG="aegis-aegis-m18-product-input-0001"
gh release download "${TAG}" --repo cordanaLLM/imago \
  --pattern "SHA256SUMS*" --pattern "result.json" --pattern "boot-evidence.json"

# 2. Verify keyless cosign signature
cosign verify-blob --bundle SHA256SUMS.bundle \
  --certificate-identity 'https://github.com/cordanaLLM/imago/.github/workflows/aegis-build.yml@refs/heads/main' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  SHA256SUMS

# 3. Validate product-result schema
imago aegis result validate result.json --json

# 4. Verify image digest matches SHA256SUMS
IMAGE_DIGEST=$(jq -r '."image-digest"' result.json | sed 's/^sha256://')
grep -F "${IMAGE_DIGEST}" SHA256SUMS
```
