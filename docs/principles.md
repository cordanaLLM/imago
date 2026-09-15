# lusoris-cloud-images — Engineering Principles & Operating Contract

This document defines the non-negotiable engineering principles, architectural invariants, and operational standards for `lusoris-cloud-images`. It adapts the recurring fleet conventions across Lusoris and maintainer projects (`VMAFx/vmafx`, `20-watts-was-enough`, `golusoris/*`) to the requirements of an enterprise-grade, hardware-accelerated OS image forge.

Every rule is codified into automated tooling, test suites, or repository gates. Where a standard cannot yet be fully enforced by tooling, it operates as an authoritative review gate.

---

## 1. Authority & Enforcement Classes

Every requirement in this repository belongs to one of four enforcement classes:

| Class | Meaning | Concrete Mechanism |
| :--- | :--- | :--- |
| **CI Gate** | A continuous integration check automatically rejects non-compliant pull requests. | GitHub Actions (`ci.yml`, `security-scans.yml`, `required-aggregator.yml`), `make lint`, `make test`. |
| **Review Gate** | The contributor must demonstrate satisfaction of the standard; reviewers must reject non-compliant changes. | PR templates, architectural checklists, diff review. |
| **Guidance** | Followed by default; deliberate deviations require recorded justification in commit messages or ADRs. | Documentation best practices, styling guidelines. |
| **Staged Gate** | Adopted for all new and modified files; legacy surfaces migrate incrementally via ratchets. | Pre-commit hooks, incremental lint ratchet. |

---

## 2. NASA/JPL "Power of 10" Rules (Adapted for OS Image Forging & Shell)

Gerard J. Holzmann's [_The Power of 10: Rules for Developing Safety-Critical Code_](https://spinroot.com/gerard/pdf/P10.pdf) provides the baseline for reliability. Its principles are adapted directly to shell provisioners, Packer templates, Python verification suites, and system configuration:

| ID | Preserved Invariant | Project Adaptation | Enforcement |
| :--- | :--- | :--- | :--- |
| **P10-1** | Control flow remains inspectable. | Shell provisioners use straight-line execution and small helper functions. No recursion, no dynamic `eval`, no unstructured jumping. | Review gate + ShellCheck |
| **P10-2** | Bounded execution. | Every download, loop, package installation, and network probe has an explicit timeout and retry limit (`timeout`, `curl --max-time`, bounded loops). | CI gate (`test_provisioners_executable_and_strict`) |
| **P10-3** | Controlled resource growth. | Zero base bloat. OS images purge `snapd`, telemetry daemons, unneeded locales, and documentation. Partitions expand dynamically on first boot (`growpart`). | CI gate (`test_packer_validate`) + build size limits |
| **P10-4** | Short units of logic. | Function bodies in shell provisioners must be $\le$ 60 lines (one printed page). Python test functions must be $\le$ 60 lines. | CI gate (`test_provisioners_power_of_ten_function_length`) |
| **P10-5** | Executable contracts. | Automated Pytest suite asserts schema compliance of `versions.json`, checks provisioner executable bits, and verifies zero forbidden network strings. | CI gate (`pytest tests/ -v`) |
| **P10-6** | Minimal variable scope. | Shell functions declare local variables with `local`. Packer provisioner variables are explicitly passed via `environment_vars`. | CI gate (ShellCheck `SC3043` / `SC2155`) |
| **P10-7** | Every return code is checked. | All shell provisioners strictly enforce `set -euo pipefail`. Any discarded exit code must be handled explicitly. | CI gate (`test_provisioners_executable_and_strict`) |
| **P10-8** | Deterministic & auditable generation. | Single source of truth in `versions.json`. Images build deterministically via standalone QEMU/KVM without external runtime mutations. | CI gate + Packer validate |
| **P10-9** | Explicit data flow. | Variables pass from `versions.json` $\to$ Packer variables $\to$ shell environment variables. No hidden dynamic state or ad-hoc downloading. | Review gate + Pytest SSOT checks |
| **P10-10** | Strict toolchain merge floor. | Zero warnings across Packer validate, ShellCheck, Yamllint, shfmt, Codespell, and Pytest. | CI gate (`required-checks` aggregator) |

---

## 3. Single Source of Truth (`versions.json`)

1. **Declarative Invariant**: Distribution image URLs, checksums, kernel versions, driver versions, Kubernetes releases, and container image tags reside exclusively in [`versions.json`](https://github.com/lusoris/lusoris-cloud-images/blob/main/versions.json).
2. **Zero Hardcoded Versions**: Shell provisioners and Packer HCL templates never hardcode version numbers or branch names.
3. **Automated Drift Prevention**: Automated dependency tools (Renovate) update only `versions.json`, producing minimal, verifiable pull request diffs.

---

## 4. Generational Hardware Segmentation

Hardware acceleration drivers and runtimes must remain strictly isolated by generational architecture:
- **Intel Arc / Xe**: Dedicated Battlemage Xe2, Alchemist, Level Zero, and Media Driver stack ([`30-gpu-intel.sh`](https://github.com/lusoris/lusoris-cloud-images/blob/main/packer/provisioners/30-gpu-intel.sh)).
- **AMD Radeon / ROCm**: Segregated into user-space Mesa VA-API/RADV ([`31-gpu-amd-mesa.sh`](https://github.com/lusoris/lusoris-cloud-images/blob/main/packer/provisioners/31-gpu-amd-mesa.sh)) and ROCm 10 compute ([`32-gpu-amd-rocm.sh`](https://github.com/lusoris/lusoris-cloud-images/blob/main/packer/provisioners/32-gpu-amd-rocm.sh)).
- **NVIDIA Segmentation**:
  - `legacy`: Driver 535 + CUDA 12.2 (Pascal / Volta).
  - `mainstream`: Driver 565 + CUDA 12.8 (Turing / Ampere / Ada).
  - `bleeding`: Driver 615 + CUDA 13.4 (Blackwell RTX 5090 / B200).
  - `datacenter`: NVIDIA Open Kernel Modules + Fabric Manager (Hopper / Blackwell).

Cross-generation driver mixing or monolithic "universal" driver bloat is strictly prohibited to prevent kernel module conflicts and ABI drift.

---

## 5. Privacy & Zero-Leak Invariant

1. **No RFC 1918 Private Addresses**: Code, documentation, scripts, and sample configs must never contain private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`). Always use standard IETF documentation addresses (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`, `example.com`).
2. **No Workstation Path Leaks**: Developer home directories (`/home/username/...`) must never be hardcoded into configuration, tests, or documentation.
3. **Automated Enforcement**: Verified by `test_no_private_ips_or_user_paths` in `tests/test_config.py` and Gitleaks history scanning.

---

## 6. Architecture Decision Records (ADRs)

1. **Pre-Commit Decision Records**: Every non-trivial architectural, platform, or security design decision must be documented as an ADR under [`adr/README.md`](adr/README.md) **before or alongside** the implementing commit.
2. **Template & Structure**: Follow [`adr/README.md`](adr/README.md): Title, Status, Context, Decision, Consequences.
3. **Immutable History**: ADRs are append-only. Superseded decisions are marked `Superseded by ADR-NNNN` rather than deleted or rewritten.

---

## 7. Trunk-Based Development & PR Merge Flow

1. **No Direct Commits to `main`**: Direct pushes to `main` are blocked by branch protection.
2. **Short-Lived Branches & Worktrees**: Contributors and agents author changes in isolated branches (`feat/*`, `fix/*`, `chore/*`) or git worktrees.
3. **Required CI Aggregator**: Pull requests must pass the `required-checks` aggregator before merging.
4. **Squash & Merge with Conventional Commits**: Commits are squashed into `main` using Conventional Commits syntax (`feat:`, `fix:`, `chore:`, `docs:`), maintaining a linear, bisectable history.

---

## 8. Docs & Code Synchrony

1. **Atomic Documentation**: Every user-discoverable addition or modification (new flavor, CLI flag, build target, or provisioner parameter) must be fully documented under [the documentation portal](index.md) and [`README.md`](https://github.com/lusoris/lusoris-cloud-images/blob/main/README.md) in the **exact same pull request**.
2. **Strict MkDocs Verification**: The documentation portal must build with `mkdocs build --strict` with zero broken links and zero warnings.

---

## 9. Universal Architecture, Workstation Portability & Open Standards

1. **Universal Architecture Matrix**: All images structurally target `x86_64` (amd64-v3), `arm64` (Raspberry Pi 5 NVMe, Rockchip RK3588, Apple Silicon M1–M4, Ampere/Grace), and `riscv64` (OpenSBI).
2. **Developer Workstation Portability**: First-class support for macOS (UTM, OrbStack, Lima, Rosetta 2 Linux translation, VirtIO-FS) and Windows (WSL2 rootfs import with `systemd=true`, Hyper-V Gen2 integration services).
3. **Ultra-Deep Slimming & Sub-Second Boot**: Every image boots in < 1.5s via NoCloud fast-pathing and systemd unit masking, prunes ~450MB of unnecessary desktop/wireless firmware, and prevents memory exhaustion with in-memory ZRAM swap.
4. **Open Sovereign Standards**: Built upon Discoverable Partitions Specification (DPS), Unified Kernel Images (UKI), Container Device Interface (CDI v0.6+), VirtIO 1.3, and EU Cyber Resilience Act (CRA) compliance.

---

## 10. Multi-Language Engineering Contract, Automated Epics/Milestones & Fine-Grained CI Minimization

1. **Multi-Language Power of 10 Contract**:
   - **Shell**: `set -euo pipefail`, functions $\le 60$ lines, bounded network/process execution (`timeout`, `curl --max-time`), zero ShellCheck warnings.
   - **Python**: Strict type annotations, test functions $\le 60$ lines, table-driven pytest execution, zero linter warnings.
   - **Go 1.27**: Unified `imago` CLI and official Model Context Protocol (MCP) server. Functions $\le 60$ statements, small interfaces ($\le 5$ methods), `stdoutRedirect` JSON-RPC framing protection, and `slog` exclusively to stderr.
   - **HCL & YAML**: Declarative SSOT injection from `versions.json`, strict yamllint and actionlint compliance.
2. **Automated Epics & Milestones Lifecycle**:
   - Machine-readable tracking catalogs in `.github/epics.json` and `.github/milestones.json`.
   - Automated PR hard gates (`.github/workflows/pr-project-gate.yml`) verifying milestone assignment, issue/epic references, and tier labels.
3. **Fine-Grained Path-Filtered CI Minimization**:
   - CI pipelines strictly execute only the jobs corresponding to modified change vectors (`packer`, `shell`, `go`, `python`, `docs`, `workflows`), eliminating maintenance bottlenecks and compute waste.
