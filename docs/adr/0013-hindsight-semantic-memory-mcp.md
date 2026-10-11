# 13. Persistent Cross-Session Memory via Hindsight Semantic Backend & MCP Architecture

Date: 2026-09-10

## Status

Accepted

## Context

Autonomous engineering agents in `lusoris-cloud-images` operate across multiple sessions, worktrees, and feature branches. Without a persistent memory substrate, each new session suffers from contextual amnesia:

1. **Context Window Exhaustion**: Agents spend significant token budgets repeatedly rediscovering established architectural constraints, ADRs, test patterns, and historical bug resolutions.
2. **Loss of Experiential Knowledge**: Decisions reached during debugging sessions, performance profiling (e.g., QEMU CPU pin flags, B580 concurrency bounds), or security reviews are discarded when the chat session terminates.
3. **Fleet-Wide Knowledge Fragmentation**: When multiple specialized agents (such as `infra-forge`, `security-compliance`, `container-k8s`, and `qa-gatekeeper`) make discoveries in parallel worktrees, their observations remain siloed.

In the companion infrastructure repository (`lusoris/k8s`), the self-hosted **Hindsight** (`v0.8.4`) semantic memory engine (`apps/ai/hindsight`) provides persistent, long-term memory for the fleet:

- **Core Memory Primitives**: Retain (fact extraction and ingestion), Recall (hybrid semantic search and vector retrieval), and Reflect (mental model synthesis).
- **Embedded pgvector Storage**: Persisted on Longhorn v2 NAS-backed storage with HNSW index acceleration, currently holding 40 banks and 36,000+ facts.
- **Nightly Observation Consolidation**: Scheduled distillation (`02:20 Europe/Berlin`) merging raw facts into compact, evidence-grounded observations.

We require a standardized bridge to connect Antigravity IDE, Claude Code, Cursor, and autonomous agents to Hindsight while strictly observing repository security invariants (Hard Rule 6 zero-leak boundary) and ensuring operational resilience when disconnected from the cluster.

## Decision

We integrate Hindsight semantic memory into `lusoris-cloud-images` via a dual-layer Model Context Protocol (MCP) architecture:

### 1. Dual-Layer MCP Configuration Standard

We establish declarative MCP server configuration across two standard locations:

- **`.mcp.json`** (Repository Root): Industry-standard manifest consumable by Antigravity, Claude Code, Cursor, Zed, and Codex CLI.
- **`.agents/mcp_config.json`** (Antigravity Workspace Root): Native workspace configuration automatically discovered by Antigravity IDE.

Both manifests declare:

- `hindsight`: Local stdio bridge executing `python scripts/hindsight_mcp_server.py`.
- `cauda-kb`: Streamable HTTP endpoint (`http://127.0.0.1:38001/mcp`) exposing the unified `lusoris-k8s` knowledge base.
- `context7`: Upstash documentation MCP server (`@upstash/context7-mcp@3.1.0`).

### 2. Resilient Hindsight MCP Stdio Bridge (`scripts/hindsight_mcp_server.py`)

Rather than depending on a brittle raw TCP connection that causes IDE crashes if the cluster drops, we implement an stdio MCP server proxy:

- **Protocol**: Standard JSON-RPC 2.0 over `stdin`/`stdout`.
- **Bank Isolation**: Default bank set to `lusoris-cloud-images` within tenant `default`.
- **Exposed Toolset**:
  - `hindsight_recall(query, top_k=5, bank_id)`: Hybrid retrieval over durable architectural rules, bug root causes, and previous decisions.
  - `hindsight_retain(content, context, bank_id)`: Persists discoveries, rationale, and constraints into Hindsight memory.
  - `hindsight_reflect(bank_id)`: Triggers consolidation and mental model synthesis.
  - `hindsight_status()`: Probes backend connectivity, active bank count, and local buffer state.
  - `hindsight_list_banks()`: Lists available fleet memory banks.

### 3. Hard Rule 6 Zero-Leak Privacy Guard

Prior to retaining any memory into Hindsight, `scripts/hindsight_mcp_server.py` executes pre-ingest privacy sanitization:

- **RFC 1918 Private IP Redaction**: Strips all `10.x.x.x`, `192.168.x.x`, and `172.16-31.x.x` addresses, replacing them with `[REDACTED-RFC1918-IP]`.
- **Workstation Path Redaction**: Strips `/home/<user>`, `/Users/<user>`, and Windows user directories, replacing them with `[REDACTED-USER-PATH]`.

### 4. Resilient Offline Buffer & Reconnection Sync

If the cluster backend is temporarily unreachable:

- Retained memories are safely appended to an ignored local buffer at `.workingdir2/memory/hindsight-local-buffer.json` with `pending_sync: true`.
- Recall operations seamlessly query both local buffer facts and report offline status.
- Once the cluster endpoint is restored, subsequent operations flush pending buffered items to Hindsight.

### 5. Cluster Tunnel Supervisor (`scripts/tunnel_hindsight.py`)

A lightweight supervisor daemon manages the `kubectl --namespace=ai port-forward service/hindsight 8888:8888 --address=127.0.0.1` process with auto-reconnection and health probing.

## Consequences

### Positive

- **Persistent Recall**: Agents remember past debugging findings, GPU hardware quirks, and architectural constraints across fresh sessions.
- **Privacy Assurance**: Zero private RFC 1918 IP addresses or developer home paths enter vector memory banks.
- **Seamless Offline Work**: The local buffer ensures that agents remain fully functional even when developing offline or without active cluster VPN access.
- **Cross-Client Standardization**: Compatible with Antigravity IDE, Claude Code, and Codex.

### Negative / Neutral

- **Tunnel Lifecycle**: Accessing live cluster memory requires running `python scripts/tunnel_hindsight.py` or having an active port-forward.
- **Memory Consolidation Cadence**: Raw retained facts depend on Hindsight's nightly consolidation loop for full deduplication.
