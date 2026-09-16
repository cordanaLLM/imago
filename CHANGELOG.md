# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Aegis product-input acceptance (ADR-0020): `pkg/aegis` decodes `aegis.p01.product-input.v1` strictly (unknown fields, trailing content, and inputs above 1 MiB rejected), validates every field against documented bounds (retries 1..10 attempts and 0..3600 s backoff, 1..256 unique packages, 40-hex revision, relative definition paths), maps it to a typed build request with a symmetric `Result` type, and reports correlated errors; `imago aegis validate <path> [--json]` exposes it.
- Pinned kernel artifact contract with `cordanaLLM/nucleus` (ADR-0021): `pkg/kernel` strictly decodes the Aegis `aegis.p01-nucleus.kernel-requirement.v1` payload (fixtures vendored from `cordanallm/Aegis-OS@5148ab2` under `pkg/kernel/testdata/`, empty feature lists rejected with `ErrEmptyRequirement`) and the `imago.nucleus.kernel-artifact.v1` manifest, and `kernel.Verify` recomputes the `SHA256SUMS` digest, every artifact digest and size, and the presence of the cosign bundle under bounded reads.
- `imago kernel requirement validate` and `imago kernel artifact verify` CLI commands with positive, tampered-artifact, and empty-requirement tests; `kernel/requirement.json` carries imago's own requirement (`imago-kernel-requirement-0001`, `required-by` ids naming flavor tiers).
- Typed `kernel` section in `versions.json` and `versions.schema.json` pinning the provider `cordanaLLM/nucleus`, the contract id, the dispatch event, and per-stream `version`, `artifact_digest`, and provenance; `streams` is empty until the first verified nucleus release.
- Repository transferred to `cordanaLLM/imago` and the kernel forge to `cordanaLLM/nucleus`; badges, documentation portal URL, and the kernel dispatch target follow the new identities.
- Fleet migration to `cordanaLLM/imago` (ADR-0019): Go module `github.com/cordanaLLM/imago`, CLI and MCP server renamed to `imago`, praetor governance adopted with the interim `gitops-infra` profile, and a proposed `os-image` archetype under `planning/archetypes/`.
- Golusoris core composition: `core/clikit` command tree, `core/log` logger, `core/clock` injected into the build dispatcher and staging guard, and `core/mcp` owning the MCP transport (stdio stdout-purity guard and streamable-HTTP).
- Routed planning graph under `planning/` (praetor planning schema v1) with `imago plan validate`, `imago plan route`, and the `route_plan` MCP tool ranking ready work by (1 + transitive unblocks) / cost.
- CloudNative immutable container host and Kubernetes node flavors (`cloudnative-generic`, `cloudnative-k8s`).
- CNCF Storage appliance (`cloudnative-storage`) with NVMe-oF TCP, OpenZFS 2.3, iSCSI, and multipath support.
- CloudNativePG database host flavor (`cloudnative-pg`) with strict memory overcommit and checkpoint dirty-ratio tuning.
- K3s Edge Fleet flavors (`k3s-agent-generic`, `k3s-agent-intel`, `k3s-agent-amd`, `k3s-agent-nvidia`, `k3s-server-generic`).
- Hypervisor performance engine: weekly `fstrim.timer`, ZRAM swap guard, VirtIO `mq-deadline` scheduler, fast NoCloud cloud-init discovery.
- Single Source of Truth `versions.schema.json` schema validation for automated version bump decoupling.
- Dedicated segmented flavor catalog in `FLAVORS.md` partitioning 39 flavors across 6 workload tiers.
- Streamlined `README.md` with multi-tier badge rows, architecture diagram, and workload summary table.
- Interactive tabbed flavor explorer in `docs/flavors/matrix.md`.
- Comprehensive modular test coverage suite (48 tests across 8 modules: manifest SSOT, provisioner static analysis, flavor matrix, cloud-init seed data, documentation/ADR integrity, security/privacy invariants, Packer templates, and repository governance).
- Tier 7: Specialized Homelab Appliances (5 new flavors: `appliance-vision-nvr`, `appliance-gateway-dns`, `appliance-media-server`, `appliance-ci-runner`, `appliance-game-server`) addressing r/homelab and Steam survey hardware patterns.
- Comprehensive documentation bug hunt: corrected Tier 3 Kubernetes flavor count from 10 to 9, fixed 44-flavor count synchrony across matrix.md, and updated provisioner log messages in `61-cloudnative-immutable.sh`.
- Visual architecture overhaul: integrated 10 low-cognitive-load, theme-resilient Mermaid diagrams across landing pages, flavor matrix, Kubernetes node stack, AI inference pipeline, NTS multi-peer time architecture, direct disk streaming, CLI/MCP framing sequence, and multi-architecture boot hierarchy.
- Automated Mermaid syntax and diagram type verification suite in `tests/test_docs.py`.
- ADR-0009: Multi-Distribution Base OS Architecture and Roadmap (`docs/adr/0009-multi-distribution-base-roadmap.md`), establishing a 4-tier upstream strategy (Ubuntu LTS, Debian, Alpine, and bootc).
- High-contrast semantic color styling and theming across all architecture Mermaid flowcharts (landing pages, matrix, Kubernetes, AI inference, homelab appliances, and time security).
- ADR-0010: Modern Container Runtimes, Lazy-Pulling Snapshotters, and Zero-Footprint Diagnostic Tooling (`docs/adr/0010-container-ecosystem-runtimes-and-tooling.md`), incorporating insights from `pditommaso/awesome-containers` and companion cloud-native lists.
- High-performance dual OCI runtime support: configured `crun` alternative `RuntimeClass` in containerd alongside standard `runc` in `k8s-node-*` appliances, reducing container resident memory from ~25MB to ~4MB and cutting startup latency by 2–3x.
- Zero-footprint container diagnostics: integrated `cdebug` static binary across container appliances (`docker-*`, `podman-*`, `k8s-node-*`) for ephemeral container and pod troubleshooting without image bloat.
- Declarative SSOT schema expansion in `versions.json` and `versions.schema.json` tracking `runtimes.crun`, `runtimes.stargz_snapshotter`, `tools.cdebug`, and `tools.enroot`.
- ADR-0011: Enterprise Golden Image Hardening, Compliance Crosswalk, and Lifecycle Governance (`docs/adr/0011-enterprise-golden-image-compliance-and-lifecycle.md`).
- OpenSSH hardening drop-in (`/etc/ssh/sshd_config.d/00-hardened-sshd.conf`) enforcing CIS Level 2 / DISA STIG cryptographic suites (`chacha20-poly1305`, `aes256-gcm`), root login restriction, and OpenSSH Certificate Authority (`TrustedUserCAKeys`) support.
- NIST SP 800-53 (Rev. 5) & NIST SP 800-190 compliance crosswalk documented in `docs/standards/flavor-hardening-standards.md`.
- Multi-cloud KMS CMK cross-account grant patterns for `AWSServiceRoleForAutoScaling` and image gallery governance documented in `docs/platforms/cloud.md`.
- 30-day immutable image deprecation lifecycle policy and zero-patching fleet contract documented in `docs/operations/maintenance-cadence.md`.
- Declarative Goss dynamic compliance-as-code verification profile in `tests/compliance/goss.yaml`.
- Google AI Studio Managed Agents Fleet: defined 6 specialized autonomous agent manifests (`infra-forge`, `security-compliance`, `container-k8s`, `qa-gatekeeper`, `deep-researcher`, `docs-architect`) under `.agents/agents/` powered by `antigravity-preview-05-2026` and `deep-research-pro-preview-12-2025`.
- Dynamic Google AI Studio & Gemini Interactions API Agent Management CLI (`scripts/manage_aistudio_agents.py`) supporting agent validation, dry-run registration, and fleet synchronization.
- Worktree-isolated parallel agent execution engine (`scripts/orchestrate_fanout.py`) spawning isolated git worktrees (`.workingdir2/worktrees/agent-<role>`) complying with Hard Rule 11.
- Pre-execution privacy and zero-leak lifecycle guard (`.agents/hooks.json` and `.agents/hooks-scripts/guard_privacy.py`) intercepting tool calls to guarantee zero private RFC 1918 IPs or workstation home paths before any file modification.
- Comprehensive Managed Agents operations guide with saturated jewel-tone architecture flowcharts in `docs/operations/managed-agents.md`.
- Automated agent fleet integrity test suite in `tests/test_agents_fleet.py` validating schema adherence, hooks wiring, and privacy guard interception.

- ADR-0012: Universal Architecture Portability, Containerd 2.x CRI Modernization, and Dual-Stack Hardening (`docs/adr/0012-universal-arch-containerd2-and-dualstack-hardening.md`).
- Modernized containerd 2.x CRI schema support in `50-k8s-runtime.sh` configuring `crun` runtime classes under `plugins."io.containerd.cri.v1.runtime"` with legacy fallback.
- Dual-stack IPv4/IPv6 support in hardened OpenSSH (`00-base-strip.sh`) via `AddressFamily any` preserving CIS Level 2 cryptographic baselines.
- NIST SP 800-53 SI-4 compliant kernel audit logging (`audit=1 audit_backlog_limit=8192`) and `net.ipv4.tcp_syncookies = 1` in `20-kernel-sysctl.sh`.
- Comprehensive CLI unit test suite (`cmd/lusoris-forge/main_test.go`) validating all 10 root commands and subcommands.
- Declarative compliance inspection MCP tool (`inspect_compliance`) exposing CIS Level 2 and NIST SP 800-53 controls to autonomous agents.
- Upgraded `stargz_snapshotter` version to `0.18.2` across `versions.json`, Packer templates, and Go manifest structs for containerd 2.3+ compatibility.
- ADR-0013: Persistent Cross-Session Memory via Hindsight Semantic Backend & MCP Architecture (`docs/adr/0013-hindsight-semantic-memory-mcp.md`).
- Dual-layer MCP configuration (`.mcp.json` and `.agents/mcp_config.json`) and Hindsight JSON-RPC 2.0 stdio bridge (`scripts/hindsight_mcp_server.py`) with Hard Rule 6 zero-leak pre-sanitization and offline buffer resilience.
- Cluster tunnel supervisor daemon (`scripts/tunnel_hindsight.py`) managing loopback forwarding to cluster Hindsight services.
- Enterprise testing architecture expansion (205 tests total):
  - In-memory MCP JSON-RPC 2.0 protocol client-server test suite (`pkg/mcp/protocol_test.go`) validating all 10 tools.
  - Deep negative manifest validation across 14 failure modes and zero-allocation benchmark suite (`pkg/manifest/benchmark_test.go`: 461 ns/op, 0 B/op).
  - Hermetic shell mock execution sandbox (`tests/harness/mock_runner.py`, `tests/test_provisioners_execution.py`) running production provisioners under `set -euo pipefail` with isolated command journaling.
  - Live Docker container integration suite (`tests/test_container_integration.py`) validating `/usr/sbin/sshd -t`, sysctl kernel tuning, and CDI JSON in `ubuntu:24.04`.
  - Deep 4-platform x 7-tier cloud-init matrix tests (`tests/test_cloudinit_deep.py`).
  - Repository automation test suite (`tests/test_scripts_automation.py`) testing fleet manager, fanout worktrees, and zero-leak pre-tool hooks.
  - Quality gate orchestration targets: `make test-all`, `make test-bench`, `make test-coverage`.
  - ADR-0014: Automated Dependency & Security Governance via Zero-Noise Renovate and Native CodeQL (`docs/adr/0014-automated-dependency-management-renovate.md`).
  - Native GitHub CodeQL static analysis workflow (`.github/workflows/codeql.yml`) analyzing Go and Python codebases with `+security-and-quality` rules.
  - Zero-noise Renovate configuration (`renovate.json`) with automated GitHub Action commit SHA pinning (`helpers:pinGitHubActionDigests`), weekly Monday batch scheduling, 3-day release stability quarantine, and SSOT regex managers for `versions.json`.
  - OpenSSF Scorecard least-privilege token permissions across all GitHub Actions workflows (`contents: read` top-level default, job-scoped write permissions only).
  - Automated least-privilege workflow permission enforcement test (`test_workflows_least_privilege_permissions`) in `tests/test_security_privacy.py` and `codeql.yml` verification in `tests/test_governance.py`.
  - ADR-0015: Progressive Agent Skills, Reference Modularization, and Staged MCP Operations (`docs/adr/0015-progressive-agent-skills-and-staged-mcp-operations.md`).
  - Progressive Disclosure skills pattern: refactored `.agents/skills/build-image/` and `.agents/skills/add-flavor/` into 3-tier progressive disclosure structures with dedicated `references/` directories.
  - Two-Phase Staged MCP Operations: implemented `pkg/mcp/staging.go` providing in-memory concurrency-safe action staging, preview cards, and safety guardrails via `list_staged_actions`, `confirm_action`, and `discard_staged_action` for destructive or heavy mutations like `trigger_build`.
  - ADR-0016: Hypervisor and Image Runtime Optimizations (`docs/adr/0016-hypervisor-and-image-runtime-optimizations.md`), establishing NVMe/VirtIO `mq-deadline`, 1MB QCOW2 cluster sizing, and multi-queue virtio-net tuning.
  - ADR-0017: Developer Workstations, Single-Node Kubernetes, and Alternative Orchestration Engines (`docs/adr/0017-developer-workstations-single-node-k8s-and-orchestration-expansion.md`), detailing blueprints for `dev-workstation`, `k8s-node-standalone`, Docker Swarm, Nomad, Incus, and `appliance-dev-forge`.
  - ADR-0018: Storage & NAS Appliance Ecosystem Architecture (`docs/adr/0018-nas-and-storage-appliance-ecosystem.md`), establishing a dual-mode integration strategy for open-source (TrueNAS SCALE, OpenMediaVault, CasaOS/ZimaOS) and proprietary (QNAP QTScloud, Synology vDSM, StarWind) storage environments.
  - Comprehensive platform guides for TrueNAS SCALE (`docs/platforms/truenas.md`) and NAS/Storage Appliances (`docs/platforms/nas-appliances.md`).
  - Sister repository architectural blueprint for `lusoris-kernel-forge` (`docs/operations/sister-repo-kernel-forge-blueprint.md`), detailing multi-stream kernel building (`lts`, `mainstream`, `bleeding`, `realtime`) across architectures with zero-leak privacy invariants.
  - Cross-repository bidirectional synchronization workflows (`.github/workflows/sync-kernel-manifest.yml` and `.github/workflows/dispatch-kernel-requirements.yml`) with OpenSSF Scorecard least-privilege token permissions.
  - Fleet verification test `test_skills_progressive_disclosure_structure` in `tests/test_agents_fleet.py` ensuring all skills maintain high-density concise root instructions and partitioned reference manuals.
  - High-performance systems benchmarking suites: added `pkg/flavors/benchmark_test.go` ($O(1)$ lookups at ~9.5 ns/op, 0 allocs), `pkg/cloudinit/benchmark_test.go` (~494 ns/op), and `pkg/mcp/benchmark_test.go` (~11.9 ns/op).
  - Cross-platform hermetic mock execution sandbox (`tests/harness/mock_runner.py`) with dynamic bash resolution enabling 100% test execution on Linux, macOS, and Windows.
  - TrueNAS SCALE platform configuration in hardened cloud-init generator (`pkg/cloudinit/cloudinit.go`) with VirtIO-SCSI discard rules and NFS mounts.
  - Two-phase staged MCP operations TTL eviction guard and capacity bounding (`pkg/mcp/staging.go`).
  - Automated Go catalog and provisioner script synchrony invariant test (`test_go_catalog_provisioners_synchrony` in `tests/test_flavors.py`).

### Changed
- **Breaking**: `sync-kernel-manifest.yml` refuses a `kernel_release_published` payload without `stream`, `version`, and `tag` (the default-version fallback is removed), downloads the nucleus release, verifies the keyless cosign bundle over `SHA256SUMS`, runs `imago kernel artifact verify` against the payload and the `versions.json` contract pin, and only then proposes the `kernel.streams.<stream>` pin (version, `artifact_digest`, provenance) as a pull request that adds only `versions.json`.
- `dispatch-kernel-requirements.yml` validates `kernel/requirement.json` and dispatches its path, `sha256`, and commit to the provider named in `versions.json` instead of the unread drivers/runtimes/kubernetes triple; it triggers on changes to the requirement file.
- `docs/operations/sister-repo-kernel-forge-blueprint.md` section 4 documents the pinned contract: payload shape, manifest schema and bounds, and the verification order (cosign bundle, `SHA256SUMS` digest, per-artifact digests, `versions.json` pin).

### Fixed

- The build account is sealed by the shutdown command rather than by a provisioner.
  The shutdown authenticates with the build password, so locking that password
  beforehand left the machine unable to power off and the build waiting for it.

- Template cleanup seals the build account last instead of first. Revoking sudo at the
  start left every later step unable to run, so SSH hardening, the apt cache, the
  machine identity, host keys, logs and the free-space zeroing were all skipped while
  the build reported only that a terminal was required to authenticate.
- The cdebug installer names a release that exists. The manifest pinned 0.5.1, which
  upstream has never published, and the asset name carried a version the file name
  does not have; the download is now checked rather than discarded.

- The QEMU accelerator is a variable rather than a hardcoded `kvm`. A GitHub-hosted
  runner has no `/dev/kvm`, so every build died with "Qemu failed to start" as soon
  as it got past authoring the seed ISO; the workflow now emulates, while a build on
  real hardware keeps `kvm` by default.

- The weekly image build installs `xorriso`, so Packer can author the `cidata`
  ISO the cloud-init seed is delivered on. Without it every flavor failed in under
  fifteen seconds with "could not find a supported CD ISO creation command", which
  is why no image has ever been produced.
- Catalog desynchronization in `pkg/flavors/flavors.go`: aligned 13 provisioner script references with `packer/builds.pkr.hcl` across AMD, NVIDIA, Podman, K3s, and homelab appliance tiers, eliminating silent failures in imageless host conversion.
- Podman standard requirements inversion in `pkg/standards/standards.go`: ensured `podman-generic` enforces `podman`, `buildah`, `skopeo`, and `netavark` rather than Docker CE.
- Local Packer build command path in `pkg/builder/builder.go`: updated target directory from `.` to `packer/` for seamless execution from repository root.
- Universal multi-architecture portability: replaced hardcoded `[arch=amd64]` APT repository configurations with dynamic `$(dpkg --print-architecture)` in AMD ROCm (`32-gpu-amd-rocm.sh`) and Docker CE (`40-docker-runtime.sh`) provisioners.
- Package resolution in `25-baremetal-tuning.sh`: replaced non-existent package `partprobe` with GNU `parted` so disk partition probing utilities install properly.
- Architecture guard in `79-appliance-game.sh`: restricted `dpkg --add-architecture i386` multiarch registration to `amd64` hosts.
- CDI specification compliance in `75-appliance-vision.sh`: modernized `cdiVersion` from unquoted float `0.5.0` to semantic string `"0.6.0"`.
- Hardened loopback urllib usage in Hindsight MCP server (`scripts/hindsight_mcp_server.py`) and tunnel supervisor (`scripts/tunnel_hindsight.py`) with URL scheme validation and nosemgrep annotations, resolving Semgrep dynamic URL audit findings in CI.
- Corrected base OS badge and metadata to Ubuntu 26.04 LTS Resolute in `README.md`.
- Synchronized 44-flavor catalog count across repository map in `README.md` and test suite docstrings.

## [0.1.0] - 2026-09-09

### Added
- Initial repository bootstrap for lusoris-cloud-images.
- Standalone QEMU and Proxmox Packer HCL2 builders.
- Hardware-accelerated GPU stacks: Intel Arc/iGPU, AMD Radeon, NVIDIA Container Toolkit.
- Kubernetes node flavors with pre-baked containerd 2.x, kubelet, and daemonset caching.
- Automated verification suite and linters.
