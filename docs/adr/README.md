# Architecture Decision Records (ADRs)

We document significant technical decisions using Architecture Decision Records in Nygard format.

## Immutable Once Accepted

Once an ADR reaches status **Accepted**, its text is immutable. If architectural direction evolves, a new ADR is created that supersedes the prior one.

## Seed ADRs

| # | Title | Status | Date |
| :--- | :--- | :--- | :--- |
| [0001](0001-declarative-version-manifest.md) | Centralized Declarative Version Manifest (`versions.json`) | Accepted | 2026-09-10 |
| [0002](0002-global-anycast-nts-time.md) | Multi-Tiered Global Anycast & Stratum-1 NTS Topology | Accepted | 2026-09-10 |
| [0003](0003-nvidia-generational-segmentation.md) | NVIDIA Multi-Generational CUDA & Driver Segmentation | Accepted | 2026-09-10 |
| [0004](0004-hypervisor-agent-coexistence.md) | Hypervisor Guest Agent Coexistence (QEMU + VMware) | Accepted | 2026-09-10 |
| [0005](0005-baremetal-streaming-install.md) | Bare-Metal Compressed Block Streaming Installation | Accepted | 2026-09-10 |
| [0006](0006-k3s-edge-fleet-flavors.md) | K3s Lightweight Fleet Edge Flavors | Accepted | 2026-09-10 |
| [0007](0007-cloudnative-and-cncf-storage-appliances.md) | Cloud-Native Immutable and CNCF Storage Appliances | Accepted | 2026-09-10 |
| [0008](0008-specialized-homelab-appliances.md) | Specialized Homelab Appliance Flavors | Accepted | 2026-09-10 |
| [0009](0009-multi-distribution-base-roadmap.md) | Multi-Distribution Base OS Architecture and Roadmap | Accepted | 2026-09-10 |
| [0010](0010-container-ecosystem-runtimes-and-tooling.md) | Modern Container Runtimes, Lazy-Pulling Snapshotters, and Zero-Footprint Diagnostic Tooling | Accepted | 2026-09-10 |
| [0011](0011-enterprise-golden-image-compliance-and-lifecycle.md) | Enterprise Golden Image Hardening, Compliance Crosswalk, and Lifecycle Governance | Accepted | 2026-09-10 |
| [0012](0012-universal-arch-containerd2-and-dualstack-hardening.md) | Universal Architecture Portability, Containerd 2.x CRI Modernization, and Dual-Stack Hardening | Accepted | 2026-09-10 |
| [0013](0013-hindsight-semantic-memory-mcp.md) | Persistent Cross-Session Memory via Hindsight Semantic Backend & MCP Architecture | Accepted | 2026-09-10 |
| [0014](0014-automated-dependency-management-renovate.md) | Automated Dependency & Security Governance via Zero-Noise Renovate and Native CodeQL | Accepted | 2026-09-10 |
| [0015](0015-progressive-agent-skills-and-staged-mcp-operations.md) | Progressive Disclosure Agent Skills & Two-Phase Staged MCP Mutation Guardrails | Accepted | 2026-09-10 |
| [0016](0016-hypervisor-and-image-runtime-optimizations.md) | Hypervisor, Storage, and Runtime Image Optimization Architecture | Accepted | 2026-09-10 |
| [0017](0017-developer-workstations-single-node-k8s-and-orchestration-expansion.md) | Developer Workstation Environments, Single-Node Kubernetes, and Clustered Orchestration Expansion | Accepted | 2026-09-10 |
| [0018](0018-nas-and-storage-appliance-ecosystem.md) | Open-Source and Virtual Network Attached Storage (NAS) Ecosystem Architecture | Accepted | 2026-09-10 |
| [0019](0019-imago-fleet-migration-praetor-golusoris-planning-graph.md) | Fleet Migration to cordanaLLM/imago: Praetor Governance, Golusoris Core, and a Routed Planning Graph | Accepted | 2026-09-15 |
| [0020](0020-aegis-product-input-contract-acceptance.md) | Aegis Product-Input Contract Acceptance | Accepted | 2026-09-15 |
| [0021](0021-pinned-kernel-artifact-contract-with-nucleus.md) | Pinned Kernel Artifact Contract with cordanaLLM/nucleus | Accepted | 2026-09-15 |


