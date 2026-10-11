# 11. Enterprise Golden Image Hardening, Compliance Crosswalk, and Lifecycle Governance

Date: 2026-09-10

## Status

Accepted

## Context

Modern cloud security engineering dictates that machine and container images must be engineered as immutable, cryptographically attested software artifacts rather than long-lived systems patched in place. Industry best practices—cataloged in the architectural standard *"Engineering Hardened, Optimized, and Compliant Cloud Infrastructure Images"*—prescribe end-to-end controls across the golden image factory lifecycle:

1. **Cryptographic SSH Hardening & Certificate Authorities (CA)**: Traditional static SSH key management incurs operational overhead, credential drift, and rotation debt. Moving to an OpenSSH Certificate Authority (`TrustedUserCAKeys`) with modern cryptographic cipher suites (`chacha20-poly1305`, `aes256-gcm`, `curve25519-sha256`) eliminates static authorized keys in favor of short-lived, identity-bound certificates while disabling root login and legacy MACs.
2. **Regulatory & Hardening Compliance Crosswalk**: While `lusoris-cloud-images` already implements CIS Ubuntu Benchmark Level 2 and BSI IT-Grundschutz SYS.1.3, enterprise adoption requires explicit compliance crosswalks to federal standards: **NIST SP 800-53 (Rev. 5)** (Least Privilege AC-6, Configuration Baseline CM-6, Flaw Remediation SI-2, Monitoring SI-4) and **NIST SP 800-190** (Application Container Security Guide).
3. **Multi-Cloud KMS Encryption & Auto Scaling Safety**: In multi-account public cloud architectures, sharing encrypted machine images requires Customer Managed Keys (CMKs). A frequent operational failure occurs when target Auto Scaling Groups attempt to launch instances using cross-account AMIs without explicit KMS grants assigned to `AWSServiceRoleForAutoScaling`. Establishing standard KMS grant patterns prevents scaling loop terminations.
4. **Automated 30-Day Image Deprecation & Zero-Patching**: Production cloud fleets must never be patched in place. Golden images must enforce a maximum 30-day lifecycle, utilizing automated cloud provider deprecation flags (`aws ec2 enable-image-deprecation`) to drive continuous node recycling over fresh baselines.
5. **Dynamic Compliance-as-Code Validation**: Static linting must be complemented by declarative, dynamic compliance validation (such as Goss or InSpec) asserting kernel parameters, filesystem blacklists, and daemon configurations prior to snapshot finalization.

## Decision

We formalize an enterprise compliance and multi-cloud lifecycle contract for `lusoris-cloud-images`:

### 1. OpenSSH Hardening Drop-in (`00-hardened-sshd.conf`)

- In `00-base-strip.sh`, deploy a hardened configuration drop-in at `/etc/ssh/sshd_config.d/00-hardened-sshd.conf` with permissions `0600`:
  - **Cipher Selection**: `chacha20-poly1305@openssh.com`, `aes256-gcm@openssh.com`, `aes128-gcm@openssh.com`.
  - **Key Exchange**: `curve25519-sha256`, `curve25519-sha256@libssh.org`, `diffie-hellman-group16-sha512`, `diffie-hellman-group18-sha512`.
  - **Message Authentication Codes**: `hmac-sha2-512-etm@openssh.com`, `hmac-sha2-256-etm@openssh.com`.
  - **Access Controls**: `PermitRootLogin no`, `MaxAuthTries 3`, `MaxSessions 2`, `ClientAliveInterval 300`, `ClientAliveCountMax 0`, `X11Forwarding no`.
  - **Certificate Authority Integration**: Configured with `TrustedUserCAKeys /etc/ssh/trusted-user-ca-keys.pub` to support enterprise ephemeral signed certificates.
  - **Build-Time Communicator Protection**: Temporary build credentials remain active during Packer execution; in `99-cleanup.sh`, `PasswordAuthentication no` is enforced upon snapshot sealing.

### 2. NIST SP 800-53 (Rev. 5) & NIST SP 800-190 Compliance Mappings

- Codify explicit mappings across all 44 flavors:
  - **AC-6 (Least Privilege)**: Stripping setuid/setgid bits from non-essential utilities, setting low-level binary permissions (`chmod 0700 /usr/bin/as /usr/bin/byacc`), unprivileged container execution (UID >= 10001).
  - **CM-6 (Configuration Settings)**: Complete declarative version locking via `versions.json` Single Source of Truth.
  - **SI-2 (Flaw Remediation)**: Zero in-place patching; weekly automated rebuilds incorporating upstream security errata.
  - **SI-4 (Information System Monitoring)**: Pre-baked system telemetry and auditd buffer scaling (`-b 8192 -f 1`).
  - **NIST SP 800-190**: Elimination of package managers/shells in minimal container layers, seccomp profile enforcement, and read-only rootfilesystems.

### 3. Multi-Cloud Lifecycle & KMS Governance

- Standardize cross-account KMS grant procedures for AWS Auto Scaling Service-Linked Roles (`AWSServiceRoleForAutoScaling`).
- Standardize Azure Compute Gallery (ACG) and GCP Shared VPC image project RBAC/IAM configurations.
- Enforce a 30-day image deprecation cadence across public cloud catalogs.

### 4. Declarative Dynamic Compliance Specification (`tests/compliance/goss.yaml`)

- Provide a standalone, zero-dependency Goss specification to evaluate booted image instances against kernel sysctl, filesystem blacklist, and SSH security baselines.

## Consequences

### Positive

- **Federal & Enterprise Audit Readiness**: Aligns `lusoris-cloud-images` with DISA STIG, NIST SP 800-53, and NIST SP 800-190 standards alongside CIS Benchmark Level 2.
- **Elimination of Static SSH Keys**: Enables enterprise fleets to transition to ephemeral, identity-backed OpenSSH user certificates.
- **Zero-Patching Fleet Immutability**: Guarantees production nodes run on fresh, uncorrupted base layers without configuration drift.
- **Operational Safety**: Avoids the top production pitfalls (broken package managers from `/tmp` noexec, auditd buffer panics, and cross-account KMS launch failures).

### Negative / Neutral

- Hardened SSH cipher suites require automation clients to support modern cryptography (`curve25519-sha256`, `chacha20-poly1305`).
- Deployments utilizing password authentication must transition to SSH public keys or CA certificates upon snapshot finalization.
