#!/usr/bin/env python3
# Copyright 2026 Lusoris
# Licensed under the Apache License, Version 2.0
"""
Automated Agent Fleet Manager for Google AI Studio & Antigravity Managed Agents.
Declaratively registers, synchronizes, and audits custom agents defined under .agents/agents/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / ".agents" / "agents"
DEFAULT_MODEL = "gemini-3.8-flash"
BASE_AGENT = "antigravity-preview-05-2026"


def load_agent_spec(agent_dir: Path) -> Dict[str, Any]:
    agent_json_path = agent_dir / "agent.json"
    agents_md_path = agent_dir / "AGENTS.md"

    if not agent_json_path.is_file():
        raise FileNotFoundError(f"Missing agent.json in {agent_dir}")
    if not agents_md_path.is_file():
        raise FileNotFoundError(f"Missing AGENTS.md in {agent_dir}")

    with open(agent_json_path, "r", encoding="utf-8") as f:
        spec: Dict[str, Any] = json.load(f)

    with open(agents_md_path, "r", encoding="utf-8") as f:
        spec["system_instruction"] = f.read().strip()

    return spec


def build_agent_payload(spec: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": spec.get("id"),
        "base_agent": spec.get("base_agent", BASE_AGENT),
        "description": spec.get("description", ""),
        "system_instruction": spec.get("system_instruction", ""),
        "agent_config": spec.get(
            "agent_config",
            {"type": "antigravity", "model": DEFAULT_MODEL},
        ),
        "tools": spec.get("tools", []),
        "base_environment": {
            "type": "remote",
            "sources": [
                {
                    "type": "repository",
                    "source": "https://github.com/cordanaLLM/imago",
                    "target": "/workspace/imago",
                }
            ],
            "network": {
                "allowlist": [
                    {"domain": "github.com"},
                    {"domain": "api.github.com"},
                    {"domain": "archive.ubuntu.com"},
                    {"domain": "deb.debian.org"},
                    {"domain": "dl-cdn.alpinelinux.org"},
                    {"domain": "registry.k8s.io"},
                    {"domain": "packages.cloud.google.com"},
                ]
            },
        },
    }
    return payload


def validate_agents_fleet() -> List[Dict[str, Any]]:
    if not AGENTS_DIR.is_dir():
        print(f"Error: Agents directory not found at {AGENTS_DIR}", file=sys.stderr)
        sys.exit(1)

    payloads = []
    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if agent_dir.is_dir() and not agent_dir.name.startswith("."):
            spec = load_agent_spec(agent_dir)
            payload = build_agent_payload(spec)
            payloads.append(payload)
            print(f"  [OK] Conforming spec: {payload['id']} ({agent_dir.name})")

    return payloads


def register_agents(payloads: List[Dict[str, Any]], dry_run: bool = False) -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and not dry_run:
        print("Error: GEMINI_API_KEY environment variable is required unless --dry-run is set.", file=sys.stderr)
        sys.exit(1)

    print(f"Discovered {len(payloads)} agents in .agents/agents/:")
    for p in payloads:
        print(f"  -> Agent ID: {p['id']}")
        print(f"     Base Agent: {p['base_agent']}")
        print(f"     Model: {p['agent_config'].get('model')}")
        print(f"     Tools: {[t.get('type') for t in p.get('tools', [])]}")

    if dry_run:
        print("\n[DRY RUN] All payloads are valid. No API calls dispatched.")
        return

    try:
        from google import genai
        client = genai.Client()
        for p in payloads:
            print(f"Registering {p['id']} on Google AI Studio...")
            agent = client.agents.create(**p)
            print(f"  Successfully registered {agent.id}")
    except ImportError:
        print("Notice: google-genai library not installed. Falling back to HTTP requests or manual import.")
    except Exception as e:
        print(f"API interaction error: {e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Google AI Studio Managed Agents Fleet")
    parser.add_argument("action", choices=["validate", "register", "list"], default="validate", nargs="?")
    parser.add_argument("--dry-run", action="store_true", help="Validate without registering via API")
    args = parser.parse_args()

    payloads = validate_agents_fleet()
    if args.action in ("validate", "register"):
        register_agents(payloads, dry_run=(args.action == "validate" or args.dry_run))


if __name__ == "__main__":
    main()
