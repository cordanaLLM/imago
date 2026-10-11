# ADR 0007: Cloud-Native Immutable and CNCF Storage Appliances

## Status

Accepted

## Context

Production container platforms and stateful database engines demand runtime invariants that differ from mutable, general-purpose server distributions:

1. **Configuration Drift & Attack Surface**: Long-lived mutable nodes suffer from uncontrolled configuration drift, unversioned package updates, and persistent file modification across reboots. Declarative container systems benefit from read-only root filesystems and volatile runtime state.
2. **CNCF Storage Orchestration**: Modern Kubernetes storage operators (e.g., Rook-Ceph, Longhorn, OpenEBS LocalPV) require low-level storage protocol support, including NVMe-oF (NVMe over Fabrics TCP), OpenZFS 2.3, multipath I/O, and iSCSI.
3. **Database Kernel Constraints**: Transactional database management systems like PostgreSQL and CloudNativePG require strict kernel virtual memory accounting (`vm.overcommit_memory = 2`) to avoid sudden OOM killer termination, bounded dirty page ratios to prevent checkpoint I/O stalls, and transparent hugepage madvise tuning.

## Decision

We introduce 4 specialized Cloud-Native and Storage appliance flavors:

1. **`cloudnative-generic`**: Hardened, immutable container host with read-only root systemd protections, volatile `/tmp` and `/var/tmp` tmpfs mounts, sealed package managers to prevent untracked updates, and Container Device Interface (CDI) support.
2. **`cloudnative-k8s`**: Immutable Kubernetes worker node pairing read-only root hardening with containerd 2.3.5 and kubelet 1.37.0 for zero-drift cluster operation.
3. **`cloudnative-storage`**: CNCF storage appliance with pre-configured NVMe-oF TCP module autoloading (`nvme-core`, `nvme-fabrics`, `nvme-tcp`), OpenZFS 2.3 (`zfsutils-linux`), `multipath-tools`, and `open-iscsi`.
4. **`cloudnative-pg`**: Production PostgreSQL and CloudNativePG host pre-tuned with strict memory overcommit ratios, bounded dirty page writeback, transparent hugepage madvise support, and elevated file descriptor limits.

All provisioners (`61-cloudnative-immutable.sh`, `65-storage-cncf.sh`, `70-cloudnative-pg.sh`) adhere strictly to NASA/JPL Power of 10 bash rules ($\le 60$ lines per function, `set -euo pipefail`).

## Consequences

- Expands the flavor matrix to 39 fully automated flavors.
- Delivers native support for immutable container architectures and CNCF distributed storage fabrics.
- Ensures zero memory overcommit crashes for high-throughput CloudNativePG workloads.
