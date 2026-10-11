# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""
Automated verification suite for Google AI Studio Managed Agents and Antigravity fleet.
Asserts agent definitions, hooks configuration, and privacy guardrails.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / ".agents" / "managed-agents"
HOOKS_JSON = REPO_ROOT / ".agents" / "hooks.json"
GUARD_PRIVACY_SCRIPT = REPO_ROOT / ".agents" / "hooks-scripts" / "guard_privacy.py"

EXPECTED_AGENTS = {
    "lusoris-infra-forge",
    "lusoris-security-compliance",
    "lusoris-container-k8s",
    "lusoris-qa-gatekeeper",
    "lusoris-deep-researcher",
    "lusoris-docs-architect",
}


class TestAgentsFleetIntegrity:
    """Validates declarative configuration for AI Studio & Antigravity Managed Agents."""

    def test_expected_agents_present(self) -> None:
        assert AGENTS_DIR.is_dir(), f"Missing {AGENTS_DIR}"
        discovered = set()
        for d in AGENTS_DIR.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                agent_json = d / "agent.json"
                agents_md = d / "AGENTS.md"
                assert agent_json.is_file(), f"Missing agent.json in {d}"
                assert agents_md.is_file(), f"Missing AGENTS.md in {d}"

                with open(agent_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                discovered.add(data.get("id"))

        assert discovered == EXPECTED_AGENTS, (
            f"Expected agents {EXPECTED_AGENTS}, found {discovered}"
        )

    def test_agent_json_schemas(self) -> None:
        for d in AGENTS_DIR.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                with open(d / "agent.json", "r", encoding="utf-8") as f:
                    data = json.load(f)

                assert "id" in data
                assert "base_agent" in data
                assert "description" in data
                assert "agent_config" in data
                assert "tools" in data
                assert isinstance(data["tools"], list)
                assert len(data["tools"]) > 0

    def test_hooks_configuration_validity(self) -> None:
        assert HOOKS_JSON.is_file(), f"Missing {HOOKS_JSON}"
        with open(HOOKS_JSON, "r", encoding="utf-8") as f:
            hooks_data = json.load(f)

        assert "events" in hooks_data
        for event in hooks_data["events"]:
            assert "event" in event
            assert "tools" in event
            assert "hooks" in event
            for hook in event["hooks"]:
                assert hook.get("type") in ("command", "http")

    def test_guard_privacy_hook_behavior(self) -> None:
        assert GUARD_PRIVACY_SCRIPT.is_file()

        # Clean payload should exit 0
        clean_input = json.dumps({"arguments": {"content": "server: 192.0.2.1\nname: test"}})
        res_clean = subprocess.run(
            [sys.executable, str(GUARD_PRIVACY_SCRIPT)],
            input=clean_input,
            capture_output=True,
            text=True,
        )
        assert res_clean.returncode == 0

        # RFC 1918 payload should exit 1
        leak_input = json.dumps({"arguments": {"content": "gateway: 192.168.1.1"}})
        res_leak = subprocess.run(
            [sys.executable, str(GUARD_PRIVACY_SCRIPT)],
            input=leak_input,
            capture_output=True,
            text=True,
        )
        assert res_leak.returncode == 1
        assert "SECURITY VIOLATION" in res_leak.stderr

    def test_skills_progressive_disclosure_structure(self) -> None:
        """Verify .agents/skills/ adhere to 3-layer progressive disclosure standard."""
        skills_dir = REPO_ROOT / ".agents" / "skills"
        assert skills_dir.is_dir(), f"Missing {skills_dir}"

        discovered_skills = [d for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        assert len(discovered_skills) >= 8, f"Expected at least 8 skills, found {len(discovered_skills)}"

        for skill_dir in discovered_skills:
            skill_md = skill_dir / "SKILL.md"
            assert skill_md.is_file(), f"Missing SKILL.md in {skill_dir.name}"

            content = skill_md.read_text(encoding="utf-8")
            assert content.startswith("---"), f"SKILL.md in {skill_dir.name} missing YAML frontmatter opening"
            parts = content.split("---", 2)
            assert len(parts) >= 3, f"SKILL.md in {skill_dir.name} malformed frontmatter"

            frontmatter = parts[1]
            assert "name:" in frontmatter, f"SKILL.md in {skill_dir.name} missing 'name'"
            assert "description:" in frontmatter, f"SKILL.md in {skill_dir.name} missing 'description'"

            # If references are defined, assert each referenced file exists
            if "references:" in frontmatter:
                for line in frontmatter.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("- ") and stripped.endswith(".md"):
                        ref_rel = stripped[2:].strip().strip("'\"")
                        ref_file = skill_dir / ref_rel
                        assert ref_file.is_file(), f"Referenced file {ref_rel} not found in {skill_dir}"

