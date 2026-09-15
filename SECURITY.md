# Security Policy

`imago` produces hardened, production-grade cloud and bare-metal OS images. Security is paramount across our image forge, provisioners, and supply chain.

## Supported Versions

Only the current rolling branch and the latest two minor tags receive security patches:

| Version | Supported |
| :--- | :--- |
| `main` (rolling weekly) | :white_check_mark: |
| Latest minor release (v0.x) | :white_check_mark: |
| Older releases | :x: |

## Reporting a Vulnerability

Please **do not report security vulnerabilities through public GitHub issues**.

Instead, please report vulnerabilities by opening a private GitHub Security Advisory:
- Navigate to the **Security** tab of this repository: [Report a vulnerability](https://github.com/cordanaLLM/imago/security/advisories/new).
- Click **Report a vulnerability**.
- Provide a detailed description of the vulnerability, affected flavors, and steps to reproduce.

All vulnerability disclosures are handled confidentially through GitHub Security Advisories.

### Response Timeline
- **Initial Acknowledgement**: Within 24 hours.
- **Triage & Reproduction**: Within 72 hours.
- **Fix & Disclosure**: Patches will be developed in private and released alongside a coordinated GitHub Security Advisory (GHSA) and CVE identifier if warranted.

## Supply Chain Integrity & Continuous Auditing

All official release artifacts (`.qcow2.zst`, `.raw.zst`, `.vmdk.zst`) are:
1. Cryptographically signed using **Cosign** (keyless OIDC with GitHub Actions).
2. Accompanied by **CycloneDX** and **SPDX** Software Bill of Materials (SBOM) generated via **Syft**.
3. Scanned for CVE vulnerabilities in CI via **Trivy**, static analysis via **Semgrep**, and supply-chain health via **OpenSSF Scorecard**.

For comprehensive audit reports, automated gate metrics, and zero-leak verification details, consult the [Security Policy & Audit Ledger](https://github.com/cordanaLLM/imago/blob/main/docs/community/security.md).

