# 19. Fleet Migration to cordanaLLM/imago: Praetor Governance, Golusoris Core, and a Routed Planning Graph

Date: 2026-09-15

## Status

Accepted

## Context

The fleet's connected-stack contract in `cordanaLLM/Aegis-OS` (`docs/integration/stack.md`) assigns "reusable image construction, kernel consumption, image artifact production" to a producer named `cordanaLLM/imago`, and kernel artifact production to `cordanaLLM/nucleus`. Praetor's changelog records governance bootstrapping for both names. Neither repository exists on GitHub yet; the Aegis-OS roadmap milestone M09 records the unresolved producer identities as its blocker. This repository is the image forge those names describe, and `lusoris/lusoris-kernel-forge` is the kernel forge.

At the same time, three fleet conventions had not reached this repository:

1. **Praetor governance** (`cordanaLLM/praetor`): a declarative `.standards.yaml`, HISS-16 invariants, a single canonical `AGENTS.md` compiled into vendor context, lefthook gates, a `.needs.yaml` demand declaration, and the `.workingdir/` state ledger. Praetor's own adoption dry-run detected this polyglot repository (Packer HCL, shell, Python, Go) as the `framework` archetype and the `python-ml` flavor; no archetype describes an OS image forge, and `adopt` failed on Windows because `internal/config/catalog_projection.go` compares a platform path against a slash-separated constant.
2. **Golusoris core** (`github.com/golusoris/golusoris/core`): golusoris ADR-0019 expects every fleet Go repository to deduplicate onto the framework. This repository's Go code carried its own cobra root, tint logger, stdout-purity guard, and `time.Now()` calls. The framework's `capabilities.yaml` contract maps all four third-party dependencies (tint, go-sdk, cobra, testify) to framework packages.
3. **Graph-routed planning**: praetor compiles typed planning drafts (schema version 1) into linked `TODO.md`, `ROADMAP.md`, and `MILESTONES.md` projections with dependency-cycle rejection and a stable digest. Aegis-OS commits its roadmap as a dependency graph ranked by unblock value per cost. This repository tracked work only as cadence epics in `.github/epics.json`.

## Decision

1. **Identity**: the module path becomes `github.com/cordanaLLM/imago`, the CLI and MCP server are named `imago`, and documentation refers to the target identity. The GitHub transfer is an operator action tracked in the planning graph; links under `lusoris/lusoris-cloud-images` keep resolving through GitHub redirects until then.
2. **Praetor governance now, `os-image` archetype next**: the repository adopts praetor with the interim profile `gitops-infra` (60-line function bound, yamllint and trivy gates) and the facets `security:high`, `agent:sandboxed`, and `docs:seo-portal`. A complete `os-image` archetype is drafted under `planning/archetypes/os-image.yaml` and proposed upstream; the manifest switches to it once praetor ships it. The Python gate is selected explicitly through `pytest.ini`. The praetor Windows path-separator defect is reported upstream rather than worked around in this repository.
3. **Golusoris core composition**: `core/clikit` builds the command tree; `core/log` provides the `slog` logger; `core/clock` is injected into the build dispatcher and the two-phase staging guard (a request without a clock is rejected); `core/mcp` owns the MCP transport lifecycle, including the stdio stdout-purity guard this repository previously duplicated. The MCP package exposes `RegisterTools` on the framework server instead of constructing one. `testify` stays for assertions because the framework's `testutil` tree targets infrastructure fixtures, and this non-goal is declared in `.needs.yaml`.
4. **Routed planning graph**: `planning/plan.json` is a praetor planning draft compiled with `praetorctl planning prepare`; the generated `TODO.md`, `ROADMAP.md`, and `MILESTONES.md` are committed next to it. `planning/routing.json` carries the operational facts the draft schema excludes (cost class, completion, ownership, external-contract and hardware flags). `imago plan route` and the `route_plan` MCP tool derive the ready set and rank it: ready local work first, then score `(1 + transitive unblocks) / cost`, ties toward more transitive unblocks, then lexicographic ID. Cadence epics in `.github/epics.json` remain the recurring-work ledger; one-off migration work lives in the graph.

## Consequences

- **Positive**: the repository is addressable by the identity the Aegis-OS contract expects, and its Go surface reuses framework capabilities instead of maintaining copies (the stdout guard and logger wiring are deleted, not forked).
- **Positive**: agents and operators share one deterministic answer to "what is ready and most valuable next" through the CLI, the MCP tool, and the committed projections.
- **Negative**: `gitops-infra` records nine legacy HISS infractions in the baseline that must ratchet down; `container-image` gates (hadolint, dockle) do not apply and are not declared.
- **Negative**: the MCP transport now runs under an fx lifecycle; the server exits when the stdio client disconnects, matching praetor and golusoris behaviour but differing from the previous long-lived process.
- **Neutral**: the Aegis product-input contract (`aegis.p01.product-input.v1`, mkosi and UKI output) is a planned milestone flagged as needing an external contract; nothing in this decision implements it.
