# 33. Aegis OS Image Build and Release Workflow

Date: 2026-10-17

## Status

Accepted. Implements issue #46 unit 2, fulfilling the executor contract anticipated in [ADR-0020](0020-aegis-product-input-contract-acceptance.md) and [ADR-0024](0024-product-result-emitter-and-signature-reference-form.md).

## Context

Aegis milestone M11 requires an automated executor in `cordanaLLM/imago` that accepts the product-input manifest `aegis.p01.product-input.v1`, builds the unified operating system image using mkosi, boots the built image once under KVM acceleration to collect boot evidence, signs the artifacts keylessly via Cosign, and publishes an immutable GitHub pre-release carrying `imago.p01.product-result.v1`.

Several architectural and environmental constraints govern this execution:

1. **Host Virtualisation vs Emulation**: GitHub-hosted runners (`ubuntu-26.04`) provide hardware-assisted virtualisation when `/dev/kvm` is made accessible. Because the Aegis OS boot contract requires testing under production hypervisor conditions, software emulation (TCG) is unacceptable. Execution must fail closed if `/dev/kvm` is missing or not readable/writable.
2. **Commit Lineage vs Definitions**: `aegis/build/product-input.json` in Aegis-OS specifies `revision: "61f2fe16bab7889e007b2fd1474b025023906e91"`. Commit `61f2fe1` is the reviewed-definitions baseline; at that commit, `build/mkosi.conf` did not yet exist in the repository tree. The build executor checks out the target `aegis-revision` tree (where `mkosi.conf` exists) and must formally prove that `request.revision` is an ancestor of `aegis-revision`.
3. **Firmware and Console Redirection**: Aegis produces Unified Kernel Images (UKIs) without hardcoded serial console arguments (`console=ttyS0`). The boot validator must inject console redirection without mutating the signed image or guest filesystems.
4. **Artifact Contract & Integrity**: Forge releases impose a hard limit of 2 GiB per asset. Every release artifact must be accounted for in a single signed `SHA256SUMS` file before publishing. Releases must be strictly immutable pre-releases to prevent clobbering or unintended deployment.

## Decision

1. **Workflow Trigger & Runner Environment**: The executor is defined in `.github/workflows/aegis-build.yml` and triggers exclusively on `workflow_dispatch`. Its first step refuses any ref other than `refs/heads/main`, so a pre-release is only ever built from reviewed workflow code, and `gh release create --target "${GITHUB_SHA}"` points the new tag at that commit. It runs on GitHub-hosted `ubuntu-26.04` (accepted by `actionlint`). Top-level permissions are strictly empty (`permissions: {}`); the build job receives exactly `contents: write` (to publish pre-releases and upload assets) and `id-token: write` (for OIDC keyless Sigstore Cosign signing).
2. **Input Validation and Lineage Verification**: The dispatch inputs are `aegis-revision` (40 lowercase hexadecimal characters) and `request-sha256` (64 lowercase hexadecimal characters). Inputs are passed to steps via environment variables, never expanded directly inside `run:` blocks. A dedicated verification tool (`tools/aegis/check_request.py`) performs preflight checks:
   - Validates the hex syntax of both inputs;
   - Verifies the SHA-256 of `aegis/build/product-input.json` against `request-sha256`;
   - Validates the manifest syntax and schema via `imago aegis validate`;
   - Confirms that `request.revision` (`61f2fe1...`) is a git ancestor of `aegis-revision` using `git -C aegis merge-base --is-ancestor`.
3. **KVM Fail-Closed Enforcement**: mkosi is provisioned via the upstream GitHub Action `systemd/mkosi` pinned to v27.1 (`ecf7f5702bb2052b7a69cab3fe7d37bc3b9ad77b`). Inspection of `action.yaml` at that commit confirms that it configures udev rules (`/etc/udev/rules.d/99-kvm4all.rules`) granting mode `0666` access to `/dev/kvm`, `/dev/vhost-vsock`, and `/dev/vhost-net`, triggers kernel module loading (`modprobe kvm`), and enables unprivileged user namespaces via sysctl. The action installs `pacman-package-manager` and `makepkg` only when the runner's apt sources carry them and skips them silently otherwise; the workflow therefore checks that `mkosi` and `pacman` are on `PATH` and fails if either is missing. There is no fallback installation of mkosi from another source. A subsequent workflow step verifies read and write access to `/dev/kvm` and exits immediately with code 1 upon any failure. No TCG emulation fallback is permitted.
4. **mkosi Build Parameters & Artifact Contracts**: mkosi is executed with `mkosi -C aegis/build --tools-tree=yes --tools-tree-distribution=arch --output-directory <dir> build`. The first dispatch (run 39067484406) failed with `Could not find 'systemd-repart' which is required to build disk images`: Ubuntu 26.04 ships `systemd-repart` and `systemd-ukify` as separate universe packages the runner image does not carry, and the Aegis partition set also needs `mkfs.erofs`, `mkfs.btrfs`, vfat tools and dm-verity support. mkosi(1) at v27.1 (sections `ToolsTree=` and TOOLS TREES) recommends a default tools tree; its Arch package list (`mkosi/resources/mkosi-tools/mkosi.conf.d/arch.conf`) carries `systemd`, `systemd-ukify`, `erofs-utils`, `btrfs-progs`, `dosfstools` and `mtools`, and `ToolsTreeSnapshot=` defaults to the image snapshot when the tools tree distribution matches the image, so the build tools are pinned to `Snapshot=2026/09/13` with the image. No host package is installed for the build. Reading `mkosi documentation` usage for version 27.1 confirms that `-C` designates the root configuration search directory, while `-O, --output-directory` directs output artifacts without modifying the source tree. Based on `mkosi.conf` (`Format=disk`, `ImageId=aegis-os`, `SplitArtifacts=uki,kernel,initrd,roothash`), the build must produce five exact artifacts:
   - `aegis-os.raw`: raw GPT disk image;
   - `aegis-os.efi`: Unified Kernel Image (UKI);
   - `aegis-os.vmlinuz`: extracted kernel binary;
   - `aegis-os.initrd`: extracted initramfs;
   - `aegis-os.roothash`: dm-verity root hash.
   The step verifies that all five artifacts exist and that no single artifact exceeds the 2 GiB forge limit.
5. **Single-Boot Verification and SMBIOS Type 11 Console**: `tools/aegis/boot_once.py` performs an isolated boot test:
   - Executes QEMU (`q35`, `accel=kvm`, `cpu=host`, `m=2048`, `smp=2`);
   - Configures non-Secure-Boot OVMF code (`/usr/share/OVMF/OVMF_CODE_4M.fd`) and copies the OVMF NVRAM vars template to a throwaway file;
   - Initialises an isolated software TPM 2.0 daemon via `swtpm socket` communicating over a UNIX domain socket with `tpm-tis`;
   - Creates a temporary `qcow2` overlay backed by `aegis-os.raw`, ensuring the underlying raw image is never modified;
   - Redirects guest serial to `serial.log`;
   - Injects the kernel command line argument `console=ttyS0` via SMBIOS Type 11 string:
     `-smbios type=11,value=io.systemd.stub.kernel-cmdline-extra=console=ttyS0`.
     As documented in `systemd-stub(7)` (section "SMBIOS Type 11 strings", string added in systemd 254; read from the systemd 262 man page), `systemd-stub` reads `io.systemd.stub.kernel-cmdline-extra` unless it detects a confidential computing environment, measures the value into PCR12, and adds it to the kernel command line. Secure Boot state does not gate this string; the hosted runner is not a confidential guest;
   - Polls for the systemd target success marker (matching `Reached target multi-user.target`, `Reached target Multi-User System`, or `Startup finished in`) within a hard 600-second deadline;
   - Ensures all spawned process groups (QEMU, swtpm) are cleanly terminated on every exit path;
   - Generates `boot-evidence.json` matching schema `imago.aegis.boot-evidence.v1`.
6. **Keyless Signing & Evidence Packaging**:
   - `SHA256SUMS` is computed over all released assets: `aegis-os.raw`, `aegis-os.efi`, `aegis-os.vmlinuz`, `aegis-os.initrd`, `aegis-os.roothash`, `boot-evidence.json`, and `serial.log`.
   - Sigstore Cosign (`sigstore/cosign-installer` pinned to `d7d6bc7722e3daa8354c50bcb52f4837da5e9b6a # v3.8.1`) signs `SHA256SUMS` keylessly to produce `SHA256SUMS.bundle`.
   - The signature is verified locally using `cosign verify-blob` against `--certificate-identity "https://github.com/${GITHUB_WORKFLOW_REF}"` and `--certificate-oidc-issuer https://token.actions.githubusercontent.com`.
7. **Product-Result Emission & Reference Forms**: `imago aegis result emit` produces `result.json` (`imago.p01.product-result.v1`):
   - `signature-ref`: `https://github.com/<repo>/releases/download/aegis-<cid>/SHA256SUMS.bundle` (meets ADR-0024 allow-list syntax);
   - `boot-evidence-ref`: `https://github.com/<repo>/releases/download/aegis-<cid>/boot-evidence.json`. This form satisfies `validateReference` (non-empty, $\le 512$ bytes, no control characters or backslashes) and passes `Result.Validate`.
8. **Pre-Release Publication**: The pre-release is published using `gh release create aegis-<cid> --prerelease --latest=false`:
   - Enforces that the tag starts with `aegis-`;
   - Queries `gh release view` and `git ls-remote` to refuse execution if the tag already exists;
   - Never uses `--clobber` and never sets latest;
   - Uploads only signed artifacts and evidence: the five mkosi outputs, `boot-evidence.json`, `serial.log`, `SHA256SUMS`, `SHA256SUMS.bundle`, and `result.json`.

### Facts measured on the first dispatch

The following are unmeasured when this record is accepted and are recorded on issue #46 after the first dispatch: whether the hosted runner exposes `/dev/kvm`, whether `swtpm` starts under the runner's AppArmor state, whether the Arch Linux keyring is usable by `pacman` on Ubuntu, the exact file names mkosi writes for the split artifacts, disk headroom, artifact sizes against the 2 GiB limit, and wall time. First dispatch, run 39067484406 on `ubuntu-26.04` image 20261012.163.1: `/dev/kvm` read-write passed, the request check passed, `mkosi 27.1` and `pacman` were on `PATH`, `pacman` installed the Arch keyring and the default initrd built (61.1 MB zstd cpio); the disk build then failed on the missing host `systemd-repart`, fixed by the tools tree above. A measured failure of KVM, swtpm or disk is the trigger for the self-hosted VM runner fallback the operator approved; any other failure is fixed in this workflow.

## Consequences

- **Positive**: Imago provides a fully automated, verifiable, and fail-closed build and release pipeline for Aegis OS.
- **Positive**: Git lineage validation cleanly bridges the reviewed baseline commit (`61f2fe1`) with the runnable tree at `aegis-revision`.
- **Positive**: SMBIOS Type 11 injection provides serial visibility during boot testing without modifying UKI binaries or root partition contents.
- **Positive**: All published artifacts are cryptographically bound to the GitHub Actions workflow identity through keyless Cosign signatures.
- **Neutral**: The pre-release tag `aegis-<correlation-id>` is immutable. Re-running a failed or aborted correlation ID requires generating a new correlation ID in Aegis.

## References

- Issue #46: Aegis product-input execution, signing, and product-result emission.
- [ADR-0020](0020-aegis-product-input-contract-acceptance.md): Aegis product-input contract acceptance.
- [ADR-0024](0024-product-result-emitter-and-signature-reference-form.md): Product-result emitter and signature reference form.
- [ADR-0032](0032-local-packer-executor.md): Local Packer executor.
- Upstream `systemd/mkosi` Action: commit `ecf7f5702bb2052b7a69cab3fe7d37bc3b9ad77b` (v27.1).
- Systemd documentation: `systemd-stub(7)` and `smbios-type-11(7)`.
- Tools: `tools/aegis/check_request.py`, `tools/aegis/boot_once.py`.
- Workflow: `.github/workflows/aegis-build.yml`.
