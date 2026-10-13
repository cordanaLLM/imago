#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Fail a scanner job unless its scanner refuses a planted finding.

A scanner that passes the repository proves nothing on its own: a broken rule, a
config file it does not read or a flag that hides findings pass as well. Before the
real scan, each job runs this canary. It writes planted findings into a temporary
directory outside the checkout, runs the scanner there with the repository's own
configuration and fails unless the scanner exits non-zero and reports every planted
rule. The planted text is assembled at run time, so the repository holds no finding.

Usage:
  python3 -I tools/ci/scanner_canary.py gitleaks --binary /tmp/gitleaks
  python3 -I tools/ci/scanner_canary.py semgrep --binary semgrep
"""

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SCAN_TIMEOUT_S = 600
MAX_FINDINGS = 1024

# Rule id -> (file name, planted content). Split literals keep the source clean.
GITLEAKS_PLANTS = {
    "no-cosign-private-key": (
        "cosign.key",
        "-----BEGIN ENCRYPTED " + "COSIGN PRIVATE KEY-----\nAAAA\n",
    ),
    "github-pat": ("token.env", "GITHUB_TOKEN=gh" + "p_" + "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3z5A\n"),
}
SEMGREP_PLANTS = {
    "python.lang.security.audit.eval-detected.eval-detected": (
        "plant.py",
        "import sys\n\nprint(ev" + "al(sys.argv[1]))\n",
    ),
}


class CanaryError(Exception):
    """A scanner that did not refuse the planted findings."""


def plant(directory: pathlib.Path, plants: dict[str, tuple[str, str]]) -> None:
    for name, content in plants.values():
        (directory / name).write_text(content, encoding="utf-8")


def gitleaks_command(binary: str, target: pathlib.Path, report: pathlib.Path) -> list[str]:
    return [
        binary, "dir", "--no-banner", "--redact", "--exit-code", "1",
        "--config", str(ROOT / ".gitleaks.toml"),
        "--report-format", "json", "--report-path", str(report), str(target),
    ]  # fmt: skip


def semgrep_command(binary: str, target: pathlib.Path, report: pathlib.Path) -> list[str]:
    return [
        binary, "--error", "--metrics", "off", "--config", "p/ci", "--config", "p/security-audit",
        "--json", "--output", str(report), str(target),
    ]  # fmt: skip


def gitleaks_rules(report: object) -> set[str]:
    if not isinstance(report, list):
        raise CanaryError("gitleaks report is not a JSON list")
    return {str(item.get("RuleID", "")) for item in report[:MAX_FINDINGS] if isinstance(item, dict)}


def semgrep_rules(report: object) -> set[str]:
    results = report.get("results") if isinstance(report, dict) else None
    if not isinstance(results, list):
        raise CanaryError("semgrep report has no results list")
    return {str(item.get("check_id", "")) for item in results[:MAX_FINDINGS] if isinstance(item, dict)}


SCANNERS = {
    "gitleaks": (GITLEAKS_PLANTS, gitleaks_command, gitleaks_rules),
    "semgrep": (SEMGREP_PLANTS, semgrep_command, semgrep_rules),
}


def check(scanner: str, returncode: int, found: set[str]) -> None:
    """Raise unless the scanner failed and reported every planted rule."""
    plants = SCANNERS[scanner][0]
    missing = sorted(set(plants) - found)
    if returncode == 0:
        raise CanaryError(f"{scanner} exited 0 on the planted findings")
    if missing:
        raise CanaryError(f"{scanner} exited {returncode} but did not report: {', '.join(missing)}")


def run(scanner: str, binary: str) -> None:
    plants, command, rules = SCANNERS[scanner]
    with tempfile.TemporaryDirectory(prefix=f"{scanner}-canary-") as scratch:
        target = pathlib.Path(scratch) / "plant"
        target.mkdir()
        plant(target, plants)
        report = pathlib.Path(scratch) / "report.json"
        result = subprocess.run(command(binary, target, report), timeout=SCAN_TIMEOUT_S, check=False)
        if result.returncode not in (0, 1):
            raise CanaryError(f"{scanner} could not scan (exit {result.returncode})")
        if not report.is_file():
            raise CanaryError(f"{scanner} wrote no report")
        found = rules(json.loads(report.read_text(encoding="utf-8")))
    check(scanner, result.returncode, found)
    print(f"{scanner} canary: exit {result.returncode}, refused {', '.join(sorted(plants))}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scanner", choices=sorted(SCANNERS))
    parser.add_argument("--binary", required=True, help="scanner executable to run")
    args = parser.parse_args(argv)
    try:
        run(args.scanner, args.binary)
    except (CanaryError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"::error::{args.scanner} canary failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
