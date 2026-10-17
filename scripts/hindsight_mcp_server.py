#!/usr/bin/env python3
# Copyright 2026 Lusoris Authors
# SPDX-License-Identifier: EUPL-1.2
"""Hindsight semantic-memory Model Context Protocol (MCP) server bridge.

Exposes self-hosted Hindsight memory (from lusoris/k8s) as standard MCP tools:
- hindsight_recall: query persistent facts, decisions, and observations
- hindsight_retain: store durable engineering discoveries and rules
- hindsight_reflect: trigger observation distillation and mental models
- hindsight_status: probe cluster backend health and local cache state
- hindsight_list_banks: list memory banks across the fleet

Complies with NASA/JPL Power of 10: short functions (<= 60 lines), strict
validation, bounded loops, and zero-leak privacy sanitization.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

HINDSIGHT_URL = os.environ.get("HINDSIGHT_URL", "http://127.0.0.1:8888").rstrip("/")
HINDSIGHT_TENANT = os.environ.get("HINDSIGHT_TENANT", "default")
DEFAULT_BANK = os.environ.get("HINDSIGHT_BANK", "lusoris-cloud-images")
REQUEST_TIMEOUT = int(os.environ.get("HINDSIGHT_TIMEOUT", "15"))
API_KEY_VAR = "HINDSIGHT_API_KEY"


def read_api_key() -> str:
    """Return the tenant key, or "" when unset or left as an unexpanded `${...}` placeholder by the client."""
    key = os.environ.get(API_KEY_VAR, "").strip()
    return "" if key.startswith("${") else key


# The server compares the bearer token with its HINDSIGHT_API_TENANT_API_KEY (secret hindsight-tenant-api-key).
HINDSIGHT_API_KEY = read_api_key()

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_CACHE_DIR = REPO_ROOT / ".workingdir" / "memory"
LOCAL_CACHE_FILE = LOCAL_CACHE_DIR / "hindsight-local-buffer.json"

RFC1918_PATTERN = re.compile(
    r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)
WORKSTATION_PATH_PATTERN = re.compile(
    r"(/home/(?!(ubuntu|username|runner)\b)[a-zA-Z0-9_-]+|/Users/[a-zA-Z0-9_-]+|[A-Za-z]:\\Users\\[a-zA-Z0-9_-]+)"
)


def sanitize_privacy(text: str) -> str:
    """Enforce zero-leak invariant by redacting private IPs and user paths."""
    sanitized = RFC1918_PATTERN.sub("[REDACTED-RFC1918-IP]", text)
    return WORKSTATION_PATH_PATTERN.sub("[REDACTED-USER-PATH]", sanitized)


def read_local_buffer() -> list[dict[str, Any]]:
    """Read local memory buffer for offline fallback."""
    if not LOCAL_CACHE_FILE.exists():
        return []
    try:
        content = LOCAL_CACHE_FILE.read_text(encoding="utf-8")
        data = json.loads(content)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def write_local_buffer(entries: list[dict[str, Any]]) -> None:
    """Save memory entries to local fallback buffer."""
    LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_CACHE_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def append_local_fact(content: str, context: str, bank_id: str) -> dict[str, Any]:
    """Append fact to local buffer when upstream is unreachable."""
    entries = read_local_buffer()
    entry = {
        "id": f"local-{int(time.time() * 1000)}",
        "bank_id": bank_id,
        "content": content,
        "context": context,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
        "pending_sync": True,
    }
    entries.append(entry)
    write_local_buffer(entries)
    return entry


def http_api(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    """Dispatch HTTP request to Hindsight API endpoint using http.client (immune to dynamic urllib SSRF)."""
    url = f"{HINDSIGHT_URL}{path}"
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Prohibited URL scheme for Hindsight API: {url}")

    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if HINDSIGHT_API_KEY:
        headers["Authorization"] = f"Bearer {HINDSIGHT_API_KEY}"
    full_path = parsed.path or "/"
    if parsed.query:
        full_path += f"?{parsed.query}"

    conn: http.client.HTTPConnection | None = None
    try:
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8888
        conn = http.client.HTTPConnection(host, port, timeout=REQUEST_TIMEOUT)

        conn.request(method, full_path, body=data, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8")
        status = resp.status
        conn.close()
        return status, json.loads(raw) if raw.strip() else {}
    except Exception as exc:
        if conn:
            # The first error is the one reported; a socket that fails to close adds nothing.
            with contextlib.suppress(OSError):
                conn.close()
        return 0, {"error": str(exc)[:300]}


def flush_local_pending() -> int:
    """Sync buffered facts, each into its own bank; stop at the first refusal and keep the rest pending."""
    entries = read_local_buffer()
    synced = 0
    for item in entries:
        if not item.get("pending_sync"):
            continue
        payload = {"content": item["content"], "context": item.get("context", "")}
        quoted_bank = urllib.parse.quote(str(item.get("bank_id", DEFAULT_BANK)), safe="")
        st, _ = http_api("POST", f"/v1/{HINDSIGHT_TENANT}/banks/{quoted_bank}/retain", payload)
        if not 200 <= st < 300:
            break
        item["pending_sync"] = False
        synced += 1
    if synced > 0:
        write_local_buffer(entries)
    return synced


def succeeded(st: int) -> bool:
    """Report a 2xx status; the first one drains the offline buffer before the caller goes on."""
    if not 200 <= st < 300:
        return False
    flush_local_pending()
    return True


def failure_reason(st: int) -> str:
    """Name why a request failed: no response, a refused tenant key, or a server error."""
    if st == 0:
        return "unreachable"
    if st in (401, 403):
        return f"unauthorised (HTTP {st})"
    return f"error (HTTP {st})"


def tool_hindsight_retain(content: str, context: str = "", bank_id: str = DEFAULT_BANK) -> str:
    """Retain memory into Hindsight or offline buffer."""
    clean_content = sanitize_privacy(content.strip())
    clean_context = sanitize_privacy(context.strip())
    if not clean_content:
        return "Error: Memory content cannot be empty."

    payload = {"content": clean_content, "context": clean_context}
    quoted_bank = urllib.parse.quote(bank_id, safe="")
    st, data = http_api("POST", f"/v1/{HINDSIGHT_TENANT}/banks/{quoted_bank}/retain", payload)

    if succeeded(st):
        doc_id = data.get("document_id") or data.get("id") or "stored"
        return f"[Hindsight Upstream] Retained fact in bank '{bank_id}' (document_id: {doc_id})."

    entry = append_local_fact(clean_content, clean_context, bank_id)
    return (
        f"[Hindsight Offline Buffer] Upstream {failure_reason(st)}. Stored locally in "
        f"bank '{bank_id}' (buffer_id: {entry['id']}, pending_sync: true)."
    )


def tool_hindsight_recall(query: str, top_k: int = 5, bank_id: str = DEFAULT_BANK) -> str:
    """Recall relevant facts from Hindsight or offline buffer."""
    clean_query = sanitize_privacy(query.strip())
    k = max(1, min(20, int(top_k)))
    quoted_bank = urllib.parse.quote(bank_id, safe="")
    payload = {"query": clean_query, "k": k}

    st, data = http_api("POST", f"/v1/{HINDSIGHT_TENANT}/banks/{quoted_bank}/recall", payload)
    if succeeded(st):
        results = data if isinstance(data, list) else data.get("results", data.get("memories", []))
        if not results:
            return f"[Hindsight Upstream] No relevant memories found in bank '{bank_id}' for query: '{clean_query}'."
        lines = [f"Found {len(results)} memories in bank '{bank_id}':"]
        for idx, item in enumerate(results, 1):
            text = item.get("text") or item.get("content") or str(item)
            score = item.get("score") or item.get("distance", "")
            lines.append(f"{idx}. {text} (score: {score})")
        return "\n".join(lines)

    local_entries = read_local_buffer()
    matched = [
        e for e in local_entries if e.get("bank_id") == bank_id and clean_query.lower() in e.get("content", "").lower()
    ]
    if matched:
        lines = [f"[Hindsight Offline Buffer] Found {len(matched[:k])} locally buffered facts in '{bank_id}':"]
        for idx, item in enumerate(matched[:k], 1):
            lines.append(f"{idx}. {item['content']} (saved: {item['timestamp']})")
        return "\n".join(lines)
    return f"[Hindsight Offline Buffer] Upstream {failure_reason(st)}. No matching buffered facts for '{clean_query}'."


def tool_hindsight_reflect(bank_id: str = DEFAULT_BANK) -> str:
    """Trigger reflection to distill observations into mental models."""
    quoted_bank = urllib.parse.quote(bank_id, safe="")
    st, data = http_api("POST", f"/v1/{HINDSIGHT_TENANT}/banks/{quoted_bank}/reflect", {})
    if succeeded(st):
        op = data.get("operation_id") or "completed"
        return f"[Hindsight Upstream] Reflection cycle triggered for bank '{bank_id}' (operation: {op})."
    return f"[Hindsight Notice] Upstream {failure_reason(st)}. Reflection skipped."


def pending_count() -> int:
    """Count buffered facts that have not reached upstream yet."""
    return sum(1 for entry in read_local_buffer() if entry.get("pending_sync"))


def status_failure(st: int, data: Any) -> tuple[str, str]:
    """Return the status headline and the notice that tells the operator what to fix."""
    if st == 0:
        return (
            "UNREACHABLE (no HTTP response)",
            "Port-forward 'service/hindsight 8888:8888' is not currently connected.",
        )
    if st in (401, 403):
        state = "was rejected" if HINDSIGHT_API_KEY else "is not set"
        return f"UNAUTHORISED (HTTP {st})", f"{API_KEY_VAR} {state}; set it to the tenant key of the deployment."
    return f"ERROR (HTTP {st})", f"The server answered with an error: {sanitize_privacy(str(data))[:300]}"


def tool_hindsight_status() -> str:
    """Probe status of Hindsight cluster API and local cache."""
    st, data = http_api("GET", f"/v1/{HINDSIGHT_TENANT}/banks")
    if succeeded(st):
        banks = data if isinstance(data, list) else data.get("banks", data.get("items", []))
        return (
            f"Hindsight Status: ONLINE (HTTP {st})\n"
            f"Upstream URL: {HINDSIGHT_URL}\n"
            f"Tenant: {HINDSIGHT_TENANT}\n"
            f"Active Banks: {len(banks)}\n"
            f"Local Offline Buffer: {pending_count()} entries pending"
        )
    headline, notice = status_failure(st, data)
    return (
        f"Hindsight Status: {headline}\n"
        f"Target URL: {HINDSIGHT_URL}\n"
        f"Notice: {notice}\n"
        f"Local Offline Buffer: {pending_count()} entries pending"
    )


def tool_hindsight_list_banks() -> str:
    """List all available memory banks."""
    st, data = http_api("GET", f"/v1/{HINDSIGHT_TENANT}/banks")
    if succeeded(st):
        banks = data if isinstance(data, list) else data.get("banks", data.get("items", []))
        lines = [f"Available Hindsight memory banks ({len(banks)}):"]
        for b in banks:
            name = b if isinstance(b, str) else b.get("bank_id") or b.get("id") or str(b)
            lines.append(f"- {name}")
        return "\n".join(lines)
    return f"Unable to list banks (upstream {failure_reason(st)} at {HINDSIGHT_URL}). Default bank: '{DEFAULT_BANK}'."


def bank_id_property() -> dict[str, Any]:
    """Return the schema of the `bank_id` argument that three tools share."""
    return {"type": "string", "description": "Target memory bank identifier.", "default": DEFAULT_BANK}


def tool_definition(
    name: str, description: str, properties: dict[str, Any], required: tuple[str, ...] = ()
) -> dict[str, Any]:
    """Build one MCP tool definition; `required` appears only when it names an argument."""
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = list(required)
    return {"name": name, "description": description, "inputSchema": schema}


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return JSON-RPC tool definitions for MCP protocol."""
    recall_properties = {
        "query": {"type": "string", "description": "Semantic search query or topic to recall."},
        "top_k": {"type": "integer", "description": "Maximum number of memories to return (1-20).", "default": 5},
        "bank_id": bank_id_property(),
    }
    retain_properties = {
        "content": {"type": "string", "description": "Fact or knowledge statement to retain."},
        "context": {"type": "string", "description": "Optional background rationale, file path, or issue reference."},
        "bank_id": bank_id_property(),
    }
    return [
        tool_definition(
            "hindsight_recall",
            "Recall relevant persistent memories, past engineering decisions, and lessons learned.",
            recall_properties,
            ("query",),
        ),
        tool_definition(
            "hindsight_retain",
            "Retain a durable fact, architecture decision, bug root cause, or constraint into persistent memory.",
            retain_properties,
            ("content",),
        ),
        tool_definition(
            "hindsight_reflect",
            "Trigger observation reflection and mental model distillation for a memory bank.",
            {"bank_id": bank_id_property()},
        ),
        tool_definition(
            "hindsight_status",
            "Check the connection status of the Hindsight memory backend and local cache.",
            {},
        ),
        tool_definition("hindsight_list_banks", "List all active memory banks in the Hindsight tenant.", {}),
    ]


def handle_tool_call(name: str, arguments: dict[str, Any]) -> str:
    """Route tool call execution to corresponding handler."""
    if name == "hindsight_recall":
        return tool_hindsight_recall(
            arguments.get("query", ""),
            arguments.get("top_k", 5),
            arguments.get("bank_id", DEFAULT_BANK),
        )
    if name == "hindsight_retain":
        return tool_hindsight_retain(
            arguments.get("content", ""),
            arguments.get("context", ""),
            arguments.get("bank_id", DEFAULT_BANK),
        )
    if name == "hindsight_reflect":
        return tool_hindsight_reflect(arguments.get("bank_id", DEFAULT_BANK))
    if name == "hindsight_status":
        return tool_hindsight_status()
    if name == "hindsight_list_banks":
        return tool_hindsight_list_banks()
    return f"Error: Unknown tool '{name}'"


def handle_rpc_message(msg: dict[str, Any]) -> dict[str, Any] | None:
    """Process single JSON-RPC message adhering to MCP specification."""
    msg_id = msg.get("id")
    method = msg.get("method")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "lusoris-hindsight-mcp", "version": "0.8.4"},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": get_tool_definitions()}}
    if method == "tools/call":
        params = msg.get("params", {})
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        result_text = handle_tool_call(tool_name, tool_args)
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"content": [{"type": "text", "text": result_text}]},
        }
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> None:
    """Stdio main loop parsing JSON-RPC messages line by line."""
    for line in sys.stdin:
        line_str = line.strip()
        if not line_str:
            continue
        try:
            req = json.loads(line_str)
            resp = handle_rpc_message(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
