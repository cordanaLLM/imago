# Repository-Rule Crosswalk

This ledger records which recurring engineering conventions from the maintainer's other fleet repositories (`VMAFx/vmafx`, `20-watts-was-enough`, `golusoris/*`) were adopted, adapted, staged, or rejected in `lusoris-cloud-images`. It prevents future maintainers and autonomous agents from copying tooling without verifying that its invariant applies to an OS image forge.

---

## 1. Reference Fleet Set

The comparative baseline is drawn from the established public repositories:

- [`VMAFx/vmafx`](https://github.com/VMAFx/vmafx) — GPU-accelerated video quality evaluation forge.
- [`20-watts-was-enough`](https://github.com/lusoris/20-watts-was-enough) — High-efficiency edge AI and compute research contract.
- [`golusoris/*`](https://github.com/golusoris) — Core infrastructure, Envoy extensions, and organization shared tooling.

The deduplicated local authority for this repository is [`docs/principles.md`](principles.md).

---

## 2. Repeated Fleet Pattern

Across the reference repositories, the stable architectural pattern is:

1. **One Root Engineering Contract**: A centralized, authoritative [`docs/principles.md`](principles.md) and [`AGENTS.md`](https://github.com/cordanaLLM/imago/blob/main/AGENTS.md).
2. **Narrow Set of Hard Automated Gates**: Zero-lint merge floors, strict static analysis, and cryptographic pinning.
3. **Explicit Governance & Community Surfaces**: Standard `CONTRIBUTING.md`, `SECURITY.md`, `GOVERNANCE.md`, `MAINTAINERS.md`, `CODE_OF_CONDUCT.md`, `SUPPORT.md`.
4. **Immutable Supply Chain**: All GitHub Actions references pinned to full 40-character commit hashes; SLSA provenance attestations.
5. **Conventional Change History**: Strict Conventional Commits driving automated Release Please semantic versioning.
6. **Domain-Specific Power of 10 Adaptation**: Holzmann's rules adapted to the repository's primary execution medium.
7. **Zero-Leak Invariant**: Total prohibition of private RFC 1918 addresses and developer workstation paths.

---

## 3. Adoption Matrix for `lusoris-cloud-images`

| Reference Convention | Local Decision | Concrete Surface |
| :--- | :--- | :--- |
| **Root Engineering Contract** | **Adopted** | [`docs/principles.md`](principles.md) & [`AGENTS.md`](https://github.com/cordanaLLM/imago/blob/main/AGENTS.md) |
| **NASA/JPL Power of 10** | **Adapted** for Shell & Packer | Functions $\le$ 60 lines, `set -euo pipefail`, bounded loops in `packer/provisioners/` |
| **Single Source of Truth (SSOT)** | **Adopted** | Declarative [`versions.json`](https://github.com/cordanaLLM/imago/blob/main/versions.json) driving Packer HCL and provisioner env vars |
| **Zero-Warning Merge Floor** | **Adopted** | `make lint` (Packer, ShellCheck, Yamllint, shfmt, Codespell) + `make test` |
| **Trunk-Based PR Merge Flow** | **Adopted** | Protected `main`, branch protection requiring `required-checks`, squash/rebase only |
| **Pinned GitHub Actions** | **Adopted** | All 26 actions in `.github/workflows/` pinned to 40-character commit SHAs |
| **Conventional Commits** | **Adopted** | `type(scope): subject` syntax enforced via PR titles and release automation |
| **Semantic Versioning (Release Please)** | **Adopted** | Automated releases, CHANGELOG generation, and release pull requests |
| **Append-Only ADRs** | **Adopted** | [`docs/adr/`](adr/README.md) following standardized format |
| **Material for MkDocs Portal** | **Adopted** | `mkdocs build --strict` deploying to GitHub Pages via [`pages.yml`](https://github.com/cordanaLLM/imago/blob/main/.github/workflows/pages.yml) |
| **Privacy & Zero-Leak Invariant** | **Adopted** | Strict prohibition on RFC 1918 IPs and `/home/*` paths (`test_no_private_ips_or_user_paths`) |
| **Supply-Chain & SAST Scans** | **Adopted** | OpenSSF Scorecard v2.4.4, Semgrep SAST, Trivy CVE filesystem scan, Gitleaks |
| **Worktree Discipline** | **Adopted** | Isolated branch/worktree execution under `.workingdir2/worktrees/`; never run parallel agents in main |
| **Working Sequence & Prose Bar** | **Adopted** | Standardized 7-step working sequence and technical information density in `AGENTS.md` |
| **Schema-Validated SSOT** | **Adopted** | Declarative `versions.schema.json` dynamically enforcing `versions.json` integrity |
| **Local Audit Ledger** | **Adopted** | `.workingdir2/AUDIT_RESULTS_2026-09-10.md` tracking merge train and audit evidence |
| **Interactive Question Style** | **Adopted** | Prefer structured popup questions on real forks; act on unambiguous work |
| **Go 1.27 Engineering Contract** | **Adopted** from `golusoris/*` | Functions $\le 60$ statements, small interfaces, `stdoutRedirect` JSON-RPC framing, `slog` to stderr |
| **Fine-Grained Path-Filtered CI** | **Adopted** | `dorny/paths-filter` splitting `packer`, `shell`, `go`, `python`, `docs`, `workflows` into conditional jobs |
| **Declarative Epics & Milestones** | **Adopted** | `.github/epics.json`, `.github/milestones.json`, and automated PR hard gate (`pr-project-gate.yml`) |
| **Universal Architecture & Survey** | **Adopted** | `x86_64`, `arm64` (RPi 5/Rockchip/Apple Silicon), `riscv64`, 2 Datacenter Tiers, and recurring sync cadences |

---

## 4. Host Controls Verified on GitHub

The following repository settings were verified via `gh api`:

- **Visibility & Metadata**: Public repository, description set, topics registered, homepage set to `https://cordanallm.github.io/imago`.
- **Merge Settings**: Squash and rebase merges allowed; merge commits disabled; delete branch on merge enabled.
- **Workflow Permissions**: `can_approve_pull_request_reviews: true` to enable Release Please automation.
- **Branch Protection on `main`**: Required status check `required-checks`; strict linear history; force-pushes and deletions blocked.
- **Project Tracking**: GitHub Project V2 [`lusoris-cloud-images Roadmap`](https://github.com/users/lusoris/projects/1) tracking active epics.
