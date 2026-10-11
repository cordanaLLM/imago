# Copyright 2026 Lusoris Authors
# Licensed under the Apache License, Version 2.0
"""Automated verification suite for Hindsight MCP memory bridge and configs.

Asserts:
- .mcp.json and .agents/mcp_config.json valid JSON and tool wiring parity.
- scripts/hindsight_mcp_server.py JSON-RPC 2.0 protocol compliance.
- Hard Rule 6 zero-leak privacy sanitization in hindsight memory.
- Resilient offline fallback buffering when cluster endpoint is unreachable.
"""

from __future__ import annotations

import http.client
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT_MCP_JSON = REPO_ROOT / ".mcp.json"
WORKSPACE_MCP_JSON = REPO_ROOT / ".agents" / "mcp_config.json"
SERVER_SCRIPT = REPO_ROOT / "scripts" / "hindsight_mcp_server.py"
TUNNEL_SCRIPT = REPO_ROOT / "scripts" / "tunnel_hindsight.py"
LOCAL_CACHE_FILE = REPO_ROOT / ".workingdir2" / "memory" / "hindsight-local-buffer.json"


def call_mcp_server(request_payload: dict) -> dict:
    """Send JSON-RPC request to hindsight_mcp_server.py via stdio."""
    raw_input = json.dumps(request_payload) + "\n"
    proc = subprocess.run(
        [sys.executable, str(SERVER_SCRIPT)],
        input=raw_input,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout.strip())


class TestHindsightMCP:
    def test_mcp_config_files_exist_and_match(self) -> None:
        """Verify .mcp.json and .agents/mcp_config.json are valid and declare hindsight."""
        assert ROOT_MCP_JSON.exists(), ".mcp.json must exist at repository root"
        assert WORKSPACE_MCP_JSON.exists(), ".agents/mcp_config.json must exist"

        root_data = json.loads(ROOT_MCP_JSON.read_text(encoding="utf-8"))
        ws_data = json.loads(WORKSPACE_MCP_JSON.read_text(encoding="utf-8"))

        assert "mcpServers" in root_data
        assert "mcpServers" in ws_data
        assert "hindsight" in root_data["mcpServers"]
        assert "hindsight" in ws_data["mcpServers"]

        assert root_data["mcpServers"]["hindsight"]["command"] == "python"
        assert root_data["mcpServers"]["hindsight"]["args"] == ["scripts/hindsight_mcp_server.py"]

    def test_json_rpc_initialize(self) -> None:
        """Verify initialize handshake conforms to MCP specification."""
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }
        res = call_mcp_server(req)
        assert res.get("jsonrpc") == "2.0"
        assert res.get("id") == 1
        result = res.get("result", {})
        assert result.get("protocolVersion") == "2024-11-05"
        assert result.get("serverInfo", {}).get("name") == "lusoris-hindsight-mcp"

    def test_json_rpc_tools_list(self) -> None:
        """Verify tools/list exposes required hindsight memory operations."""
        req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        res = call_mcp_server(req)
        tools = res.get("result", {}).get("tools", [])
        tool_names = {t["name"] for t in tools}

        expected = {
            "hindsight_recall",
            "hindsight_retain",
            "hindsight_reflect",
            "hindsight_status",
            "hindsight_list_banks",
        }
        assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"

    def test_zero_leak_privacy_sanitization(self) -> None:
        """Verify RFC 1918 IPs and workstation home paths are redacted on retain."""
        test_content = "Configuring proxy at 10.244.0.15 and workstation at /home/developer/dev on C:\\Users\\developer"
        req = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "hindsight_retain",
                "arguments": {
                    "content": test_content,
                    "bank_id": "test-privacy-bank",
                },
            },
        }
        res = call_mcp_server(req)
        assert res.get("id") == 10
        assert "Stored locally" in res["result"]["content"][0]["text"]

        assert LOCAL_CACHE_FILE.exists()
        saved = json.loads(LOCAL_CACHE_FILE.read_text(encoding="utf-8"))
        entry = next((e for e in saved if e.get("bank_id") == "test-privacy-bank"), None)
        assert entry is not None

        # Verify privacy invariants
        assert "10.244.0.15" not in entry["content"]
        assert "[REDACTED-RFC1918-IP]" in entry["content"]
        assert "/home/developer" not in entry["content"]
        assert "[REDACTED-USER-PATH]" in entry["content"]

        # Clean up test entry
        remaining = [e for e in saved if e.get("bank_id") != "test-privacy-bank"]
        if remaining:
            LOCAL_CACHE_FILE.write_text(json.dumps(remaining, indent=2), encoding="utf-8")
        else:
            LOCAL_CACHE_FILE.unlink(missing_ok=True)

    def test_tunnel_script_help(self) -> None:
        """Verify tunnel supervisor script CLI arguments."""
        proc = subprocess.run(
            [sys.executable, str(TUNNEL_SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "--check" in proc.stdout
        assert "--port" in proc.stdout


class _FailingConnection:
    """Connection whose request always fails and whose close raises what the test sets."""

    close_error: BaseException | None = None

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.target = (host, port, timeout)

    def request(self, method: str, path: str, body: bytes | None, headers: dict) -> None:
        raise ConnectionRefusedError("request refused")

    def close(self) -> None:
        if self.close_error is not None:
            raise self.close_error


class TestHttpApiCleanup:
    """http_api reports the request error and hides only a failed socket close."""

    @pytest.fixture
    def server(self, monkeypatch: pytest.MonkeyPatch):
        spec = importlib.util.spec_from_file_location("hindsight_mcp_server", SERVER_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        monkeypatch.setattr(http.client, "HTTPConnection", _FailingConnection)
        monkeypatch.setattr(_FailingConnection, "close_error", None)
        return module

    def test_request_error_is_reported(self, server) -> None:
        assert server.http_api("GET", "/health") == (0, {"error": "request refused"})

    def test_socket_close_error_does_not_replace_the_request_error(
        self, server, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_FailingConnection, "close_error", OSError("close failed"))
        assert server.http_api("GET", "/health") == (0, {"error": "request refused"})

    def test_other_close_error_is_not_hidden(self, server, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_FailingConnection, "close_error", RuntimeError("not a socket error"))
        with pytest.raises(RuntimeError, match="not a socket error"):
            server.http_api("GET", "/health")
