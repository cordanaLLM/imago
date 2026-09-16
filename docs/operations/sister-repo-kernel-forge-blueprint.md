# Autonomous Agent Onboarding Blueprint: `nucleus`

> **Turnkey Agent Operating Directive & Repository Scaffolding Manual**
>
> This document serves as the authoritative, self-contained onboarding specification for an autonomous engineering agent (`agy`, Claude Code, Cursor) tasked with bootstrapping and operating the sister repository **`nucleus`** from scratch.
>
> **Privacy Invariant**: This specification strictly adheres to the Zero-Leak Invariant (Hard Rules 6 & 10). Zero developer workstation paths (`/home/...`) and zero private RFC 1918 IPs exist within this document. All paths use `/opt/lusoris/...` or standard documentation placeholders (`192.0.2.x`, `kernel.example.com`, `https://github.com/cordanaLLM/nucleus`).

---

## 1. Mission, Authority & Architectural Contract

`nucleus` is the dedicated compilation and packaging factory for custom-patched, high-performance Linux kernels consumed by `imago` and the wider Lusoris ecosystem.

### Core Objectives
1. **Decouple Compilation Compute**: Isolate heavy, multi-hour kernel compilation (Clang/LLVM 20, GCC 15, patch queues, kselftests) from cloud OS image generation.
2. **Multi-Architecture Support**: Produce reproducible kernel packages across **`x86_64` (AMD64)**, **`arm64` (aarch64)**, and **`riscv64`** (roadmap).
3. **Multi-Stream Kernel Matrix**: Build and maintain 4 live-verified kernel streams aligned with `kernel.org`:
   - **`lts`**: Linux 6.18 LTS / 6.12 LTS (Enterprise Kubernetes, OpenZFS 2.3+ storage, databases).
   - **`mainstream`**: Linux 7.2.x (Intel Xe2 Battlemage, AMD ROCm 10, NVIDIA 565/610, container hosts).
   - **`bleeding`**: Linux 7.3-rc2 / mainline (NVIDIA 615 Blackwell RTX 5090 / B200, CXL 3.0, `sched-ext`).
   - **`realtime`**: Linux 7.2-rt / 6.18-rt (`PREEMPT_RT` / BORE scheduler, 1000Hz timer, WireGuard).
4. **Packaging & Delivery**: Output standard Debian `.deb` packages, debug symbols, and signed Unified Kernel Image (UKI) `.efi` binaries to an APT repository (`apt.example.com/kernels`) and an OCI registry (`ghcr.io/lusoris/kernels`).

---

## 2. Repository Scaffolding & Directory Layout

An autonomous agent initializing `nucleus` must scaffold the following directory structure:

```text
nucleus/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                          # Linting, kconfig validation, commit hygiene
│   │   ├── build-matrix.yml                # Containerized cross-compilation matrix
│   │   ├── publish-release.yml             # APT repository & OCI UKI image publication
│   │   └── verify-requirements.yml         # Inbound requirement listener from cloud-images
│   ├── CODEOWNERS
│   └── dependabot.yml / renovate.json
├── configs/
│   ├── base/                               # Common hardening and CIS baseline fragments
│   │   ├── common-hardening.config
│   │   └── security-lockdown.config
│   ├── streams/
│   │   ├── lts-x86_64.config
│   │   ├── lts-arm64.config
│   │   ├── mainstream-x86_64.config
│   │   ├── mainstream-arm64.config
│   │   ├── bleeding-x86_64.config
│   │   ├── bleeding-arm64.config
│   │   ├── realtime-x86_64.config
│   │   └── realtime-arm64.config
├── patches/
│   ├── sched-ext/                          # BPF extensible scheduler framework
│   ├── bore/                               # Burst-Oriented Response Enhancer patches
│   ├── openzfs/                            # OpenZFS 2.3+ compatibility patches
│   ├── bbrv3/                              # BBRv3 congestion control backports
│   ├── nvidia/                             # NVIDIA Open Kernel Module Day-0 fixes
│   └── intel-xe2/                          # Intel Battlemage DRM/KMS backports
├── scripts/
│   ├── build-kernel.sh                     # Hermetic containerized build driver (<= 60 lines)
│   ├── merge-config.sh                     # Declarative kconfig merge wrapper
│   ├── package-deb.sh                      # make deb-pkg automation
│   ├── package-uki.sh                      # systemd-ukify EFI binary synthesis
│   └── verify-reproducibility.sh           # Diffoscope reproducible build verifier
├── tests/
│   ├── test_kconfig_lint.py                # Asserts mandatory CONFIG_ options enabled
│   ├── test_qemu_boot.py                   # Headless QEMU microVM sub-second cold boot test
│   └── test_security_privacy.py            # Zero-leak RFC 1918 & workstation path checks
├── AGENTS.md                               # Agent governance, rules, and authority
├── CHANGELOG.md                            # Keep a Changelog format
├── Makefile                                # Local entry points (build, test, lint)
├── versions.json                           # Single Source of Truth for kernel streams
└── versions.schema.json                    # Semantic JSON Schema
```

---

## 3. Hermetic Build Recipes (NASA/JPL Power of 10)

All compilation and packaging scripts must enforce `set -euo pipefail`, have functions $\le 60$ lines, and execute inside reproducible OCI builder containers.

### Example: `scripts/build-kernel.sh`
```bash
#!/usr/bin/env bash
# Copyright 2026 Lusoris
# scripts/build-kernel.sh — Hermetic Linux kernel compilation driver
set -euo pipefail

prepare_build_env() {
  local stream="${1}"
  local arch="${2}"
  echo "==> Preparing build tree for stream=${stream} arch=${arch}..."
  mkdir -p "/opt/lusoris/build/${stream}-${arch}"
  mkdir -p "/opt/lusoris/output/${stream}-${arch}"
}

merge_kernel_configs() {
  local stream="${1}"
  local arch="${2}"
  echo "==> Merging kernel configuration fragments..."
  KCONFIG_CONFIG="/opt/lusoris/build/${stream}-${arch}/.config" \
    /opt/lusoris/src/scripts/kconfig/merge_config.m \
    -m -O "/opt/lusoris/build/${stream}-${arch}" \
    "configs/base/common-hardening.config" \
    "configs/streams/${stream}-${arch}.config"
  make -C /opt/lusoris/src O="/opt/lusoris/build/${stream}-${arch}" olddefconfig
}

compile_and_package() {
  local stream="${1}"
  local arch="${2}"
  local jobs
  jobs="$(nproc)"
  echo "==> Compiling kernel using ${jobs} threads (LLVM=1)..."
  make -C /opt/lusoris/src \
    O="/opt/lusoris/build/${stream}-${arch}" \
    ARCH="${arch}" \
    LLVM=1 \
    -j"${jobs}" \
    bindeb-pkg \
    KDEB_PKGVERSION="$(date +%Y%m%d)-lusoris1"
  mv /opt/lusoris/build/*.deb "/opt/lusoris/output/${stream}-${arch}/"
}

main() {
  if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <stream> <arch>" >&2
    exit 1
  fi
  prepare_build_env "$1" "$2"
  merge_kernel_configs "$1" "$2"
  compile_and_package "$1" "$2"
  echo "==> Kernel build complete."
}

main "$@"
```

---

## 4. Cross-Repository Synchronization: Pinned Kernel Artifact Contract

`nucleus` and `imago` exchange two typed documents (ADR-0021). A `repository_dispatch` payload only names a release or a requirement revision; nothing enters an image build on the strength of the payload alone. `imago` verifies the release it was told about and pins the result in `versions.json`.

### 4.1 Downstream Release Pipeline (`nucleus` -> `imago`)

`publish-release.yml` in `nucleus` builds one stream, writes `SHA256SUMS` over every asset, signs it keylessly (`cosign sign-blob --bundle SHA256SUMS.bundle`), generates `kernel-<stream>.manifest.json`, uploads everything to the GitHub Release, and sends `repository_dispatch` type `kernel_release_published` with exactly:

```json
{"stream": "mainstream", "version": "7.2.4-lusoris1", "tag": "v7.2.4-lusoris1"}
```

Release assets: `*.deb`, `linux-<stream>-<version>-uki.efi`, `kernel-<stream>.config` (the merged kconfig the build used), `kernel-<stream>.cdx.json`, `kernel-<stream>.spdx.json`, `SHA256SUMS`, `SHA256SUMS.bundle`, and `kernel-<stream>.manifest.json`. The manifest is written after `SHA256SUMS` is signed and is deliberately not listed in it.

The manifest schema `imago.nucleus.kernel-artifact.v1` is owned by `imago` (`pkg/kernel`) and decoded strictly: unknown fields, trailing data, and documents above 1 MiB are rejected.

```json
{
  "schema": "imago.nucleus.kernel-artifact.v1",
  "provider": "cordanaLLM/nucleus",
  "stream": "mainstream",
  "version": "7.2.4-lusoris1",
  "kernel": {
    "release": "7.2.4-lusoris1",
    "config_digest": "sha256:<64 hex of kernel-mainstream.config>"
  },
  "artifacts": [
    {"name": "linux-image-7.2.4-lusoris1_x86_64.deb", "sha256": "<64 hex>", "size": 123456}
  ],
  "checksums": {"file": "SHA256SUMS", "sha256": "<64 hex>"},
  "provenance": {
    "repository": "cordanaLLM/nucleus",
    "tag": "v7.2.4-lusoris1",
    "revision": "<40 hex commit>",
    "bundle": "SHA256SUMS.bundle",
    "signer_identity": "https://github.com/cordanaLLM/nucleus/.github/workflows/publish-release.yml@refs/tags/v7.2.4-lusoris1"
  }
}
```

| Field | Bound |
| :--- | :--- |
| `provider`, `provenance.repository` | `owner/repository` slug; must equal `kernel.provider` in `versions.json` and each other |
| `stream` | one of `bleeding`, `mainstream`, `lts`, `realtime` |
| `version`, `kernel.release` | `^[0-9][A-Za-z0-9._+-]{0,63}$` |
| `kernel.config_digest` | `sha256:` + 64 lowercase hex |
| `artifacts` | 1..64 entries; unique safe basenames (no `/`, no `..`); 64-hex `sha256`; `0 <= size <= 512 MiB`; `SHA256SUMS` and the bundle may not be listed |
| `checksums` | `file` is `SHA256SUMS`; `sha256` is 64 hex |
| `provenance.tag` | `^v[0-9][A-Za-z0-9._-]{0,62}$` |
| `provenance.revision` | 40 lowercase hex |
| `provenance.bundle` | `SHA256SUMS.bundle` |
| `provenance.signer_identity` | at most 512 characters, prefixed `https://github.com/<provider>/` |

`sync-kernel-manifest.yml` in `imago` refuses a payload without `stream`, `version`, and `tag` (there is no default version), downloads the release with `gh release download`, and verifies in this order:

1. **Cosign bundle**: `cosign verify-blob --bundle SHA256SUMS.bundle --certificate-identity-regexp '^https://github.com/cordanaLLM/nucleus/' --certificate-oidc-issuer https://token.actions.githubusercontent.com SHA256SUMS`. The identity prefix is derived from `kernel.provider` in `versions.json`. This is the only signature check in the pipeline.
2. **SHA256SUMS digest**: `imago kernel artifact verify` recomputes the digest of `SHA256SUMS` (bounded at 1 MiB, at most 1024 lines) and compares it with `checksums.sha256`.
3. **Per-artifact digests**: every listed artifact must appear in `SHA256SUMS` with the same digest, be a regular file, match its declared size, and hash to its declared SHA-256 (bounded read of 512 MiB per artifact). A missing file, a size mismatch, or a digest mismatch fails the run with a typed sentinel (`ErrMissingArtifact`, `ErrSizeMismatch`, `ErrDigestMismatch`); an unlisted extra file is reported but not fatal. The manifest must also match the payload (`--expect-stream`, `--expect-version`, `--expect-tag`) and the provider and contract pinned in `versions.json`, and `SHA256SUMS.bundle` must be present next to the artifacts.
4. **versions.json pin**: only then is `kernel.streams.<stream>` written from the verification result (`version`, `artifact_digest` = `sha256:` digest of `SHA256SUMS`, `provenance.tag`, `provenance.revision`, `provenance.bundle`), validated against `versions.schema.json` and `imago manifest validate`, and proposed as a pull request that adds only `versions.json`.

`kernel.streams` stays empty until the first `nucleus` release has passed this path; an image build consumes a kernel artifact only through a pinned stream.

### 4.2 Upstream Demand Pipeline (`imago` -> `nucleus`)

`imago` keeps its kernel requirement in [`kernel/requirement.json`](https://github.com/cordanaLLM/imago/blob/main/kernel/requirement.json) in the Aegis shape `aegis.p01-nucleus.kernel-requirement.v1`, the same document `cordanaLLM/Aegis-OS` sends to `nucleus` (its fixtures are vendored under `pkg/kernel/testdata/`). The decoder is strict: `correlation-id` (1..128 characters of `[A-Za-z0-9._-]`), 1..8 unique architecture tokens, `abi.minimum-release` as a dotted numeric release with optional bounded `target-release` or `module-abi`, and 1..512 features with unique `CONFIG_[A-Z0-9_]+` symbols, `state` in `built-in` or `module`, `probe` from the allow-list `kernel-config`, `lsm-list`, `btf-vmlinux`, `powercap`, `iommu-groups`, and a bounded `required-by` id (imago uses flavor tiers such as `FLAVOR-K8S-NODE`). An empty feature list is rejected explicitly (`ErrEmptyRequirement`) because it would let any kernel pass.

`dispatch-kernel-requirements.yml` runs `imago kernel requirement validate kernel/requirement.json` and emits `kernel_requirements_updated` to the provider named in `versions.json` with:

```json
{
  "source": "imago",
  "schema": "aegis.p01-nucleus.kernel-requirement.v1",
  "correlation_id": "imago-kernel-requirement-0001",
  "requirement": {"path": "kernel/requirement.json", "sha256": "<64 hex>", "ref": "<40 hex commit>"}
}
```

`nucleus` fetches the file at `ref`, checks its `sha256`, and evaluates every feature with the named probe. Its `verify-requirements.yml` still checks a fixed symbol list today; consuming the payload shape on the `nucleus` side is tracked there and does not weaken the downstream verification above.

---

## 5. Agent Bootstrapping & Migration Order

When launching an agent to bootstrap `nucleus`, provide the following prompt:

```text
You are an autonomous engineering agent initializing the repository nucleus.
Read the authoritative blueprint at:
docs/operations/sister-repo-kernel-forge-blueprint.md

Tasks:
1. Initialize repository scaffold, .gitignore, and versions.json SSOT with live streams (6.18 LTS, 7.2.4 Mainstream, 7.3-rc2 Bleeding, 7.2-rt Realtime).
2. Create configs/ for x86_64 and arm64 across all 4 streams adhering to CIS Level 2 hardening.
3. Implement scripts/build-kernel.sh and packaging scripts complying with NASA/JPL Power of 10.
4. Establish GitHub Actions CI, build matrix, and release dispatch workflows with top-level least-privilege permissions.
5. Create automated pytest suites validating kconfig syntax and the RFC 1918 zero-leak invariant.
6. Commit all files using Conventional Commits.
```

