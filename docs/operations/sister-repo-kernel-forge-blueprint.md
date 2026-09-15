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

## 4. Cross-Repository Bidirectional Synchronization Engine

`nucleus` and `imago` communicate autonomously via GitHub Actions `repository_dispatch` and Renovate custom managers:

### 4.1 Downstream Release Pipeline (`kernel-forge` -> `cloud-images`)
Upon successful compilation, signing, and APT publishing in `publish-release.yml`:
```yaml
name: Publish Kernel Release
on:
  push:
    tags: ['v*']

jobs:
  dispatch-downstream:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - name: Dispatch Release to imago
        uses: peter-evans/repository-dispatch@26b39f2445243964d4c7385747e4b2144255d441 # v3.0.0
        with:
          token: ${{ secrets.DISPATCH_ACCESS_TOKEN }}
          repository: cordanaLLM/imago
          event-type: kernel_release_published
          client-payload: >
            {
              "stream": "${{ matrix.stream }}",
              "version": "${{ github.ref_name }}",
              "architectures": ["x86_64", "arm64"],
              "sha256": "${{ steps.checksum.outputs.hash }}"
            }
```

### 4.2 Upstream Demand Pipeline (`cloud-images` -> `kernel-forge`)
When `imago` updates `versions.json` (e.g., driver updates or new flavor requirements):
- `dispatch-kernel-requirements.yml` emits `kernel_requirements_updated`.
- In `nucleus`, `verify-requirements.yml` automatically evaluates whether all `.config` trees contain the required symbols (`CONFIG_VIRTIO_NET=y`, `CONFIG_BBR3=m`, `CONFIG_PREEMPT_RT=y`, etc.).

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

