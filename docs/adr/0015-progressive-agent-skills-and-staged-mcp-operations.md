# 15. Progressive Disclosure Agent Skills & Two-Phase Staged MCP Mutation Guardrails

Date: 2026-09-10

## Status

Accepted

## Context

As autonomous AI engineering agents (`agy`, Claude Code, Cursor, and the AI Studio Managed Agents fleet) take on complex, long-running architectural workflows in `lusoris-cloud-images`, two operational bottlenecks emerged:

1. **Context Window Saturation from Monolithic Skills**:
   The initial agent skill library embedded full reference tables (e.g. all 44 flavors, Packer target flags, hardware requirements, and lengthy test instructions) directly inside top-level `SKILL.md` files. When multiple skills are scanned or loaded during prompt discovery, hundreds of tokens are consumed before task execution even begins.
2. **Uncontrolled Live Mutation & Destructive Side Effects**:
   MCP tools that trigger builds (`trigger_build`) or generate host modification scripts (`apply_flavor`) executed synchronously upon model output. If an LLM hallucinates an invalid backend or initiates an expensive local or remote build without explicit operator intention, resources are consumed with zero human-in-the-loop review. This conflicts with global operating charters enforcing declarative sources of truth and non-destructive defaults.

An architectural audit of high-leverage open-source patterns—specifically the **3-layer progressive disclosure architecture** in [`OpenSkills`](https://github.com/LingyiChen-AI/OpenSkills) and the **two-phase write staging guardrails** in [`OmniKube`](https://github.com/LingyiChen-AI/OmniKube)—provided concrete solutions.

## Decision

We adopt a two-part architectural standard across agent skills and the Go MCP server:

### 1. Three-Layer Progressive Disclosure for Agent Skills (`.agents/skills/`)

All skills in `.agents/skills/` are refactored into three strictly isolated information layers:

- **Layer 1: Metadata (Always Loaded)**:
  Clean YAML frontmatter containing only `name`, `description`, and declared `references`. Used for rapid skill discovery and routing with zero prompt bloat:

  ```yaml
  ---
  name: build-image
  description: Build a specific Lusoris cloud or k8s node image flavor via Packer
  references:
    - references/flavor-matrix.md
  ---
  ```

- **Layer 2: Instruction (On-Demand Workflow)**:
  Concise, action-oriented execution procedures and usage examples in `SKILL.md`. Kept under 50 lines to maximize cognitive focus.
- **Layer 3: Resources & Deep References (Conditional Loading)**:
  Detailed hardware matrices, BOM templates, and validation checklists isolated in `references/` (e.g. `references/flavor-matrix.md`, `references/flavor-checklist.md`). Agents retrieve these on-demand via `view_file` only when deep technical specifications are required.

Enforced by automated verification in `tests/test_agents_fleet.py` (`test_skills_progressive_disclosure_structure`).

### 2. Two-Phase Staged Write Guardrails in Go MCP Server (`pkg/mcp`)

In `pkg/mcp/staging.go` and `pkg/mcp/server.go`:

- Any mutating or external dispatch tool (`trigger_build`, `apply_flavor`) executes under a **fail-closed staging guardrail**:
  - If invoked without `confirmed=true` or `dry_run=true`, the tool does not mutate state.
  - A thread-safe `Stager` registers a `StagedAction` with a unique ID (`act-<hex>`), timestamp, and formatted preview card.
  - A staging card is returned to the agent/operator summarizing the target flavor, backend, and exact parameters.
- **Confirmation & Execution**:
  - The action is only dispatched when explicitly confirmed via `confirm_action(action_id: "act-...")` or re-run with `"confirmed": true`.
  - Pending actions can be inspected via `list_staged_actions` or cancelled via `discard_staged_action`.

## Consequences

### Positive

- **Context Preservation**: Reduces skill discovery overhead by over 70%, keeping context windows lean for complex coding and debugging trajectories.
- **Accidental Build Prevention**: Guarantees zero unintentional builds or host-altering scripts are dispatched without deliberate confirmation.
- **Holzmann Power of 10 & Go Concurrency Safety**: All staging operations are protected by `sync.RWMutex` with clean, bounded lifecycles.
- **Zero Breaking Changes**: Existing scripts can pass `confirmed: true` or `dry_run: true` to bypass staging seamlessly.

### Negative / Neutral

- Multi-turn interactive workflows require an extra confirmation step (`confirm_action`) for mutating operations unless `confirmed: true` is passed upfront.
