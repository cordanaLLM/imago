#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Fail unless every action reference is pinned to a real commit of its repository.

The check runs zizmor online with three audits, named as in the zizmor 1.30.1 audit
documentation (https://docs.zizmor.sh/audits/):

- `unpinned-uses`: a `uses:` clause pinned to a tag or branch instead of a commit;
- `impostor-commit`: a commit that is not reachable from the named repository (it lives
  in a fork of it, or nowhere);
- `ref-version-mismatch`: a version comment that names another release than the
  pinned commit, or no release.

The check fails closed. It refuses to run without a GitHub token or with zizmor's
offline switches set, because `impostor-commit` needs the API. It loads no zizmor
configuration and honours no ignore comments, so the repository cannot relax a rule.
Before the real scan it audits a planted workflow outside the checkout and fails unless
each named audit reports it: an audit the pinned zizmor no longer knows, or one that
no longer reaches the API, turns the job red instead of green.

Usage:
  python3 -I tools/ci/action_pins.py --binary zizmor .github/workflows
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile

AUDITS = ("impostor-commit", "ref-version-mismatch", "unpinned-uses")
TOKEN_ENV = ("GH_TOKEN", "GITHUB_TOKEN", "ZIZMOR_GITHUB_TOKEN")
OFFLINE_ENV = ("ZIZMOR_OFFLINE", "ZIZMOR_NO_ONLINE_AUDITS")
# zizmor exits 0 without findings and 11 to 14 by the highest severity it found.
CLEAN_EXIT = 0
FINDINGS_EXIT = range(11, 15)
SCAN_TIMEOUT_S = 600
MAX_FINDINGS = 4096

# One planted step per audit. The checkout commit is v7.0.1 under a v6.0.0 comment,
# the setup-go commit exists nowhere, and the last step uses a tag.
PLANT = """\
name: plant
on: push
permissions: {}
jobs:
  plant:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v6.0.0
        with:
          persist-credentials: false
      - uses: actions/setup-go@0000000000000000000000000000000000000001 # v7.0.0
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
"""


class PinCheckError(Exception):
    """The check could not establish a trustworthy result."""


def preflight(env: dict[str, str]) -> None:
    """Raise unless zizmor can run its online audits."""
    if not any(env.get(name) for name in TOKEN_ENV):
        raise PinCheckError(f"no GitHub token in {', '.join(TOKEN_ENV)}; impostor-commit needs the API")
    switched = [name for name in OFFLINE_ENV if env.get(name)]
    if switched:
        raise PinCheckError(f"{', '.join(switched)} would disable the online audits")


def command(binary: str, target: pathlib.Path) -> list[str]:
    return [
        binary, "--format", "json", "--no-config", "--no-ignores", "--no-progress",
        "--persona", "pedantic", "--strict-collection", str(target),
    ]  # fmt: skip


def scan(binary: str, target: pathlib.Path) -> list[dict]:
    """Run zizmor on the target and return its findings."""
    result = subprocess.run(
        command(binary, target), capture_output=True, text=True, timeout=SCAN_TIMEOUT_S, check=False
    )
    if result.returncode != CLEAN_EXIT and result.returncode not in FINDINGS_EXIT:
        tail = result.stderr.strip().splitlines()[-3:]
        raise PinCheckError(f"zizmor could not audit {target} (exit {result.returncode}): {' | '.join(tail)}")
    findings = json.loads(result.stdout)
    if not isinstance(findings, list):
        raise PinCheckError("zizmor output is not a JSON list")
    return [item for item in findings[:MAX_FINDINGS] if isinstance(item, dict)]


def location(finding: dict) -> tuple[str, int]:
    """Return the file and the 1-based line of the first location of a finding."""
    first = (finding.get("locations") or [{}])[0]
    path = first.get("symbolic", {}).get("key", {}).get("Local", {}).get("verbatim_path", "?")
    row = first.get("concrete", {}).get("location", {}).get("start_point", {}).get("row", -1)
    return str(path), int(row) + 1


def pin_findings(findings: list[dict]) -> list[tuple[str, str, int]]:
    """Keep the findings of the named audits as (audit, file, line)."""
    return sorted((str(item["ident"]), *location(item)) for item in findings if item.get("ident") in AUDITS)


def canary(binary: str) -> None:
    """Raise unless every named audit reports the planted workflow."""
    with tempfile.TemporaryDirectory(prefix="action-pins-canary-") as scratch:
        workflows = pathlib.Path(scratch) / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "plant.yml").write_text(PLANT, encoding="utf-8")
        found = {audit for audit, _path, _line in pin_findings(scan(binary, pathlib.Path(scratch)))}
    missing = sorted(set(AUDITS) - found)
    if missing:
        raise PinCheckError(f"zizmor did not report the planted workflow for: {', '.join(missing)}")
    print(f"action pin canary: refused {', '.join(AUDITS)}")


def run(binary: str, target: pathlib.Path) -> int:
    preflight(dict(os.environ))
    canary(binary)
    found = pin_findings(scan(binary, target))
    for audit, path, line in found:
        print(f"::error file={path},line={line}::{audit}: pin this action to a release commit of its repository")
    print(f"action pin check: {len(found)} finding(s) in {target}")
    return 1 if found else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--binary", required=True, help="zizmor executable to run")
    parser.add_argument("target", type=pathlib.Path, help="workflow directory to audit")
    args = parser.parse_args(argv)
    try:
        return run(args.binary, args.target)
    except (PinCheckError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        print(f"::error::action pin check failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
