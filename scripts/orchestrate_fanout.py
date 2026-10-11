#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""
Multi-Agent Fan-Out & Git Worktree Orchestrator for lusoris-cloud-images.
Enforces Rule 11 (Worktree Hygiene) by fanning out specialized background agents
into isolated git worktrees outside the checkout: the workstation's central
worktrees folder, two levels above the main checkout, or the folder that
IMAGO_WORKTREES_DIR names. Run it from the main checkout.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = "imago"
WORKTREES_ENV = "IMAGO_WORKTREES_DIR"


def worktrees_dir(repo_root: Path, override: str | None) -> Path:
    """Return the folder that holds the agent worktrees.

    The default is the worktrees folder beside the organisation folders, two
    levels above the main checkout. A nested worktree is read by scans that do
    not honour ignore rules, so the folder is never inside the checkout.
    """
    if override:
        return Path(override)
    return repo_root.parent.parent / "worktrees"


def worktree_path(role: str) -> Path:
    """Return the worktree of one agent role; the name carries the repository."""
    return WORKTREES_DIR / f"{REPOSITORY}-agent-{role}"


WORKTREES_DIR = worktrees_dir(REPO_ROOT, os.environ.get(WORKTREES_ENV))


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def list_worktrees() -> None:
    res = run_cmd(["git", "worktree", "list"])
    print(res.stdout.strip())


def spawn_agent_worktree(role: str, branch_name: str) -> Path:
    WORKTREES_DIR.mkdir(parents=True, exist_ok=True)
    target_path = worktree_path(role)

    if target_path.exists():
        print(f"Worktree for agent '{role}' already exists at {target_path}")
        return target_path

    print(f"Spawning isolated worktree for agent '{role}' on branch '{branch_name}'...")
    res = run_cmd(["git", "worktree", "add", "-b", branch_name, str(target_path), "HEAD"])
    if res.returncode != 0:
        # If branch already exists, checkout without -b
        res = run_cmd(["git", "worktree", "add", str(target_path), branch_name])
        if res.returncode != 0:
            raise RuntimeError(f"Failed to create worktree: {res.stderr}")

    print(f"  [OK] Agent '{role}' assigned worktree: {target_path}")
    return target_path


def remove_agent_worktree(role: str) -> None:
    target_path = worktree_path(role)
    if not target_path.exists():
        print(f"Worktree for agent '{role}' not found.")
        return

    print(f"Pruning worktree for agent '{role}'...")
    res = run_cmd(["git", "worktree", "remove", "--force", str(target_path)])
    if res.returncode == 0:
        print(f"  [OK] Removed worktree {target_path}")
    else:
        print(f"Warning: {res.stderr}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-Agent Worktree Fan-Out Orchestrator")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    subparsers.add_parser("list", help="List active worktrees")

    spawn_parser = subparsers.add_parser("spawn", help="Spawn an isolated worktree for an agent")
    spawn_parser.add_argument("role", help="Role identifier (e.g. infra-forge, security-compliance)")
    spawn_parser.add_argument("branch", help="Branch name for the worktree")

    prune_parser = subparsers.add_parser("prune", help="Prune an agent worktree")
    prune_parser.add_argument("role", help="Role identifier to prune")

    args = parser.parse_args()

    if args.subcommand == "list":
        list_worktrees()
    elif args.subcommand == "spawn":
        try:
            spawn_agent_worktree(args.role, args.branch)
        except RuntimeError as err:
            print(err, file=sys.stderr)
            sys.exit(1)
    elif args.subcommand == "prune":
        remove_agent_worktree(args.role)


if __name__ == "__main__":
    main()
