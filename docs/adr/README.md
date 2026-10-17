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
| [0020](0020-aegis-product-input-contract-acceptance.md) | Aegis Product-Input Contract Acceptance | Accepted; amended by [0028](0028-one-reason-bound-for-every-contract-parser.md); decision 4 superseded by [0030](0030-kernel-requirement-decoder-follows-the-schema-owner.md) | 2026-09-15 |
| [0021](0021-pinned-kernel-artifact-contract-with-nucleus.md) | Pinned Kernel Artifact Contract with cordanaLLM/nucleus | Accepted; amended by [0028](0028-one-reason-bound-for-every-contract-parser.md) | 2026-09-15 |
| [0022](0022-fail-closed-provisioners-and-declared-main-protection.md) | Fail-Closed Provisioners and a Declared Rule Set for `main` | Accepted | 2026-10-11 |
| [0023](0023-eupl-1.2-licence-and-reuse-annotations.md) | EUPL-1.2 Licence and REUSE Annotations | Accepted | 2026-10-11 |
| [0024](0024-product-result-emitter-and-signature-reference-form.md) | Product-Result Emitter and the Signature Reference Form | Accepted | 2026-10-11 |
| [0025](0025-forge-as-record-of-open-work-and-frozen-planning-graph.md) | The Forge as the Record of Open Work and a Frozen Planning Graph | Accepted | 2026-10-11 |
| [0026](0026-required-checks-accept-only-detector-decided-skips.md) | Required Checks Accept Only Detector-Decided Skips | Superseded by [0027](0027-pull-request-jobs-never-skip-path-filter-per-job.md) | 2026-10-12 |
| [0027](0027-pull-request-jobs-never-skip-path-filter-per-job.md) | Pull Request Jobs Never Skip; Each Job Filters Its Own Paths | Accepted | 2026-10-14 |
| [0028](0028-one-reason-bound-for-every-contract-parser.md) | One Reason Bound for Every Contract Parser | Accepted | 2026-10-14 |
| [0030](0030-kernel-requirement-decoder-follows-the-schema-owner.md) | The Kernel Requirement Decoder Follows the Schema Owner | Accepted | 2026-10-17 |
