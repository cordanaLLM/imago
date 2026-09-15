<!-- markdownlint-disable MD013 MD025 -->
# cordanaLLM/imago Agent Operating Harness

Run verification before concluding any turn:

```bash
make verify-all
```

```mermaid
flowchart LR
    AGENT["Autonomous Agent"] --> CHECK["make verify-all"]
    CHECK --> AUDIT["standardsctl audit"]
    CHECK --> COMPILER["standardsctl compile-context --verify"]
    CHECK --> GATE{"All checks Pass?"}
    GATE -- Yes --> RECEIPT["Ed25519 Exit-0 Receipt"]
    GATE -- No --> DISTILL["SARIF Diagnostic Distillation (<= 1500 tokens)"]
```

## Core Directives & Invariants (Modernized NASA JPL Power-of-10)

| Invariant | Scope | NASA Rule | Enforcement Mechanism | Failure Action |
| :--- | :--- | :--- | :--- | :--- |
| **HISS-01** | Control Flow | Rule 1 | Recursion strictly prohibited; call graph must be DAG; zero `goto`. | Immediate build failure |
| **HISS-02** | Loops & I/O | Rule 2 | Scalar upper bound on all loops; explicit `context.Context` timeout on all I/O. | Semgrep / AST error |
| **HISS-03** | Memory | Rule 3 | Zero dynamic heap allocation (`malloc` / `free`) in hot simulation/tick loops. | Allocation audit sweep |
| **HISS-04** | Complexity | Rule 4 | Function length $\le 60$ LOC, McCabe Cyclomatic $\le 10$, Statements $\le 50$. | AST sweep blocker |
| **HISS-07** | Error Handling | Rule 7 | Zero `.unwrap()` / `.expect()`; all errors handled or wrapped with context. | Linter / Compiler error |
| **HISS-08** | Determinism | Rule 8 | Zero dynamic execution (`eval` / `exec`); zero banned unsafe libc (`gets` / `strcpy` / `sprintf`). | AST / Linter error |
| **HISS-09** | Reference Safety | Rule 9 | Mandatory `// SAFETY:` proofs for all pointer arithmetic and `unsafe` blocks. | AST check blocker |
| **HISS-10** | Warning Hygiene | Rule 10 | Zero-warning tolerance across compiler, linter, and format sweeps. | Exit code 1 |
| **HISS-15** | 3D Testing | Rule 5 | Positive, negative, and boundary tests mandatory for all public interfaces. | CI coverage gate |
| **HISS-16** | Context Integrity | Fleet | Single canonical `AGENTS.md`; vendor files compiled via `standardsctl compile-context`. | Pre-commit blocker |

## Operational Rules

1. **Act on Verified State**:
   Read source files and run real commands before hypothesizing or editing. Never guess flag names, library signatures, or repo configurations from memory.

2. **Lead with Output**:
   Provide direct answers, diffs, and commands. Avoid filler preambles, "Based on", restatements, or conversational chatter.

3. **Context Transpiler First**:
   Never edit `CLAUDE.md`, `.cursor/rules/*.mdc`, `.windsurfrules`, or `.github/copilot-instructions.md` manually. Make all agent instruction updates in `AGENTS.md` and execute:

   ```bash
   standardsctl compile-context
   ```

4. **SARIF Diagnostic Distillation**:
   When reporting compiler or linter errors, distill output to $\le 1,500$ tokens ($< 60$ lines). Print the top 3 root-cause failures with file/line pointers and write full SARIF logs to ephemeral storage.

5. **No Evasion Tolerated**:
   Do not attempt `--no-verify`, `LEFTHOOK=0`, or modifying `.git/hooks`. All pull requests are authoritatively re-checked in an ephemeral isolated sandbox by `cordana-standards[bot]`.

6. **Anti-Loop Interception**:
   If the same AST diff and error category repeats $\ge 3$ times, halt execution immediately. Re-evaluate the underlying design instead of making micro-textual retries.

## Primary Verification Commands

```bash
# Fast local test suite
# Declared commands only; run them before claiming application verification.
'go' 'build' '-v' './...'
'go' 'test' '-v' '-race' './...'
'python3' '-m' 'pytest'

# Recompile and verify cross-agent context outputs
standardsctl compile-context --verify

# Audit repository against declared HISS-16 standards
standardsctl audit

# Run all formatting, linting, and security gates
make verify-all
```

<!-- praetor:harness:end -->

---

# AGENTS.md — Agent & Contributor Directives

> Authoritative operating guide for all autonomous engineering agents and human contributors in `cordanaLLM/imago` (formerly `lusoris/lusoris-cloud-images`; the transfer is tracked in [`planning/TODO.md`](planning/TODO.md)).
>
> **Read [`docs/principles.md`](docs/principles.md) before changing this repository.** It is the project-wide engineering and architecture contract. Then consult [`docs/repository-rule-crosswalk.md`](docs/repository-rule-crosswalk.md) for fleet standards cross-walked from `VMAFx/vmafx` and `20-watts-was-enough`.

---

## 🌟 TOP-PRIORITY GLOBAL RULES

These rules apply to ALL agents, ALL tools, and ALL commits — without exception:

1. **Read `docs/principles.md` First**: It defines the authority classes, Holzmann Power of 10 adaptations, and architectural contracts.
2. **Single Source of Truth (`versions.json`)**: Never hardcode distribution URLs, Kubernetes versions, container tags, or driver branches in Packer templates or shell provisioners. All versions must originate from [`versions.json`](versions.json) and be injected via Packer environment variables.
3. **Trunk-Based PR Merge Flow**: Direct commits to `main` are strictly prohibited. Always create a short-lived branch (`feat/*`, `fix/*`, `chore/*`), run all local quality gates, push, and open a PR with `gh pr create`. Merges require passing the `required-checks` aggregator.
4. **Docs & Code Synchrony**: Every user-discoverable change (new flavor, configuration variable, or provisioner step) must be reflected in documentation ([README.md](README.md) and [`docs/`](docs/)) in the **exact same commit/PR**.
5. **NASA/JPL Power of 10 Compliance**: All shell provisioner functions must be $\le$ 60 lines, enforce `set -euo pipefail`, check return codes, and pass ShellCheck with zero warnings.
6. **Privacy & Zero-Leak Invariant**: Never commit private RFC 1918 IP addresses (`10.x`, `192.168.x`, `172.16-31.x`) or local workstation home paths. Use standard documentation placeholders (`192.0.2.x`, `pve.example.com`).
7. **All Documentation in English**: All commit messages, code comments, documentation, and agent reports must be written in a neutral, professional English register.

---

## 1. Mission & Purpose

`lusoris-cloud-images` produces clean, hardened, production-ready cloud and bare-metal OS images optimized for virtualization (Proxmox VE, Unraid, VMware ESXi, QEMU/KVM, Public Clouds) and bare-metal servers.

Key capabilities:
- **Zero Base Bloat**: Purges `snapd`, `lxd`, Ubuntu Pro telemetry, motd news, and unneeded documentation/locales.
- **Hardware Acceleration Flavors**: Dedicated flavors for Intel Arc/Xe, AMD Mesa/ROCm, and NVIDIA generational CUDA (Pascal 535, Ampere/Ada 565, Hopper/Blackwell Open + Fabric Manager).
- **Multi-Hypervisor Portability**: Coexistence of `qemu-guest-agent`, `open-vm-tools`, Unraid `virtiofs`/`9p` host sharing, and ACPI clean power shutdown.
- **Bare-Metal & Hypervisor Performance Engine**: NVMe/VirtIO `mq-deadline` I/O scheduling, automated weekly `fstrim.timer`, ZRAM in-memory swap guard, fast-boot `NoCloud` cloud-init discovery, BBR congestion control, and direct disk streaming (`lusoris-install-to-disk`).
- **Resilient Global Time**: Cryptographically authenticated Network Time Security (NTS) combining Cloudflare Anycast NTS and European Stratum-1 national laboratories (PTB, Netnod, SIDN, 3eck) with graceful fallback.

---

## 2. Conventional Entry Points & Skills Library

Autonomous agents should utilize specialized project skills under `.agents/skills/`:

| Task | Skill Entry Point | Description |
| :--- | :--- | :--- |
| **Build OS Image** | [`.agents/skills/build-image/SKILL.md`](.agents/skills/build-image/SKILL.md) | Build image flavor via Packer QEMU or Proxmox |
| **Test Image & Config** | [`.agents/skills/test-image/SKILL.md`](.agents/skills/test-image/SKILL.md) | Run automated pytest verification suite |
| **Lint Entire Repo** | [`.agents/skills/lint-all/SKILL.md`](.agents/skills/lint-all/SKILL.md) | Run Packer validate, ShellCheck, Yamllint, shfmt |
| **Format All Files** | [`.agents/skills/format-all/SKILL.md`](.agents/skills/format-all/SKILL.md) | Format shell (`shfmt`), Packer (`packer fmt`), YAML |
| **Add New Flavor** | [`.agents/skills/add-flavor/SKILL.md`](.agents/skills/add-flavor/SKILL.md) | Add flavor to manifest, HCL, tests, and docs |
| **Draft Commit Message** | [`.agents/skills/dev-llm-commitmsg/SKILL.md`](.agents/skills/dev-llm-commitmsg/SKILL.md) | Conventional Commits drafting |
| **Regenerate Docs** | [`.agents/skills/regen-docs/SKILL.md`](.agents/skills/regen-docs/SKILL.md) | Strict Material for MkDocs build |
| **Prepare Release** | [`.agents/skills/prep-release/SKILL.md`](.agents/skills/prep-release/SKILL.md) | Pre-release verification checklist |

---

## 3. The 4-Dimensional Flavor Matrix (44 Flavors)

| Workload Tier | Hardware Stack | Flavor Target | Key Components |
| :--- | :--- | :--- | :--- |
| **Base** | Generic (VirtIO) | `base-generic` | Minimal hardened OS, Anycast NTS, QEMU+VMware agents |
| **Base** | Intel GPU | `base-intel` | Intel Media Driver (`iHD`), Level Zero, vainfo, Battlemage Xe2 |
| **Base** | AMD GPU | `base-amd` | AMD Mesa VA-API (`radeonsi`), RADV Vulkan, AMDGPU DRM |
| **Base** | NVIDIA Legacy | `base-nvidia-legacy` | NVIDIA 535 driver branch, CUDA 12.2 (Pascal/Volta) |
| **Base** | NVIDIA Mainstream | `base-nvidia-mainstream`| NVIDIA 565 driver branch, CUDA 12.8 (RTX/Ampere) |
| **Base** | NVIDIA Modern | `base-nvidia-modern` | NVIDIA 610 driver branch, CUDA 13.3 (Ada/Hopper) |
| **Base** | NVIDIA Bleeding | `base-nvidia-bleeding` | NVIDIA 615 driver branch, CUDA 13.4 (Blackwell RTX 5090) |
| **Base** | NVIDIA Datacenter | `base-nvidia-datacenter`| NVIDIA Open Kernel Modules, Fabric Manager (Hopper/Blackwell) |
| **Docker** | Generic (VirtIO) | `docker-generic` | Docker CE 29.8, Docker Compose v2, containerd, log rotation |
| **Docker** | Intel GPU | `docker-intel` | Docker CE + Intel Media/Compute + QuickSync passthrough |
| **Docker** | AMD GPU | `docker-amd` | Docker CE + AMD ROCm 10 compute runtime |
| **Docker** | NVIDIA Mainstream | `docker-nvidia` | Docker CE + NVIDIA Container Toolkit + CDI specifications |
| **Docker** | NVIDIA Modern | `docker-nvidia-modern` | Docker CE + NVIDIA 610 + NVIDIA Container Toolkit CDI |
| **Docker** | NVIDIA Bleeding | `docker-nvidia-bleeding`| Docker CE + NVIDIA 615 + NVIDIA Container Toolkit CDI |
| **Podman** | Generic (VirtIO) | `podman-generic` | Podman 5.x, Buildah, Skopeo, Quadlet, Netavark CNI |
| **Kubernetes**| Generic (VirtIO) | `k8s-node-generic` | containerd 2.3.5, kubelet/kubeadm 1.37.0, lean zero-preheat |
| **Kubernetes**| Generic (VirtIO) | `k8s-node-cilium` | containerd 2.3.5, preheated Cilium 1.20.1 & kube-vip 1.2.3 |
| **Kubernetes**| Generic (VirtIO) | `k8s-node-calico` | containerd 2.3.5, preheated Calico 3.32.2 & kube-vip 1.2.3 |
| **Kubernetes**| Generic (VirtIO) | `k8s-node-flannel` | containerd 2.3.5, preheated Flannel 0.28.9 & kube-vip 1.2.3 |
| **Kubernetes**| Intel GPU | `k8s-node-intel` | containerd 2.3.5 + Intel drivers + Intel K8s Device Plugin |
| **Kubernetes**| AMD GPU | `k8s-node-amd` | containerd 2.3.5 + AMD ROCm 10 + AMD K8s Device Plugin |
| **Kubernetes**| NVIDIA Mainstream | `k8s-node-nvidia` | containerd 2.3.5 + NVIDIA 565 + NVIDIA K8s Device Plugin |
| **Kubernetes**| NVIDIA Modern | `k8s-node-nvidia-modern` | containerd 2.3.5 + NVIDIA 610 + NVIDIA K8s Device Plugin |
| **Kubernetes**| NVIDIA Bleeding | `k8s-node-nvidia-bleeding`| containerd 2.3.5 + NVIDIA 615 + NVIDIA K8s Device Plugin |
| **K3s Edge** | Generic (VirtIO) | `k3s-agent-generic` | Lightweight K3s agent, containerd, Flannel (< 300MB RAM) |
| **K3s Edge** | Intel GPU | `k3s-agent-intel` | K3s agent + Intel QuickSync passthrough (`iHD`) + Level Zero |
| **K3s Edge** | AMD GPU | `k3s-agent-amd` | K3s agent + AMD ROCm 10 compute runtime + RADV Vulkan |
| **K3s Edge** | NVIDIA Mainstream | `k3s-agent-nvidia` | K3s agent + NVIDIA 565 + Container Toolkit CDI |
| **K3s Edge** | Control Plane | `k3s-server-generic` | K3s standalone master, embedded SQLite, local-path storage |
| **CloudNative**| Generic (VirtIO) | `cloudnative-generic` | Immutable container host, read-only root, ephemeral tmpfs, containerd CDI |
| **CloudNative**| Generic (VirtIO) | `cloudnative-k8s` | Immutable Kubernetes node, read-only root, containerd 2.3.5, kubelet 1.37.0 |
| **CloudNative**| Storage (CNCF) | `cloudnative-storage` | NVMe-oF (TCP), OpenZFS 2.3, iSCSI, multipath, NFS |
| **CloudNative**| Database (CNPG) | `cloudnative-pg` | PostgreSQL / CloudNativePG kernel tuning, hugepages, strict overcommit |
| **AI Infer** | Generic (CPU) | `ai-infer-generic` | AMX, AVX-512, NUMA, vLLM/Ollama CPU, Docker CE |
| **AI Infer** | Intel GPU | `ai-infer-intel` | Intel Level Zero, OpenVINO, IPEX-LLM, CDI, Docker CE |
| **AI Infer** | AMD GPU | `ai-infer-amd` | AMD ROCm 10, /dev/kfd, RDNA 3/4 & Instinct, CDI, Docker CE |
| **AI Infer** | NVIDIA Mainstream | `ai-infer-nvidia` | Transparent hugepages, numactl, vLLM/Ollama (NVIDIA 565) |
| **AI Infer** | NVIDIA Modern | `ai-infer-nvidia-modern` | Transparent hugepages, numactl, vLLM/Ollama (NVIDIA 610) |
| **AI Infer** | NVIDIA Bleeding | `ai-infer-nvidia-bleeding`| Transparent hugepages, Blackwell RTX 5090 / B200 (NVIDIA 615) |
| **Homelab** | Intel GPU + Coral | `appliance-vision-nvr` | Coral Edge TPU (`gasket-dkms`, udev), Intel QuickSync (`iHD`), CDI, Docker CE |
| **Homelab** | VirtIO / Low-Power | `appliance-gateway-dns` | Port 53 stub disabled, WireGuard, line-rate forwarding (< 150MB RAM) |
| **Homelab** | Intel + AMD GPU + NAS | `appliance-media-server`| Intel QuickSync + AMD Mesa VA-API, `nfs-common`, `cifs-utils`, 4096KB readahead |
| **Homelab** | Multi-Core CPU / DinD | `appliance-ci-runner` | QEMU ARM64/ARMv7 binfmt, Docker Buildx, `git-lfs`, 4GB tmpfs `/tmp` |
| **Homelab** | High Clock CPU | `appliance-game-server` | 32-bit `i386` glibc, `steamcmd`, 16MB UDP socket buffer tuning, 1M file limits |

---

## 4. Working Sequence

Quick verification commands (run the targeted ones while developing, all before a pull request):

```bash
make fmt-check                  # Verify Packer HCL formatting
make lint                       # packer validate, shellcheck, actionlint, yamllint
make test-go                    # Go unit tests (golusoris core composition)
make test                       # Go + Pytest verification suites
make verify-all                 # Praetor gate: compile-context --verify, audit, build, tests
imago plan route --ready        # Ranked ready set of the planning graph
```


1. **Inspect Authority**: Read the relevant authority file (`docs/principles.md`, `versions.json`, or the nearest docs). Before commit, inspect staged, unstaged, and untracked changes.
2. **Smallest Coherent Patch**: Make the minimal changes necessary. Do not rewrite nearby code or configs for style alone.
3. **Select & Run Local Checks**: Run targeted verification during development (`packer fmt`, `pytest -k ...`), and run full gates (`make lint`, `make test`) before pushing or creating a pull request.
4. **Update Changelog & Records**: Update `CHANGELOG.md` for notable changes. Add an ADR under `docs/adr/` when an architecture, flavor, or policy decision changes durably.
5. **Conventional Commits**: Draft clear, descriptive commit messages adhering strictly to Conventional Commits (`type(scope): subject`).
6. **Worktree Hygiene**: Keep auxiliary Git worktrees under the ignored `.workingdir2/worktrees/` directory instead of creating repository siblings.
7. **Prose Integrity**: Project-authored documentation and comments must carry high-density technical information rather than generated-sounding filler.

---

## 5. Hard Rules

1. **Single Source of Truth**: Never hardcode versions, tags, URLs, or driver branches in templates or scripts. All versions originate exclusively from [`versions.json`](versions.json).
2. **Never `git push --force` to `main`**.
3. **Never commit directly to `main`** — pull requests with squash or rebase merge only.
4. **Never merge without `make lint` + `make test` green** locally and in CI.
5. **Every commit message follows Conventional Commits** (`type(scope): subject`).
6. **Every new script or code file starts with license header** (`Copyright 2026 Lusoris`).
7. **Every user-discoverable surface ships human-readable documentation** under `docs/` in the same PR.
8. **Every non-trivial architectural or policy decision ships an ADR** under [`docs/adr/`](docs/adr/) before or alongside the code.
9. **Power of 10 compliance**: Shell functions $\le$ 60 lines, `set -euo pipefail`, bounded loops, zero linter warnings.
10. **Privacy & Zero-Leak invariant**: Zero private RFC 1918 IPs, zero `/home/*` workstation paths.
11. **Worktree discipline**: Background coding agents run in isolated git worktrees (`.workingdir2/worktrees/`) or dedicated branches; never execute concurrent tasks in the main worktree.
12. **All documentation in English**: Commit messages, code comments, and documentation must be in neutral, professional English.
13. **Interaction style — ask only on real forks**: Act on unambiguous work directly. When a genuine fork arises (destructive trade-off, target ambiguity), ask concise, structured questions.
14. **No placeholder contact emails**: Never provide made-up or placeholder emails; route security reports and discussions exclusively to GitHub native surfaces (`/security/advisories/new`, `/discussions`).
15. **Normative Default**: EU and German data protection and software security standards are the normative default. Do not infer compliance from titles alone.

