#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Prove that the local Git hooks refuse planted defects (issue #80).

The pre-commit hooks of lefthook.yml run through the pinned Praetor engine, which no CI job
installs, so CI cannot show them refusing anything. This tool clones the committed tree into
a temporary directory, installs the hooks there and runs the three cases of issue #80:

  positive  `compile-context --verify` and `audit --offline` exit 0 on the fresh clone;
  negative  a commit with a hand edit to CLAUDE.md is refused as out of sync with AGENTS.md;
  boundary  a commit that adds a banned eval call to a touched file is refused as HISS-08,
            and the recorded baseline is unchanged afterwards.

A refusal counts only when the commit exits non-zero, HEAD does not move and the output
names the expected reason. The checkout this runs from is never changed. The clone takes
the origin URL and default branch of the checkout, because the audit reads both, and its push
URL is disabled so nothing leaves it.

Usage:
  python3 -I tools/ci/prove_hooks.py        (or: make prove-hooks)
"""

import argparse
import hashlib
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
STEP_TIMEOUT_S = 600
ENGINE = ["sh", ".config/lefthook/engine.sh"]
BASELINE = ".standards-baseline.json"
CONTEXT_FILE = "CLAUDE.md"
CONTEXT_REASON = "CLAUDE.md is out of sync with AGENTS.md"
PLANT_FILE = "tools/ci/trivy_coverage.py"
PLANT_REASON = f"[HISS-08] {PLANT_FILE}"
# The planted call is assembled at run time, so this file holds no infraction.
PLANT = "\n\ndef planted(text):\n    return ev" + "al(text)\n"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class ProofError(Exception):
    """A hook that did not behave as the case requires."""


def run(args: list[str], cwd: pathlib.Path) -> tuple[int, str]:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=STEP_TIMEOUT_S, check=False)
    return result.returncode, ANSI.sub("", result.stdout + result.stderr)


def must(args: list[str], cwd: pathlib.Path) -> str:
    status, output = run(args, cwd)
    if status != 0:
        raise ProofError(f"{' '.join(args[:3])} exited {status}: {output.strip()[-200:]}")
    return output.strip()


def head(clone: pathlib.Path) -> str:
    return must(["git", "rev-parse", "HEAD"], clone)


def make_clone(clone: pathlib.Path) -> None:
    """Clone the checkout, take its origin and default branch, and install the hooks."""
    url = must(["git", "remote", "get-url", "origin"], ROOT)
    default = must(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], ROOT)
    must(["git", "clone", "--quiet", str(ROOT), str(clone)], ROOT)
    must(["git", "remote", "set-url", "origin", url], clone)
    must(["git", "remote", "set-url", "--push", "origin", "no-push"], clone)
    must(["git", "symbolic-ref", "refs/remotes/origin/HEAD", f"refs/remotes/{default}"], clone)
    must(["lefthook", "install"], clone)


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expect_pass(name: str, result: tuple[int, str]) -> None:
    status, output = result
    if status != 0:
        failures = [line.strip() for line in output.splitlines() if "[FAIL]" in line]
        raise ProofError(f"{name} exited {status} on the fresh clone: {'; '.join(failures[-3:]) or 'no [FAIL] line'}")


def expect_refusal(name: str, status: int, output: str, reason: str, heads: tuple[str, str]) -> None:
    """Raise unless the commit failed, left HEAD in place and named the reason."""
    if status == 0:
        raise ProofError(f"{name}: the commit was accepted")
    if heads[0] != heads[1]:
        raise ProofError(f"{name}: HEAD moved from {heads[0]} to {heads[1]}")
    if reason not in output:
        raise ProofError(f"{name}: refused without naming {reason!r}")


def planted_commit(clone: pathlib.Path, path: str, text: str, message: str) -> tuple[int, str, tuple[str, str]]:
    """Append text to path, try to commit it, then restore the file."""
    before = head(clone)
    with (clone / path).open("a", encoding="utf-8") as handle:
        handle.write(text)
    must(["git", "add", "--", path], clone)
    status, output = run(["git", "commit", "--quiet", "--signoff", "--no-gpg-sign", "-m", message], clone)
    after = head(clone)
    must(["git", "reset", "--quiet", "--hard", before], clone)
    return status, output, (before, after)


def prove(clone: pathlib.Path) -> list[str]:
    expect_pass("compile-context --verify", run([*ENGINE, "compile-context", "--verify"], clone))
    expect_pass("audit --offline", run([*ENGINE, "audit", "--offline"], clone))
    status, output, heads = planted_commit(clone, CONTEXT_FILE, "\nPlanted hand edit.\n", "test: planted hand edit")
    expect_refusal("negative", status, output, CONTEXT_REASON, heads)
    baseline = digest(clone / BASELINE)
    status, output, heads = planted_commit(clone, PLANT_FILE, PLANT, "test: planted infraction")
    expect_refusal("boundary", status, output, PLANT_REASON, heads)
    if digest(clone / BASELINE) != baseline:
        raise ProofError(f"boundary: {BASELINE} changed")
    return [
        "positive: compile-context --verify and audit --offline exit 0",
        f"negative: hand edit to {CONTEXT_FILE} refused ({CONTEXT_REASON})",
        f"boundary: planted eval in {PLANT_FILE} refused ({PLANT_REASON}), {BASELINE} unchanged",
    ]


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args(argv)
    try:
        with tempfile.TemporaryDirectory(prefix="imago-hooks-") as scratch:
            clone = pathlib.Path(scratch) / "clone"
            make_clone(clone)
            print(f"clone of {head(clone)[:12]}")
            for line in prove(clone):
                print(line)
    except (ProofError, OSError, subprocess.TimeoutExpired) as error:
        print(f"::error::hook proof failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
