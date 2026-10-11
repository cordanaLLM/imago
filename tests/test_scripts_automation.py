# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""
Unit and integration tests for repository automation scripts:
- scripts/manage_aistudio_agents.py
- scripts/orchestrate_fanout.py
- .agents/hooks-scripts/guard_privacy.py
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import scripts.manage_aistudio_agents as manage_agents
import scripts.orchestrate_fanout as orchestrate


# ---------------------------------------------------------------------------
# Tests for scripts/manage_aistudio_agents.py
# ---------------------------------------------------------------------------


class TestManageAIStudioAgents:
    """Test suite for AI Studio agent fleet configuration and validation."""

    def test_load_agent_spec_success(self, tmp_path: Path):
        agent_dir = tmp_path / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "agent.json").write_text(
            json.dumps({"id": "agent-test", "description": "Test agent"}),
            encoding="utf-8",
        )
        (agent_dir / "AGENTS.md").write_text("System instructions for test.", encoding="utf-8")

        spec = manage_agents.load_agent_spec(agent_dir)
        assert spec["id"] == "agent-test"
        assert spec["description"] == "Test agent"
        assert spec["system_instruction"] == "System instructions for test."

    def test_load_agent_spec_missing_json(self, tmp_path: Path):
        agent_dir = tmp_path / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENTS.md").write_text("Instruction", encoding="utf-8")

        with pytest.raises(FileNotFoundError, match="Missing agent.json"):
            manage_agents.load_agent_spec(agent_dir)

    def test_load_agent_spec_missing_md(self, tmp_path: Path):
        agent_dir = tmp_path / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "agent.json").write_text("{}", encoding="utf-8")

        with pytest.raises(FileNotFoundError, match="Missing AGENTS.md"):
            manage_agents.load_agent_spec(agent_dir)

    def test_build_agent_payload_defaults(self):
        spec = {"id": "agent-default"}
        payload = manage_agents.build_agent_payload(spec)

        assert payload["id"] == "agent-default"
        assert payload["base_agent"] == manage_agents.BASE_AGENT
        assert payload["agent_config"]["model"] == manage_agents.DEFAULT_MODEL
        assert payload["tools"] == []
        assert payload["base_environment"]["type"] == "remote"

        # Check network allowlist contains expected domains
        allowlist = [item["domain"] for item in payload["base_environment"]["network"]["allowlist"]]
        assert {"github.com", "registry.k8s.io"} <= set(allowlist)

    def test_validate_agents_fleet_existing_repo(self):
        """Validates all agents committed to .agents/managed-agents/ conform to spec."""
        payloads = manage_agents.validate_agents_fleet()
        assert len(payloads) > 0

        for payload in payloads:
            assert payload["id"]
            assert payload["system_instruction"]
            assert "agent_config" in payload
            assert payload["base_environment"]

    def test_validate_agents_fleet_missing_dir(self, tmp_path: Path, monkeypatch):
        missing_dir = tmp_path / "nonexistent"
        monkeypatch.setattr(manage_agents, "AGENTS_DIR", missing_dir)

        with pytest.raises(FileNotFoundError, match="Agents directory not found"):
            manage_agents.validate_agents_fleet()

    def test_register_agents_dry_run(self, capsys):
        payloads = [
            {
                "id": "agent-test",
                "base_agent": "antigravity",
                "agent_config": {"model": "gemini-3.8-flash"},
                "tools": [{"type": "code_exec"}],
            }
        ]
        manage_agents.register_agents(payloads, dry_run=True)
        captured = capsys.readouterr()
        assert "Discovered 1 agents" in captured.out
        assert "agent-test" in captured.out
        assert "[DRY RUN]" in captured.out

    def test_register_agents_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        payloads = [{"id": "agent-test"}]

        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            manage_agents.register_agents(payloads, dry_run=False)

    def test_register_agents_live_mock(self, monkeypatch, capsys):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-mock")
        payloads = [
            {
                "id": "agent-1",
                "base_agent": "antigravity",
                "agent_config": {"model": "gemini-3.8-flash"},
                "tools": [],
            }
        ]

        mock_genai = MagicMock()
        mock_client = MagicMock()
        mock_agent = MagicMock()
        mock_agent.id = "agent-1-registered"
        mock_client.agents.create.return_value = mock_agent
        mock_genai.Client.return_value = mock_client

        with patch.dict(sys.modules, {"google": MagicMock(), "google.genai": mock_genai}):
            manage_agents.register_agents(payloads, dry_run=False)

        captured = capsys.readouterr()
        assert "Registering agent-1 on Google AI Studio..." in captured.out


# ---------------------------------------------------------------------------
# Tests for scripts/orchestrate_fanout.py
# ---------------------------------------------------------------------------


class TestOrchestrateFanout:
    """Test suite for git worktree fan-out orchestration."""

    def test_worktrees_dir_default_is_outside_the_checkout(self):
        root = Path("/srv/dev/organisation/imago")
        assert orchestrate.worktrees_dir(root, None) == Path("/srv/dev/worktrees")
        assert orchestrate.worktrees_dir(root, "") == Path("/srv/dev/worktrees")

    def test_worktrees_dir_override_wins(self):
        root = Path("/srv/dev/organisation/imago")
        assert orchestrate.worktrees_dir(root, "/srv/elsewhere") == Path("/srv/elsewhere")

    def test_configured_worktrees_dir_is_never_inside_the_checkout(self):
        assert orchestrate.REPO_ROOT not in orchestrate.WORKTREES_DIR.parents
        assert orchestrate.WORKTREES_DIR != orchestrate.REPO_ROOT

    def test_worktree_name_carries_the_repository(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(orchestrate, "WORKTREES_DIR", tmp_path)
        assert orchestrate.worktree_path("docs") == tmp_path / "imago-agent-docs"

    def test_spawn_worktree_already_exists(self, tmp_path: Path, monkeypatch, capsys):
        monkeypatch.setattr(orchestrate, "WORKTREES_DIR", tmp_path)
        role = "infra"
        existing = tmp_path / f"imago-agent-{role}"
        existing.mkdir(parents=True)

        res = orchestrate.spawn_agent_worktree(role, "feat/test")
        assert res == existing
        captured = capsys.readouterr()
        assert "already exists" in captured.out

    def test_spawn_worktree_success(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(orchestrate, "WORKTREES_DIR", tmp_path)
        role = "security"

        mock_res = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")
        with patch.object(orchestrate, "run_cmd", return_value=mock_res) as mock_run:
            res = orchestrate.spawn_agent_worktree(role, "feat/security-branch")
            assert res == tmp_path / f"imago-agent-{role}"
            mock_run.assert_called_once()
            assert "feat/security-branch" in mock_run.call_args[0][0]

    def test_spawn_worktree_fallback_existing_branch(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(orchestrate, "WORKTREES_DIR", tmp_path)
        role = "docs"

        fail_res = subprocess.CompletedProcess(args=["git"], returncode=128, stdout="", stderr="branch exists")
        succ_res = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")

        with patch.object(orchestrate, "run_cmd", side_effect=[fail_res, succ_res]) as mock_run:
            res = orchestrate.spawn_agent_worktree(role, "feat/docs-branch")
            assert res == tmp_path / f"imago-agent-{role}"
            assert mock_run.call_count == 2

    def test_remove_worktree_not_found(self, tmp_path: Path, monkeypatch, capsys):
        monkeypatch.setattr(orchestrate, "WORKTREES_DIR", tmp_path)
        orchestrate.remove_agent_worktree("nonexistent")
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_remove_worktree_success(self, tmp_path: Path, monkeypatch, capsys):
        monkeypatch.setattr(orchestrate, "WORKTREES_DIR", tmp_path)
        role = "test"
        target = tmp_path / f"imago-agent-{role}"
        target.mkdir()

        mock_res = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")
        with patch.object(orchestrate, "run_cmd", return_value=mock_res):
            orchestrate.remove_agent_worktree(role)

        captured = capsys.readouterr()
        assert "Removed worktree" in captured.out

    def test_list_worktrees(self, capsys):
        mock_res = subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout="/path/main [main]\n/path/worktree [branch]", stderr=""
        )
        with patch.object(orchestrate, "run_cmd", return_value=mock_res):
            orchestrate.list_worktrees()

        captured = capsys.readouterr()
        assert "/path/main [main]" in captured.out


# ---------------------------------------------------------------------------
# Tests for .agents/hooks-scripts/guard_privacy.py
# ---------------------------------------------------------------------------


class TestGuardPrivacyHook:
    """Test suite for the Zero-Leak privacy pre-tool hook."""

    @pytest.fixture(autouse=True)
    def import_guard_privacy(self):
        hook_path = Path(__file__).resolve().parent.parent / ".agents" / "hooks-scripts" / "guard_privacy.py"
        import importlib.util

        spec = importlib.util.spec_from_file_location("guard_privacy", hook_path)
        self.guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.guard)

    @pytest.mark.parametrize(
        "private_ip",
        [
            "10.0.0.1",
            "10.254.1.5",
            "192.168.1.1",
            "192.168.100.254",
            "172.16.0.10",
            "172.24.1.1",
            "172.31.255.254",
        ],
    )
    def test_rfc1918_blocked(self, private_ip: str):
        payload = f"Setting upstream DNS server to {private_ip} in config"
        violation = self.guard.inspect_payload(payload)
        assert violation is not None
        assert private_ip in violation

    @pytest.mark.parametrize(
        "benign_ip",
        [
            "192.0.2.1",       # RFC 5737 TEST-NET-1
            "198.51.100.25",   # RFC 5737 TEST-NET-2
            "203.0.113.10",    # RFC 5737 TEST-NET-3
            "1.1.1.1",         # Cloudflare Public
            "8.8.8.8",         # Google Public
            "192.170.1.1",     # Outside 192.168.0.0/16
            "172.15.0.1",      # Below 172.16.0.0/12
            "172.32.0.1",      # Above 172.31.255.255
        ],
    )
    def test_benign_ips_allowed(self, benign_ip: str):
        payload = f"Configuring public DNS server {benign_ip}"
        assert self.guard.inspect_payload(payload) is None

    def test_workstation_paths_blocked(self):
        violation = self.guard.inspect_payload("Writing output to /home/developer/secrets.txt")
        assert violation is not None
        assert "Local workstation path" in violation

        violation = self.guard.inspect_payload(r"Target file is C:\Users\user1\dev\project\file.py")
        assert violation is not None
        assert "Local workstation path" in violation

    def test_hook_main_stdin_clean(self, monkeypatch):
        clean_input = json.dumps({"arguments": {"content": "server 192.0.2.10:123"}})
        monkeypatch.setattr("sys.stdin", io.StringIO(clean_input))

        with pytest.raises(SystemExit) as exc:
            self.guard.main()
        assert exc.value.code == 0

    def test_hook_main_stdin_violation(self, monkeypatch):
        bad_input = json.dumps({"arguments": {"content": "nameserver 10.0.1.5"}})
        monkeypatch.setattr("sys.stdin", io.StringIO(bad_input))

        with pytest.raises(SystemExit) as exc:
            self.guard.main()
        assert exc.value.code == 1

    def test_hook_main_empty_stdin(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO(""))

        with pytest.raises(SystemExit) as exc:
            self.guard.main()
        assert exc.value.code == 0
