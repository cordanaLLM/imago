# 14. Automated Dependency & Security Governance via Zero-Noise Renovate and Native CodeQL

Date: 2026-09-10

## Status

Accepted

## Context

`imago` depends on upstream operating system bases, container runtimes (`containerd`, `crun`, `stargz-snapshotter`), Kubernetes versions and preheated container images, diagnostic binaries (`cdebug`, `enroot`), NVIDIA/AMD/Intel drivers and GPU device plugins, and Python/Go testing and build automation.

The repository enforces strict security and architectural invariants:

1. **Single Source of Truth (`versions.json`)**: All upstream versions, container image tags, and driver branches must originate exclusively from `versions.json`.
2. **GitHub Actions 40-Character Commit SHA Pinning**: All GitHub Actions must be pinned to immutable 40-character commit SHAs, as verified by `test_github_actions_pinned_to_sha` in `tests/test_security_privacy.py`. Unmanaged or default dependency bot updates that emit version tags (e.g., `@v4`) immediately break CI quality gates.
3. **Low-Churn Engineering Cadence**: Uncoordinated, continuous pull requests from dependency bots create reviewer fatigue, CI resource exhaustion, and merge conflicts.
4. **Release Stability Guard**: Zero-day library and container releases occasionally suffer from regressions, accidental yankings, or supply chain compromises that are rectified within days of publication.
5. **OpenSSF Scorecard & Static Analysis**: Automated workflows must enforce least-privilege token permissions (no top-level `write` scopes), and the codebase requires native GitHub CodeQL static analysis for Go and Python toolchains.

## Decision

We establish an automated, zero-noise dependency and security governance architecture across three pillars:

### 1. Zero-Noise Renovate Dependency Configuration (`renovate.json`)

We configure Renovate to eliminate broken PR churn and honor repository architectural constraints:

- **Action Digest Pinning (`helpers:pinGitHubActionDigests`)**: Renovate automatically resolves and pins new GitHub Action releases to their full 40-character immutable commit SHAs with an inline tag comment (e.g. `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2`). This prevents CI failures under `test_github_actions_pinned_to_sha`.
- **Weekly Batch Scheduling (`schedule: ["before 6am on monday"]`)**: Routine dependency updates are scheduled exclusively before 6:00 AM UTC on Mondays, batching reviews into a predictable weekly maintenance window.
- **Mandatory 3-Day Release Stability (`minimumReleaseAge: "3 days"`)**: Renovate withholds proposing new dependency releases until they have been published for at least 3 days, filtering out transient upstream breakages and emergency point releases.
- **Dependency Grouping (`packageRules`)**:
  - `github-actions`: Combines all workflow action updates into a single atomic pull request.
  - `python-tooling`: Groups test framework and linting tools (`pytest`, `ruff`, `mypy`).
  - `go-modules`: Groups Go SDK and runtime dependencies.
  - `container-images`: Batches container image updates defined in `versions.json`.
- **SSOT Custom Regex Managers**: Custom regex managers continuously monitor upstream GitHub releases and container registries, updating `versions.json` directly for `kubernetes`, `k3s`, `containerd`, `docker_ce`, `crun`, `stargz_snapshotter`, `cdebug`, `enroot`, and NVIDIA Container Toolkit.

### 2. OpenSSF Scorecard Least-Privilege Workflow Permissions

To satisfy OpenSSF Scorecard `TokenPermissionsID` invariants and eliminate Code Scanning alerts:

- All `.github/workflows/*.yml` workflows enforce `permissions: { contents: read }` at the top level.
- Elevated write permissions (`contents: write`, `packages: write`, `id-token: write`, `pull-requests: write`, `pages: write`) are strictly scoped to specific individual jobs that require them (`build-matrix`, `provenance`, `deploy`, `release-please`).
- Any workflow executing without explicit write requirements operates with read-only or empty tokens.

### 3. Native GitHub CodeQL Static Analysis (`.github/workflows/codeql.yml`)

We deploy GitHub CodeQL static analysis alongside existing SAST scanners (`semgrep`, `trivy`, `gitleaks`):

- **Analyzed Languages**: `go` (MCP server bridge, CLI utilities) and `python` (test suites, provisioning generators, tooling).
- **Execution Matrix**: Triggered on pushes to `main`, pull requests targeting `main`, and a scheduled weekly scan (`cron: "26 6 * * 1"`).
- **Query Suite**: Runs `+security-and-quality` queries to detect security vulnerabilities, resource leaks, and algorithmic flaws.
- **Least-Privilege Scoping**: Workflow executes with top-level `contents: read`, scoping `security-events: write` solely to the `analyze` job for SARIF upload.

## Consequences

### Positive

- **Zero-Friction Dependency Maintenance**: Dependency PRs arrive pre-pinned to commit SHAs, grouped, and tested, eliminating repetitive developer fixes.
- **Zero OpenSSF Scorecard Permission Alerts**: All workflow files adhere to least-privilege token specifications.
- **Continuous Deep SAST**: Go and Python code is continuously analyzed by GitHub CodeQL for security and code quality defects.
- **SSOT Integrity**: Updates to core runtimes and container images flow directly into `versions.json`.

### Negative

- **Minor Update Latency**: The 3-day release stability filter intentionally delays adoption of new upstream versions by 72 hours (critical security advisories can still be upgraded manually).
