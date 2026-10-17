# Copyright 2026 Lusoris Authors
# SPDX-License-Identifier: EUPL-1.2
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
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT_MCP_JSON = REPO_ROOT / ".mcp.json"
WORKSPACE_MCP_JSON = REPO_ROOT / ".agents" / "mcp_config.json"
SERVER_SCRIPT = REPO_ROOT / "scripts" / "hindsight_mcp_server.py"
TUNNEL_SCRIPT = REPO_ROOT / "scripts" / "tunnel_hindsight.py"
LOCAL_CACHE_FILE = REPO_ROOT / ".workingdir" / "memory" / "hindsight-local-buffer.json"


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

    def test_json_rpc_tools_list_schemas(self) -> None:
        """Each tool declares its required arguments; a tool without one carries no `required` key."""
        res = call_mcp_server({"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}})
        schemas = {t["name"]: t["inputSchema"] for t in res["result"]["tools"]}

        assert schemas["hindsight_recall"]["required"] == ["query"]
        assert schemas["hindsight_retain"]["required"] == ["content"]
        for name in ("hindsight_reflect", "hindsight_status", "hindsight_list_banks"):
            assert "required" not in schemas[name], f"{name} declares a required argument"
        assert schemas["hindsight_status"] == {"type": "object", "properties": {}}
        with_bank = [name for name, schema in schemas.items() if "bank_id" in schema["properties"]]
        assert sorted(with_bank) == ["hindsight_recall", "hindsight_reflect", "hindsight_retain"]
        assert all(s["type"] == "object" for s in schemas.values())

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


class _EndedProcess:
    """A port-forward process that has already ended."""

    def wait(self) -> int:
        return 1

    def poll(self) -> int:
        return 1


class TestTunnelStartBound:
    """run_tunnel starts the port-forward a bounded number of times, then gives up."""

    @pytest.fixture
    def tunnel(self, monkeypatch: pytest.MonkeyPatch):
        spec = importlib.util.spec_from_file_location("tunnel_hindsight", TUNNEL_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
        monkeypatch.setattr(module, "check_health", lambda _port: False)
        return module

    def count_starts(self, tunnel, monkeypatch: pytest.MonkeyPatch, max_starts: int) -> tuple[int, int]:
        """Run the supervisor against a port-forward that always ends; return (status, starts)."""
        starts = []

        def fake_popen(cmd, **_kwargs):
            starts.append(cmd)
            # Ends a supervisor that ignores its bound instead of hanging the test run.
            # pytest.fail raises a BaseException, which run_tunnel's retry handler lets through.
            if len(starts) > max_starts + 2:
                pytest.fail("run_tunnel started the port-forward beyond its bound")
            return _EndedProcess()

        monkeypatch.setattr(tunnel.subprocess, "Popen", fake_popen)
        return tunnel.run_tunnel(8888, max_starts=max_starts), len(starts)

    def test_gives_up_after_the_bound(self, tunnel, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
        assert self.count_starts(tunnel, monkeypatch, 3) == (1, 3)
        assert "started 3 times; giving up" in capsys.readouterr().err

    def test_bound_of_one_starts_once(self, tunnel, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self.count_starts(tunnel, monkeypatch, 1) == (1, 1)

    def test_bound_of_zero_starts_nothing(self, tunnel, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self.count_starts(tunnel, monkeypatch, 0) == (1, 0)

    def test_default_bound_is_declared(self, tunnel) -> None:
        assert tunnel.MAX_STARTS == 7200
        assert tunnel.run_tunnel.__defaults__ == (tunnel.DEFAULT_PORT, tunnel.MAX_STARTS)


class _ScriptedConnection:
    """Connection that records every request and answers with the status the test sets."""

    sent: list[tuple[str, str, dict]] = []
    status = 200

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.target = (host, port, timeout)

    def request(self, method: str, path: str, body: bytes | None, headers: dict) -> None:
        self.sent.append((method, path, dict(headers)))

    def getresponse(self) -> _ScriptedConnection:
        return self

    def read(self) -> bytes:
        return b"{}" if 200 <= self.status < 300 else b'{"detail": "planted"}'

    def close(self) -> None:
        return None


def load_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, key: str | None):
    """Load the server with HINDSIGHT_API_KEY as given, a scripted backend and a buffer under tmp_path."""
    if key is None:
        monkeypatch.delenv("HINDSIGHT_API_KEY", raising=False)
    else:
        monkeypatch.setenv("HINDSIGHT_API_KEY", key)
    spec = importlib.util.spec_from_file_location("hindsight_mcp_server", SERVER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(http.client, "HTTPConnection", _ScriptedConnection)
    monkeypatch.setattr(_ScriptedConnection, "sent", [])
    monkeypatch.setattr(_ScriptedConnection, "status", 200)
    monkeypatch.setattr(module, "LOCAL_CACHE_DIR", tmp_path)
    monkeypatch.setattr(module, "LOCAL_CACHE_FILE", tmp_path / "buffer.json")
    return module


def buffered(bank_id: str, content: str) -> dict:
    return {"id": f"local-{content}", "bank_id": bank_id, "content": content, "context": "", "pending_sync": True}


class TestTenantKey:
    """Every request carries the tenant key from HINDSIGHT_API_KEY as a bearer token (issue #36)."""

    def test_key_is_sent_on_every_request(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        server = load_server(monkeypatch, tmp_path, "planted-key")
        server.tool_hindsight_status()
        server.tool_hindsight_retain("a fact")
        server.tool_hindsight_recall("a fact")
        server.tool_hindsight_reflect()
        server.tool_hindsight_list_banks()
        assert len(_ScriptedConnection.sent) == 5
        assert {sent[2].get("Authorization") for sent in _ScriptedConnection.sent} == {"Bearer planted-key"}

    @pytest.mark.parametrize("key", [None, "", "${HINDSIGHT_API_KEY}"])
    def test_missing_key_sends_no_header(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, key) -> None:
        server = load_server(monkeypatch, tmp_path, key)
        server.tool_hindsight_status()
        assert "Authorization" not in _ScriptedConnection.sent[0][2]

    def test_mcp_configs_declare_the_key_without_a_value(self) -> None:
        for path in (ROOT_MCP_JSON, WORKSPACE_MCP_JSON):
            env = json.loads(path.read_text(encoding="utf-8"))["mcpServers"]["hindsight"]["env"]
            assert env["HINDSIGHT_API_KEY"] == "${HINDSIGHT_API_KEY:-}", path


class TestStatusFailureModes:
    """hindsight_status names the actual failure instead of always blaming the port-forward (issue #36)."""

    def test_reachable_with_key_is_online(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        server = load_server(monkeypatch, tmp_path, "planted-key")
        assert server.tool_hindsight_status().startswith("Hindsight Status: ONLINE (HTTP 200)")

    @pytest.mark.parametrize("status", [401, 403])
    def test_rejected_key_is_unauthorised(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, status) -> None:
        server = load_server(monkeypatch, tmp_path, "wrong-key")
        monkeypatch.setattr(_ScriptedConnection, "status", status)
        text = server.tool_hindsight_status()
        assert text.startswith(f"Hindsight Status: UNAUTHORISED (HTTP {status})")
        assert "HINDSIGHT_API_KEY was rejected" in text
        assert "Port-forward" not in text

    def test_missing_key_is_unauthorised_and_names_the_variable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        server = load_server(monkeypatch, tmp_path, None)
        monkeypatch.setattr(_ScriptedConnection, "status", 401)
        text = server.tool_hindsight_status()
        assert text.startswith("Hindsight Status: UNAUTHORISED (HTTP 401)")
        assert "HINDSIGHT_API_KEY is not set" in text

    def test_server_error_is_not_blamed_on_the_tunnel_or_the_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        server = load_server(monkeypatch, tmp_path, "planted-key")
        monkeypatch.setattr(_ScriptedConnection, "status", 500)
        text = server.tool_hindsight_status()
        assert text.startswith("Hindsight Status: ERROR (HTTP 500)")
        assert "planted" in text
        assert "Port-forward" not in text and "HINDSIGHT_API_KEY" not in text

    def test_unreachable_names_the_port_forward(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        server = load_server(monkeypatch, tmp_path, "planted-key")
        monkeypatch.setattr(http.client, "HTTPConnection", _FailingConnection)
        monkeypatch.setattr(_FailingConnection, "close_error", None)
        text = server.tool_hindsight_status()
        assert text.startswith("Hindsight Status: UNREACHABLE (no HTTP response)")
        assert "Port-forward" in text

    def test_rejected_retain_says_why_it_buffered(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        server = load_server(monkeypatch, tmp_path, "wrong-key")
        monkeypatch.setattr(_ScriptedConnection, "status", 401)
        text = server.tool_hindsight_retain("a fact")
        assert "unauthorised (HTTP 401)" in text and "unreachable" not in text
        assert server.read_local_buffer()[0]["pending_sync"] is True


class TestBufferDrain:
    """The offline buffer drains on the first successful call, each entry into its own bank (issue #36)."""

    @pytest.mark.parametrize(
        "call",
        [
            lambda s: s.tool_hindsight_status(),
            lambda s: s.tool_hindsight_recall("query"),
            lambda s: s.tool_hindsight_reflect(),
            lambda s: s.tool_hindsight_list_banks(),
            lambda s: s.tool_hindsight_retain("new fact"),
        ],
    )
    def test_buffer_drains_on_first_success(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, call) -> None:
        server = load_server(monkeypatch, tmp_path, "planted-key")
        server.write_local_buffer([buffered("bank-a", "one"), buffered("bank b", "two")])
        call(server)
        retained = [path for method, path, _ in _ScriptedConnection.sent[1:] if method == "POST"]
        assert "/v1/default/banks/bank-a/retain" in retained
        assert "/v1/default/banks/bank%20b/retain" in retained
        assert [e["pending_sync"] for e in server.read_local_buffer()] == [False, False]
        call(server)
        drained = [path for method, path, _ in _ScriptedConnection.sent if path == "/v1/default/banks/bank-a/retain"]
        assert len(drained) == 1

    def test_empty_buffer_is_a_no_op(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        server = load_server(monkeypatch, tmp_path, "planted-key")
        server.tool_hindsight_status()
        assert len(_ScriptedConnection.sent) == 1
        assert not (tmp_path / "buffer.json").exists()

    def test_failed_call_keeps_the_buffer(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        server = load_server(monkeypatch, tmp_path, "wrong-key")
        server.write_local_buffer([buffered("bank-a", "one")])
        monkeypatch.setattr(_ScriptedConnection, "status", 401)
        server.tool_hindsight_recall("query")
        assert len(_ScriptedConnection.sent) == 1
        assert server.read_local_buffer()[0]["pending_sync"] is True

    def test_drain_stops_at_the_first_refused_entry(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        server = load_server(monkeypatch, tmp_path, "planted-key")
        server.write_local_buffer([buffered("bank-a", "one"), buffered("bank-a", "two")])
        monkeypatch.setattr(_ScriptedConnection, "status", 503)
        assert server.flush_local_pending() == 0
        assert len(_ScriptedConnection.sent) == 1
        assert [e["pending_sync"] for e in server.read_local_buffer()] == [True, True]
