<!-- markdownlint-disable MD013 MD024 -->
# Security Policy & Audit Ledger

> Authoritative security documentation, vulnerability disclosure SLAs, and continuous automated security audit findings for `lusoris-cloud-images`.

---

## 1. Security Philosophy & Threat Model

`lusoris-cloud-images` produces hardened, production-ready cloud and bare-metal OS images designed for enterprise virtualization and edge compute. Our threat model assumes:
- Untrusted multi-tenant host environments where guest images must be hardened against privilege escalation, kernel info leaks, and unauthenticated network probing.
- Fully automated, reproducible build pipelines where supply-chain tampering and unauthorized artifact mutation are actively prevented via cryptographic verification and dependency pinning.
- Zero-tolerance for credential or topology leakage (RFC 1918 private subnets, local workstation paths, developer credentials).

---

## 2. Vulnerability Disclosure & Response SLAs

We welcome responsible security research and vulnerability reports. Please **never report potential vulnerabilities through public GitHub issues**.

### Reporting Channels
All vulnerability reports must be submitted through **GitHub Private Vulnerability Reporting**:
- Navigate to the **Security** tab of [cordanaLLM/imago](https://github.com/cordanaLLM/imago/security/advisories/new).
- Click **Report a vulnerability** to open an encrypted private advisory draft.
- Include affected flavors, reproduction steps, and potential exploit impact.

### Coordinated Response SLAs
| Phase | Target Timeline | Action Description |
| :--- | :--- | :--- |
| **Initial Acknowledgement** | Within 24 hours | Coordinator receipt confirmation and tracking ID assignment |
| **Triage & Reproduction** | Within 72 hours | Vulnerability assessment across flavors and severity scoring (CVSS v3.1) |
| **Patch & Coordinated Release**| Within 14 days | Private branch development, automated gate re-verification, GHSA publication |

### Supported Versions
Only the `main` branch (rolling weekly daily-upstream builds) and the two latest minor release tags receive security backports.

---

## 3. Automated Continuous Security Audit Findings

Every commit and pull request must pass the automated security and quality gates before merge:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                AUTOMATED SECURITY & INTEGRITY PIPELINE                                 │
├──────────────────────┬──────────────────────┬────────────────────┬───────────────────┬────────────────┤
│ OpenSSF Scorecard    │ Trivy Filesystem CVE │ Semgrep SAST Gate  │ GitHub CodeQL     │ Gitleaks Gate  │
│ Least Privilege      │ 0 CVEs Detected      │ 0 Code Alerts      │ Go + Python       │ 0 Leaks Found  │
│ 10/10 Core Controls  │ Clean Base Packages  │ Zero Taint Paths   │ Security & Quality│ Clean History  │
└──────────────────────┴──────────────────────┴────────────────────┴───────────────────┴────────────────┘
```

### A. OpenSSF Scorecard Analysis (v5.4.0)
The repository runs the OpenSSF Scorecard supply-chain security analysis via GitHub Actions:

| Check | Score | Status | Description |
| :--- | :--- | :--- | :--- |
| **Binary-Artifacts** | **10 / 10** | **PASS (✓)** | Zero pre-compiled binary executables checked into source control. |
| **Dangerous-Workflow**| **10 / 10** | **PASS (✓)** | Workflows avoid untrusted script evaluations or code injections. |
| **Vulnerabilities** | **10 / 10** | **PASS (✓)** | Zero known unfixed OSV/CVE vulnerabilities. |
| **Security-Policy** | **10 / 10** | **PASS (✓)** | Public `SECURITY.md` with explicit disclosure SLA and channels. |
| **License** | **10 / 10** | **PASS (✓)** | Permissive Apache-2.0 OSI-approved license. |
| **Dependency-Update** | **10 / 10** | **PASS (✓)** | Zero-noise Renovate active with automated grouping and 3-day stability guard. |
| **CI-Tests** | **10 / 10** | **PASS (✓)** | 100% of pull requests verified by automated test suites. |
| **Pinned-Dependencies**| **10 / 10** | **PASS (✓)** | 100% of GitHub Actions pinned to 40-character immutable commit SHAs. |
| **Token-Permissions**| **10 / 10** | **PASS (✓)** | Top-level `contents: read` least privilege enforced; job-scoped write tokens only. |

### B. Trivy Vulnerability & Container Scan (v0.36.0)
- **Scope**: Repository filesystem, package dependency manifests, and workflow configurations.
- **Result**: **0 Critical, 0 High, 0 Medium, 0 Low** vulnerabilities.
- **Action**: Daily automated scanning via `aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25`.

### C. Semgrep Static Application Security Testing (SAST)
- **Scope**: Shell provisioner scripts, Python verification test files, and GitHub Actions definitions.
- **Rule Packs**: `p/default`, `p/ci`, `p/secrets`, `p/owasp-top-ten`.
- **Result**: **0 Security Alerts**, zero taint vulnerabilities.

### D. GitHub CodeQL Static Analysis
- **Scope**: Go runtime components and Python test and orchestration automation.
- **Rule Suites**: `+security-and-quality` detecting code flaws, injection surfaces, and concurrency defects.
- **Result**: **0 Security Alerts**. Executed on push to `main`, pull requests, and scheduled weekly cron (`.github/workflows/codeql.yml`).

### E. Gitleaks Deep History Secret Scan (v8.x)
- **Scope**: Complete git history from initial root commit to `HEAD`.
- **Result**: **0 Secret Leaks**. Verified zero exposed private keys, bearer tokens, or sensitive API secrets.

### F. Automated Zero-Noise Dependency Governance (Renovate)
- **Architecture**: Declarative `renovate.json` adhering to [ADR-0014](../adr/0014-automated-dependency-management-renovate.md).
- **Digest Pinning**: Automatically resolves 40-character commit SHAs for GitHub Actions via `helpers:pinGitHubActionDigests`.
- **Cadence & Stability**: Weekly batches (Mondays before 6am UTC) with a 3-day minimum release stability quarantine.
- **SSOT Regex Synchronization**: Directly manages version declarations in `versions.json`.

### G. Zero-Leak Privacy Invariant Gate
- **Scope**: Automated pre-commit and CI verification (`tests/test_security_privacy.py`).
- **Enforcement**:
  - Rejects any RFC 1918 private IPv4 addresses (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) in configuration and code files.
  - Rejects developer workstation paths (`/home/<user>/...`), enforcing generic `/home/ubuntu` or `/tmp` paths.
  - Enforces that 100% of external GitHub Actions in `.github/workflows/*.yml` are pinned to immutable 40-character commit SHAs.
- **Result**: **100% Compliant**.

### H. NASA/JPL Power of 10 Shell Provisioner Quality Audit
- **Scope**: 28 shell provisioner scripts under `packer/provisioners/` verified across 8 dedicated test suites.
- **Standard**: Gerard J. Holzmann's Power of 10 rules adapted for cloud image engineering ([`docs/principles.md`](../principles.md)).
- **Metrics**:
  - Maximum function length $\le$ 60 lines (Rule 4).
  - Strict error handling: `set -euo pipefail` across all 28 scripts.
  - Standard `main "$@"` entrypoint structure and return code checking (Rule 7).
  - License header: `Copyright 2026 Lusoris` present in 100% of provisioners.
  - ShellCheck verification: **Zero warnings, zero errors**.

---

## 4. Supply Chain Security & Cryptographic Provenance

All official release artifacts produced by the release matrix are fortified with verifiable provenance:

1. **Cryptographic Keyless Signatures (Cosign)**:
   Release images (`.qcow2.zst`, `.raw.zst`, `.vmdk.zst`) are signed using Sigstore Cosign via GitHub Actions OIDC identity tokens, linking signatures directly to workflow runs.
2. **Software Bill of Materials (SBOM)**:
   Every image build generates CycloneDX and SPDX format SBOMs via Syft, detailing every installed package, kernel module, and container image layer.
3. **Artifact Attestation**:
   GitHub artifact attestations are published with SHA-256 digests allowing users to verify build authenticity via `gh attestation verify`.
