# Operational Maintenance Cadences and Contributor SOPs

To guarantee long-term stability, automated dependency freshness, and zero-drift security across all 44 flavors, `imago` operates on four deterministic operational cadences: **Weekly**, **Monthly**, **Quarterly**, and **Annual**.

---

## 1. Cadence Matrix Overview

```text
+------------------------------------------------------------------------------------------+
|                             OPERATIONAL MAINTENANCE CADENCES                             |
+-----------+----------------------+-------------------------------------------------------+
| Cadence   | Schedule             | Primary Operational Responsibilities                  |
+-----------+----------------------+-------------------------------------------------------+
| Weekly    | Monday 03:00 UTC     | ISO checksum check, Renovate triage, runner hygiene   |
| Monthly   | First Tuesday        | Release cut, CVE reconciliation, NTS drift, Steam sync|
| Quarterly | Jan / Apr / Jul / Oct| GPU realignment, K8s rollover, CIS audit, STH survey  |
| Annual    | Q3 (August)          | LTS migration review, GPG/Cosign rotation, Top500 sync|
+-----------+----------------------+-------------------------------------------------------+
```

---

## 2. Weekly Cadence (Every Monday at 03:00 UTC)

The weekly cadence executes automatically via scheduled GitHub Actions workflows:

### 2.1 Automated Tasks

1. **Upstream ISO Checksum Validation**:
   - Fetches the current daily SHA256 checksums from `releases.ubuntu.com/noble/` and compares against `versions.json` (`distro.iso_checksum`).
   - If an upstream ISO respin is detected, an automated PR is opened to bump `versions.json`.
2. **Renovate Dependency PR Triage**:
   - Review and merge passing minor/patch updates for container images, CNI plugins, and Kubernetes patch revisions.
3. **CI Runner Cache Invalidation**:
   - Purges stale Packer QEMU build caches to prevent layer contamination.

---

## 3. Monthly Cadence (First Tuesday of Every Month)

The monthly cadence is overseen by release maintainers following standard SOPs:

### 3.1 Tasks & Procedures

1. **Release Milestone Cut**:
   - Review the release pull request that `release-please` keeps open against `main`. It
     carries the next `CHANGELOG.md` section, the `VERSION` file and the version constant in
     `cmd/imago/main.go`.
   - Merge it to publish. The next run of the `release-please` workflow tags the merge
     commit `vX.Y.Z` and creates the GitHub release. The first release is `v0.1.0`
     (`initial-version` in `release-please-config.json`), the version the milestone
     `0.1.0 — First release` names; `tests/test_governance.py` refuses any later version
     while that milestone is open. Later versions follow from the
     Conventional Commits merged since the last tag.
   - `release-please` opens that pull request with the workflow token, so the repository must
     allow GitHub Actions to create pull requests. `overrides.actions` in `.standards.yaml`
     declares that setting; when it is withdrawn, the online `praetorctl audit` fails with
     `Actions workflow permissions drifted` before a release run would.
2. **CVE Drift Reconciliation**:
   - Run Trivy and Grype against base image rootfs artifacts.
   - Any disclosed High/Critical vulnerabilities without upstream deb patches are flagged for mitigation or base package pinning.
3. **Stratum-1 NTS Drift & Latency Audit**:
   - Audit upstream NTS server reachability for European national laboratories (PTB, Netnod, SIDN, 3eck).
   - Verify handshake latency is within acceptable tolerance (< 50ms across European points of presence).
4. **Steam Hardware Survey Synchronization**:
   - Check monthly GPU adoption data on the Steam Hardware Survey.
   - Rebalance consumer GPU presets in `base-nvidia-mainstream` and `appliance-media-server`.

---

## 4. Quarterly Cadence (January, April, July, October)

Quarterly reviews address foundational runtime migrations and platform updates:

### 4.1 Tasks & Procedures

1. **NVIDIA Driver Branch Realignment**:
   - Evaluate NVIDIA New Feature Branch (NFB) and Production Branch (PB) releases.
   - Shift mainstream / modern / bleeding branch pointers in `versions.json` in accordance with upstream support lifecycles.
2. **Kubernetes Minor Version Window Rollover**:
   - Verify supported Kubernetes versions against the upstream N-2 support policy (e.g., v1.37, v1.36, v1.35).
   - Update CNI preheat images (Cilium, Calico, Flannel, kube-vip) to their respective validated patch releases.
3. **CIS Benchmark & BSI IT-Grundschutz Audit**:
   - Audit provisioner scripts against newly published CIS Ubuntu Server benchmarks.
   - Run OpenSCAP or custom compliance verification rules.
4. **r/homelab & ServeTheHome (STH) Survey Synchronization**:
   - Review secondary market hardware trends for decommissioned enterprise servers (Dell 14G/15G, HPE Gen10, Supermicro).
   - Adjust bare-metal kernel tuning and NIC driver defaults in `25-baremetal-tuning.sh`.

---

## 5. Annual Cadence (Every August)

Annual maintenance focuses on cryptographic identity hygiene and architectural roadmap alignment:

### 5.1 Tasks & Procedures

1. **Ubuntu LTS Migration Evaluation**:
   - Assess upcoming Ubuntu LTS release milestones and plan base distribution roadmap.
2. **Cryptographic Identity & Signing Key Rotation**:
   - Rotate repository GPG commit-signing keys and Cosign container signing keys in accordance with organizational security policies.
   - Update key fingerprints in documentation and security policy files.
3. **Top500 & Green500 Supercomputing Realignment**:
   - Survey the Top500 supercomputing rankings to validate datacenter AI accelerator profiles, Fabric Manager configurations, and NVLink interconnect topologies.

---

## 6. Immutable Image Deprecation & Fleet Lifecycle Policy

Following [ADR-0011](../adr/0011-enterprise-golden-image-compliance-and-lifecycle.md), production infrastructure deployed with `imago` operates on a strict **Zero-Patching Fleet Immutability** model:

1. **Strict 30-Day Image Lifespan**:
   - Published golden images enforce a 30-day active lifespan. Autoscaling node pools and hypervisor clusters are recycled continuously over newly forged baselines.
   - Older images are flagged with cloud deprecation markers (e.g. `aws ec2 enable-image-deprecation --image-id <ami-id> --deprecate-at <timestamp>`), hiding deprecated images from general provisioning while leaving existing running instances uninterrupted.
2. **Zero In-Place Host Patching**:
   - Live production nodes must never be patched in place via manual SSH, apt upgrades, or ad-hoc configuration scripts.
   - Security errata and package upgrades trigger a deterministic pipeline rebuild, producing an updated golden artifact deployed via automated rolling replacement.
