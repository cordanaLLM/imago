# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Raw disk image per released flavor: `release-matrix.yml` converts each built qcow2 to raw with `qemu-img convert -O raw`, compresses it with zstd and ships `lusoris-cloud-<flavor>.raw.zst` beside the `.qcow2.zst`, listed in the signed `SHA256SUMS`, so `lusoris-install-to-disk` can flash a released image. `tools/ci/release_assets.py sizes` writes a size table to the job summary and fails the build when an asset reaches the forge limit of 2 GiB per asset or a release would exceed 1000 assets; a manual run keeps the raw image of each flavor as a one-day artifact for inspection.
- Flash test of `lusoris-install-to-disk` (`tests/test_install_to_disk.py`): the helper is taken from the heredoc in `packer/provisioners/25-baremetal-tuning.sh` and flashes zstd-compressed disk images from a file and over HTTP onto a loop device, which must then match the image byte for byte. A target that is no block device, a wrong argument count, a truncated stream, an HTTP 404, an image larger than the device and an image without a partition table must fail; an image of exactly the device size and an MBR-only image must pass. CI runs it with passwordless sudo; without it the test skips locally and fails under `IMAGO_REQUIRE_LIVE_TESTS=1`.
- Golden transcripts for the human-readable CLI output (`cmd/imago/golden_test.go`): `--help`, `flavors list`, `standards list`, and `epics list` and `milestones list` against fixtures with one row that fits and one that overflows every column, compared byte for byte with `cmd/imago/testdata/golden/*.txt`. `go test ./cmd/imago -run TestGoldenTranscripts -update` rewrites them after an intended change; a second test refuses a transcript with a control character other than a newline, invalid UTF-8 or no final newline, so a rewrite cannot bless NUL output, and a third refuses a transcript without a case.
- Tests that run the built `imago` program (`cmd/imago/binary_test.go`): `--help`, `flavors list --json` parsed as one JSON document, an unknown command that must exit 1 with the message on stderr and nothing on stdout, `imago mcp --transport` with an unknown value that must fail before writing to the protocol stream, and `imago mcp` spoken to over stdin and stdout by an MCP client, which checks the server name, the 14 tools and one tool call. A line printed to stdout before the server starts breaks the handshake and fails the test.
- Action pin check: the `action-pins` workflow runs `tools/ci/action_pins.py`, which runs zizmor 1.30.1 (pinned with hashes in `.github/requirements/pins.txt`) online and fails on an action not pinned to a commit (`unpinned-uses`), a commit outside the action's repository (`impostor-commit`) or a version comment naming another release (`ref-version-mismatch`). It loads no zizmor configuration, honours no ignore comments, refuses to run without a token or offline, and fails unless each audit reports a planted workflow first. It runs on workflow changes, weekly and by hand.
- Boot smoke test for every released flavor: the `Boot the Image Once` step of `release-matrix.yml` runs `tools/ci/boot_smoke.py`, which boots the built image from a throw-away overlay with a NoCloud seed and fails the job unless cloud-init writes this run's nonce to the serial console before the deadline. `tests/test_boot_smoke.py` covers the pass, echoed-seed, foreign-nonce, silent, early-exit and invalid-input cases against a stub QEMU; `docs/tools/boot-smoke.md` describes it.
- Regression tests for the build fixes of #39 to #44: `tests/test_regression_guards.py` runs the shutdown command with stubbed `sudo`, `rm`, `passwd` and `shutdown` and checks the seal order and that a failed seal never powers off; checks that no provisioner seals the account early; runs `55-k8s-precache.sh` in the mock sandbox with one image failing to pull per profile and plugin; compares every precache fallback pin with the `versions.json` value the build passes; runs `packer validate` with a valid and an invalid accelerator; and reads `release-matrix.yml` for the emulated accelerator, the flavor output directory and an ISO authoring tool installed before Packer. Each test fails against the files from before its fix. The `ctr` mock in `tests/harness/mock_runner.py` replaces the host's `ctr` and fails one pull named by `MOCK_FAIL_IMAGE`.
- Hook refusal proof (issue #80): `make prove-hooks` runs `tools/ci/prove_hooks.py`, which clones the committed tree into a temporary directory, installs the hooks of `lefthook.yml` and shows that `compile-context --verify` and the offline audit pass, that a commit with a hand edit to `CLAUDE.md` is refused, and that a commit adding a banned `eval` call to a touched file is refused as HISS-08 with `.standards-baseline.json` unchanged. A refusal counts only when the commit fails, HEAD stays put and the output names the reason. `tests/test_prove_hooks.py` covers each failure mode with scripted replies, since CI does not install the engine.
- Aegis product-result emitter (ADR-0024): `aegis.Emit` and `imago aegis result emit` compute the SHA-256 of a built image under a bounded read, require that the given `SHA256SUMS` lists it, and write `imago.p01.product-result.v1` for an accepted request; `imago aegis result validate <path> [--json]` decodes a result with the decoder of the request; the fuzz target `FuzzParseResult` holds the form for every accepted input. **Breaking:** `Result.Validate` now admits one form for `signature-ref`, an `https://` URL of a keyless cosign bundle named `SHA256SUMS.bundle` (no port, query, fragment or percent-encoding); any other locator is refused. The emitter does not sign and no executor builds the image yet, so issue #46 stays open.
- Ruff gate for every Python file: `make lint` and the new `Ruff Lint & Format` job of `ci.yml` run `ruff check .` and `ruff format --check .`; `ruff` is pinned with hashes in `.github/requirements/lint.txt`. Four files written by `praetorctl adopt` are exempt by name in `ruff.toml`, each line naming `cordanaLLM/praetor#1204` and the end date 2027-01-09; `tests/test_python_lint_gate.py` fails when a line lacks that note, when the date has passed, when a listed rule no longer reports and when the formatter accepts an excluded file.
- REUSE licence gate: the `REUSE lint` workflow (`.github/workflows/reuse.yml`) and the `reuse-lint` pre-commit job run `reuse lint`; the engine audit checks the order of the `REUSE.toml` annotations and that `LICENSE` holds the declared licence text. `.github/rulesets/main.json` declares `REUSE lint` as the tenth required check. `CONTRIBUTING.md` says how a third-party file is annotated.
- Go native fuzz targets for the three strict JSON parsers: `FuzzParse` in `pkg/aegis`, `FuzzParseRequirement` and `FuzzParseArtifactManifest` in `pkg/kernel`. Each asserts that a rejection returns no value and that an accepted document validates and survives an encode and parse round trip; `FuzzParse` also holds the typed error and the bounded correlation id. The seed corpora run in every `go test`, and `make fuzz` fuzzes each target for `FUZZTIME` (default 30s).
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

- Workflow audit gate: the action pin check (`tools/ci/action_pins.py`) also fails on `template-injection`, `excessive-permissions`, `undocumented-permissions` and `anonymous-definition`, each refused on its planted workflow first. Every workflow passes them: the Packer build reads the flavor through `env`, Scorecard grants nothing at workflow level, every grant beyond `contents: read` says in a comment what it is for, and the Pages and release-please jobs carry a name.
- Concurrency groups on the PR gate, REUSE, required-aggregator, Scorecard and both release workflows; the release workflows never cancel a running release.

### Changed
- The live container tests (`tests/test_container_integration.py`) run on the Ubuntu release the images ship, `ubuntu:` plus the `distro.version` of `versions.json` (26.04), instead of `ubuntu:24.04`, so `sshd -t`, the sysctl syntax check and the CDI validation read the configuration with the OpenSSH and tools of the target release. A test fails when the image differs from `versions.json` or when any test names an image literal of its own.
- The Gitleaks and Semgrep jobs run `tools/ci/scanner_canary.py` before their scan: it scans planted findings outside the checkout and fails the job unless the scanner exits non-zero and reports each planted rule, including the custom `no-cosign-private-key` rule. The privacy tests now prove their patterns with planted leaks and pass documentation placeholders and near misses.
- The Praetor engine pin moves from `6622361940dc` to `3bbde0734` (`PRAETOR_REF` in
  `.github/workflows/ci.yml`). The new engine's audit fails when a linter the profile or a
  facet declares runs in no CI workflow; all nine declared linters already run, so the
  re-adoption wrote no exception and changed no other file.
- The Praetor engine pin moves from `4ae6247c` to `6622361940dc` (`PRAETOR_REF` in
  `.github/workflows/ci.yml`). The new engine's audit refused the earlier texts of
  `tools/markdownlint/verify.mjs`, `tools/markdownlint/no-private-scratch-links.mjs` and
  `tools/figures/checks.mjs`, and `praetorctl adopt` refreshed them together with
  `.config/agent/hooks/block_evasion.py`; no other adopted file changes. The refreshed
  interceptor chains its exception, so its `ruff.toml` lint line lists no rule (it was
  `B904`); the file stays excluded from the formatter until the same end date.
- Open work is recorded on the forge only (ADR-0025): the planning graph under `planning/` is frozen as the record of the migration, its three open steps are carried by issues #80, #81 and #46, and `planning/routing.json` marks the two archetype steps done. `.github/milestones.json` is copied from the forge again and gains the milestone "Post-1.0 roadmap". `AGENTS.md` no longer lists `imago plan route --ready` in the working sequence; the command itself is unchanged.
- Python sources under `tests/`, `scripts/` and `.agents/` follow the Ruff rule set and formatter: sorted imports, built-in generic annotations, an explicit `check=` on every `subprocess.run`. `get_tool_definitions` in `scripts/hindsight_mcp_server.py` builds its five definitions through `tool_definition` and returns the same list as before. `ci.yml` also runs when a draft pull request is marked ready for review.
- `scripts/tunnel_hindsight.py` starts `kubectl port-forward` at most 7200 times and then stops with exit status 1. It restarted without a bound before.
- The licence changes from Apache-2.0 to the European Union Public Licence 1.2 (`EUPL-1.2`) for every revision after commit `44a6bfa` and for every release (ADR-0023). Every revision up to and including `44a6bfa` stays available under Apache-2.0; no release was tagged under it. `LICENSE` holds the EUPL-1.2 text, `REUSE.toml` and `LICENSES/` carry the per-file licence information, the ten source headers that named Apache-2.0 carry an SPDX identifier, and the README has a License section.

- `.github/milestones.json` follows the milestones on the forge. It listed three monthly
  milestones (`v2026.04.0` to `v2026.06.0`) that never existed there; it now copies the four
  forge milestones with title, state, due date and description. The file therefore carries
  closed milestones and one without a due date, and `imago milestones list` and the
  `get_milestones` MCP tool are described as listing milestones with their state.
- Every workflow installs its Python tools from a hash lock with
  `pip install --require-hashes`. The inputs and the locks compiled from them with
  `uv pip compile --generate-hashes --universal` live under `.github/requirements/`
  (`docs`, `lint`, `sast`, `test`), and Renovate updates the locks through its
  `pip-compile` manager. `requirements-test.txt` moved to `.github/requirements/test.in`.
  `mkdocs-minify-plugin` is no longer installed; `mkdocs.yml` enables no plugin.
- The repository is re-adopted on the current Praetor engine (ADR-0022). The agent context is
  compiled into six vendor projections from `AGENTS.md`, the hooks run the offline audit
  before a commit and the full audit and gate before a push, and the declared branch
  rule set for `main` requires signed commits and nine status checks.
- A documentation gate is part of `make verify-all` and of CI (`Documentation Governance`):
  `make docs-lint` checks every tracked Markdown file with the pinned markdownlint
  configuration, and `make docs-figures` checks the rendered figures. The existing
  Markdown files were brought into line with it.
- The managed-agent manifests moved from `.agents/agents/` to `.agents/managed-agents/`;
  `.agents/agents/` now holds only the agent definitions the engine projects for each
  coding tool.
- The privacy tests scan the files git tracks or would add, instead of every file in the
  working tree. Ignored files (coverage data, build caches, local state) hold workstation
  paths by design and are never published.
- `.standards.yaml` declares one dated exception: `release-matrix.yml` publishes images
  without a cosign signature, an SBOM or build provenance (HISS-11). The exception names
  the file, the rule and the reason, and expires on 2027-01-09.
- CI runs `go vet ./...` before the Go unit tests.
- The pinned key for gate receipts is the one `cordanaLLM/praetor` pins and the signing
  workstation holds. It replaces the key generated on another workstation during the
  migration. The receipt file is no longer tracked, because every gate run rewrites it.
- The release tool releases the package as `imago` and starts at 0.1.0. No version was
  ever tagged or published, so the release manifest is empty and `initial-version`
  states the first one. Version 1.0.0 waits until the milestone `1.0 — First release` is
  closed; a governance test refuses `initial-version`, the manifest entry or `VERSION`
  from 1.0.0 up while it is open. The release pull request moves to a branch named after the new
  package.
- Every workflow action that ran on the Node 20 runtime is pinned to its current release,
  which runs on Node 24: `checkout` v7.0.1, `setup-go` v7.0.0, `setup-python` v7.0.0,
  `upload-artifact` v7.0.2, `deploy-pages` v5.0.1, the four `codeql-action` steps v4.38.3,
  `paths-filter` v4.0.3, `setup-packer` v3.4.0, `sbom-action/download-syft` v0.24.3,
  `release-please-action` v5.0.0, `create-pull-request` v8.1.1, `repository-dispatch`
  v4.0.1 and `action-gh-release` v3.0.3. Each pin is the commit of its tag.
  `cosign-installer` stays at v3.8.1: it has no Node runtime, and v4 installs cosign 3
  by default.
- The Praetor engine is pinned: `PRAETOR_REF` in `.github/workflows/ci.yml` names the engine
  commit, and the Git hooks and `make verify-all`, `make compile-context` and `make audit`
  run that commit through `.config/lefthook/engine.sh` instead of the `praetorctl` on `PATH`.
  The `Makefile` includes `.config/praetor/engine.mk` and calls `$(PRAETORCTL)`. A pin that
  cannot be installed fails the hook and the target; nothing falls back to `PATH`.
- Every workflow job names its runner: all 22 jobs that ran on `ubuntu-latest` now run on
  `ubuntu-26.04`, the system that label moves to from 2026-10-19. The next system release
  needs a commit here instead of arriving with the label.
- **Breaking**: `sync-kernel-manifest.yml` refuses a `kernel_release_published` payload without `stream`, `version`, and `tag` (the default-version fallback is removed), downloads the nucleus release, verifies the keyless cosign bundle over `SHA256SUMS`, runs `imago kernel artifact verify` against the payload and the `versions.json` contract pin, and only then proposes the `kernel.streams.<stream>` pin (version, `artifact_digest`, provenance) as a pull request that adds only `versions.json`.
- `dispatch-kernel-requirements.yml` validates `kernel/requirement.json` and dispatches its path, `sha256`, and commit to the provider named in `versions.json` instead of the unread drivers/runtimes/kubernetes triple; it triggers on changes to the requirement file.
- `docs/operations/sister-repo-kernel-forge-blueprint.md` section 4 documents the pinned contract: payload shape, manifest schema and bounds, and the verification order (cosign bundle, `SHA256SUMS` digest, per-artifact digests, `versions.json` pin).
- The repository has one private state folder, `.workingdir/`, the one the Praetor engine
  reads. The second folder is retired: its ignore rules and its scanner exclusions are
  removed, and the Hindsight local buffer moves to `.workingdir/memory/`.
- Linked worktrees live outside the checkout, in the workstation's central `worktrees/`
  folder, named `imago-<topic>`. `scripts/orchestrate_fanout.py` creates its agent
  worktrees there as `imago-agent-<role>`; `IMAGO_WORKTREES_DIR` names another folder.

### Removed

- The `[tool.codespell]` block in `pyproject.toml`. codespell reads `.codespellrc` after
  `pyproject.toml`, and both set the same two keys, so the block had no effect: a typo
  planted in a path only the block skipped was still reported. `.codespellrc` stays the one
  spell-check configuration.
- Generated files of agent clients and editors the project does not use. `.standards.yaml`
  now selects `agent_clients: [claude, codex, gemini]` and
  `editors: [universal, vscode, antigravity]`, so the engine compiles and verifies those
  only. Removed: the Cursor, Windsurf and Copilot context files and the two Copilot
  persona files, and the Neovim, Zed, Helix, Emacs, Fleet, Sublime Text and Visual Studio
  files (`.nvim.lua`, `lua/standards.lua`, `.zed/`, `.helix/`, `.dir-locals.el`, `.fleet/`,
  `standards.sublime-project`, `.clang-tidy`). `AGENTS.md` stays the one source every
  remaining client file is compiled from.

### Fixed

- `docs/platforms/baremetal.md` downloaded images from `releases.lusoris.org`, a host that serves none, and flashed a qcow2 file the helper cannot write. The guide now downloads the raw image, `SHA256SUMS` and its bundle from the forge release of the reader's own fork, verifies them with the release workflow's certificate identity, and names only `boot.example.com` as a placeholder netboot host.
- The `Actionlint & Yamllint` job of `ci.yml` ran the actionlint install script from the main branch of its repository, so two runs of one commit could lint with different code. It now downloads release 1.7.12 and checks it against a SHA-256 written in the workflow; `tests/test_action_pins.py` requires every download in a workflow to name a release, to match a checksum and never to be piped into a shell.
- `lusoris-install-to-disk` reported "Ready to boot." after writing any stream, a `.qcow2.zst` included, which leaves a disk without a partition table. It now reads the first sector after the write and fails unless it carries the `0x55 0xAA` boot signature.
- The kernel pin pull request that `sync-kernel-manifest.yml` opens now passes `pr-project-gate.yml` and carries a signed commit. It takes the lowest-numbered open milestone, the labels `kind/chore` and `area/fleet-contract` and a reference to issue #34, and `create-pull-request` commits through the forge API (`sign-commits`). Its first pull request had none of these and was refused. `tests/test_kernel_sync_pr.py` runs the gate against the proposed pull request and the milestone step against a stubbed `gh`.
- The MCP server refuses input outside each tool's range instead of acting on it. `inspect_compliance` and `validate_manifest` read only repository-relative paths, so an absolute path such as `/etc/passwd` or a path leaving the repository is an error; before, both read any file the server could open. `trigger_build` refuses an unknown flavor or backend before a dry run or staging, through the new `builder.Validate` that `Dispatch` also calls; before, a dry run reported success for an unknown backend and an invalid flavor was staged for confirmation. `list_flavors` reports an unknown tier as an error naming the known tiers instead of returning `null`. `pkg/mcp/boundary_test.go` adds positive, negative and boundary cases for every registered tool, including the confirm and discard paths of a staged action.
- Releases are now signed and carry SBOMs: each flavor build of `release-matrix.yml` mounts the built image read-only through `qemu-nbd`, catalogues its root file system with Syft into `sbom-<flavor>.cdx.json` and `sbom-<flavor>.spdx.json`, and fails when either lists fewer than 100 Debian packages; a new `sign` job merges the per-flavor checksums into one `SHA256SUMS`, signs it keylessly into `SHA256SUMS.bundle`, verifies the bundle and uploads both. Before, every flavor uploaded its own `SHA256SUMS` to the same release, `supply-chain.yml` signed nothing (one `echo` step, now removed), and the README's Scorecard badge pointed at that workflow. `tools/ci/release_assets.py` holds the attach, detach, check and merge steps; `tests/test_release_assets.py` covers them and fails when the sign step is removed.
- The QEMU builder's shutdown command now powers off only after the build account is sealed: `rm`, `passwd -l` and `shutdown` are chained with `&&` in `packer/sources.pkr.hcl`, so a seal that fails leaves the machine running and the build times out instead of shipping an image whose build password still works. Before, the steps were separated by `;`, so the machine powered off even when the seal failed.
- Codespell now runs on every pull request in its own `Codespell` job of `ci.yml`. It used to be a step of the workflow-gated `Actionlint & Yamllint` job, which a pull request changing only Go files skipped, so the planted misspelling in `cmd/imago/gates_test.go` reached main and turned it red. That line now carries an inline `codespell:ignore statuss`, and `tests/test_required_aggregator.py` refuses a codespell job that a condition or the change detector can skip.
- `imago cloud-init generate`, `cloud-init metadata`, the MCP tool `generate_cloudinit` and `imago boot` no longer pass caller input into YAML or a shell command unchecked: host name, user, platform, flavor, timezone, SSH keys and packages pass allow-lists and are written as quoted YAML scalars, and the boot command refuses relative paths and control characters and quotes each path as one shell word. A host name with a newline could add a `runcmd` key that cloud-init runs as root. The `epics list`, `milestones list` and `standards list` tables print a dashed separator instead of NUL bytes. New tests parse the output with a YAML reader and run the boot command through `sh`; a mutation run caught 21 of 21 mutants.
- `imago lint` now refuses tracking catalogs it used to accept: `.github/epics.json` and `.github/milestones.json` are decoded strictly (unknown keys, trailing data and a missing list fail), every epic needs an id and a title, and every milestone needs a title and the state `open` or `closed`. `imago lint` and `imago audit` write through the command's output writer, and `imago audit` returns at its deadline even when a child of the audit script holds the output open. `cmd/imago/gates_test.go` covers `lint`, `audit`, `plan validate` and `plan route` with planted defects and boundaries.
- `pr-project-gate.yml` now re-runs when a pull request is reopened or its milestone is set or removed (`reopened`, `milestoned`, `demilestoned`); before, removing the milestone left the last green result in place. `tests/test_pr_project_gate.py` runs the gate's step script with planted metadata: a missing milestone, reference or `tier/*`/`area/*` label each fail with their own error, near misses such as `ref#6` or a `subarea/*` label fail, and cross-repository, epic and title-only references pass.
- Go dependencies are now checked for known vulnerabilities in CI: the `Govulncheck Reachable Go Vulnerabilities` job of `security-scans.yml` runs govulncheck, pinned in its own module `tools/govulncheck/go.mod`, on every Go change, every push to `main` and the weekly schedule. It fails on a reachable vulnerability and when the scan cannot run; before, govulncheck ran only in the local pre-push hook and was skipped when not installed. `tests/test_security_scans.py` refuses planted steps that would pass with findings (`-json`, `-format sarif`, `|| true`, a skip when the tool is missing, an unpinned `@latest`).
- The `Trivy Filesystem CVE Scan` job of `security-scans.yml` now scans the pinned pip lockfiles under `.github/requirements/`; trivy reads pip dependencies only from files named `requirements.txt`, so they were never scanned. `.github/trivy.yaml` names them, and `tools/ci/trivy_coverage.py` fails the job when the JSON report does not list exactly the tracked lockfiles. `tests/test_trivy_coverage.py` refuses a report without the pip lockfiles, one with an unexpected target and empty reports.
- `dispatch-kernel-requirements.yml` now fails when the `KERNEL_FORGE_TOKEN` secret is missing; before, the dispatch step was skipped and the job passed without sending the requirement to `nucleus`. `tests/test_kernel_dispatch.py` runs the new guard step with and without a token.
- The `Trivy Filesystem CVE Scan` job of `security-scans.yml` now fails on a fixed CRITICAL or HIGH finding (`exit-code: "1"`); before, trivy exited 0 and the job passed with findings. `tests/test_security_scans.py` checks that Trivy, Semgrep and Gitleaks each fail their job on a finding.
- The live tests no longer pass in CI without running. A missing Docker daemon, a missing bash or a preparation step past its bound still skips a test locally, but fails it when `IMAGO_REQUIRE_LIVE_TESTS=1`, which the pytest job of `ci.yml` sets (`tests/harness/live.py`). `tests/test_live_prerequisites.py` plants each missing prerequisite and checks both outcomes.
- The `required-checks` aggregator no longer counts every skipped check as passed (ADR-0026). A skip is accepted only for the nine jobs a change detector gates, listed by name in `MAY_SKIP` of `.github/workflows/required-aggregator.yml`; every other check must succeed. `tests/test_required_aggregator.py` holds the list equal to the detector-gated jobs of all workflows and refuses planted conditions that could skip a job on another ground.
- The CDI container test and the container cleanup no longer fail because of host
  load. The CDI test ran `apt-get` and its check under one 40-second timeout, and the
  cleanup gave `docker rm -f` one attempt, so a loaded host turned both into failures
  of the local gate. In `tests/test_container_integration.py` the installation of
  `python3-yaml` now has the 300-second installation bound; a host that exceeds it
  skips the CDI tests with the measured time, and the check itself keeps a 20-second
  budget. The cleanup tries the removal at most three times and fails only when the
  container remains. The specification reaches the check on standard input, read from
  `packer/provisioners/75-appliance-vision.sh`. New tests cover a specification of
  another device kind, an installation that exceeds its bound, and the removal against
  a stubbed and the real Docker daemon. The sysctl test installs nothing and is
  unchanged.
- The OpenSSH container test no longer fails because of host load (#69). Its one
  60-second budget covered the installation of `openssh-server`, whose duration
  depends on the host, so the same commit passed and failed within minutes. In
  `tests/test_container_integration.py` the container start and the installation now
  have their own bounds (120 s and 300 s); a host that exceeds one skips the sshd
  tests with the measured time, and `sshd -t` keeps a 20-second budget. The test reads
  the drop-in from `packer/provisioners/00-base-strip.sh` instead of an inline copy,
  and two new tests cover the negative cases: a drop-in with an unknown directive is
  rejected, and an installation that exceeds its bound skips.
- The rejection text of `pkg/aegis` is bounded. `Error.Reason` was documented as not
  echoing unbounded input, but a reason built from decoder or I/O error text repeated
  caller-controlled text at full length: a manifest with a 5000-byte unknown field name
  gave a 5037-byte reason. `boundReason` in `pkg/aegis/errors.go` cuts such a reason to
  the new exported bound `MaxReasonLen` (256 bytes) and ends it with ` (truncated)`.
  The cause in `Error.Err` is unchanged. `FuzzParse` holds the bound for every input.
- The Hindsight MCP server no longer hides every error raised while it closes a failed
  connection. `http_api` in `scripts/hindsight_mcp_server.py` wrapped the close in a bare
  `except Exception: pass`; it now suppresses only `OSError`, the error a socket close
  raises, so the request error is still the one reported and any other failure surfaces.
  Three tests in `tests/test_mcp_hindsight.py` cover the path.
- Two test modules import only what they use (`tests/test_agents_fleet.py`,
  `tests/test_cloudinit_deep.py`), and the allowlist check in
  `tests/test_scripts_automation.py` compares sets of domains, so code scanning stops
  reading it as a substring check on a URL.
- The documentation site deploys again. `.github/workflows/pages.yml` pinned
  `actions/upload-pages-artifact` v3.0.1, which calls `actions/upload-artifact` by tag;
  the repository admits only actions pinned to a full commit, inner actions included, so
  the job was refused before its first step. The pin moves to v5.0.0, which pins its
  inner action by commit. From v4.0.0 the action leaves dotfiles out of the artifact; the
  built site contains none.
- A release now updates the `VERSION` file and the version the `imago` CLI and MCP server
  advertise. `VERSION` was listed as an extra file without the marker the release tool
  looks for, and the constant in `cmd/imago/main.go` was not listed at all, so both
  would have stayed at 0.1.0.
- Provisioners fail when a step fails. 81 commands in 27 provisioners and scripts ended
  in `|| true`, so a package that did not install, a unit that could not be enabled or a
  module that was not configured left a build that reported success. The suppression is
  removed; the few steps that may legitimately do nothing (a unit that is not installed,
  a kernel module the build machine cannot load) test for that case and say so.
- Every download in a provisioner and in CI carries a time limit, so a stalled mirror
  ends the build instead of holding it.
- The two kernel contract workflows can start. `sync-kernel-manifest.yml` and
  `dispatch-kernel-requirements.yml` each pinned an action to a commit that upstream
  does not have, so every run ended before its first step. Both pins now name the
  commit of the release in their comment.
- `cdebug` is downloaded from the asset name its releases publish. The former URL
  carried the version in the file name, matched no asset, and the failure was discarded.
- `hyperv-daemons` is installed only where the package index offers it; where it does
  not, the build says that no Hyper-V guest daemons are installed.
- `spice-vdagent` is no longer enabled by hand: the package ships no unit that can be
  enabled, and its udev rule starts the agent when the SPICE port appears.
- `scripts/manage_aistudio_agents.py`, `scripts/orchestrate_fanout.py` and the privacy
  guard hook report an error to their caller instead of ending the process from inside
  a helper, and `imago audit` runs its script under a time limit.

- Two preheated images were pinned to tags that do not exist: Flannel carried a `v`
  prefix upstream dropped, and the AMD device plugin was pinned to a Kubernetes
  version rather than one of its own. A failed preheat now fails the build, because
  carrying those images is what the preheated flavors are for; warning and
  continuing shipped a flavor that advertised a cached CNI and contained none.

- The built image is found where it is written. Packer runs inside `packer/`, so the
  artifacts land there, while compression and upload looked at the repository root;
  and the flavor variable was never passed, so every flavor wrote into the default
  directory instead of its own.

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
