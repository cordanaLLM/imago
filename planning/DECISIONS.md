# Planning decisions — imago migration

Operator decisions recorded on 2026-09-15 that scope the planning graph in
[plan.json](plan.json). Each decision is a caller-asserted planning source; the
graph cites this file by its SHA-256 so a changed decision invalidates the
dependent draft.

| ID | Decision | Rationale |
| :--- | :--- | :--- |
| D01 | The repository targets the identity `cordanaLLM/imago`. | Named as the reusable image builder in the Aegis-OS connected stack contract and in praetor's changelog; the GitHub repository does not exist yet and is created by the operator at transfer time. |
| D02 | Praetor governance is adopted now with the interim profile `gitops-infra`; an `os-image` archetype is drafted here and proposed upstream, and the manifest switches to it once praetor ships it. | No praetor archetype describes an OS image forge; `gitops-infra` keeps the existing 60-line function bound and yamllint/trivy gates. |
| D03 | The Go code migrates fully onto golusoris `core`: clikit for the CLI, core/log for logging, core/clock for time, core/mcp for the MCP transport. | golusoris ADR-0019 expects every fleet Go repository to deduplicate onto the framework; the duplicated stdout-purity guard is retired. |
| D04 | The migration is tracked as a typed dependency graph under `planning/`, compiled with praetor's planning compiler and routed by `imago plan route`. | Follows the Aegis-OS precedent of a committed roadmap ranked by unblock value per cost; the private `.workingdir/` ledger stays for session state. |
| D05 | Application defects surfaced by the governance gates are fixed after lefthook and `make verify-all` run green. | Gates first, then fixes, so every fix is verified by the harness it targets. |
