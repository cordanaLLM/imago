#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Fail the Trivy job unless its report scanned exactly the tracked lockfiles.

Trivy passes on a tree in which it recognised no lockfile: a file whose name its
analyzers do not know is not scanned and not reported. The pinned pip lockfiles under
.github/requirements/ went unscanned that way until .github/trivy.yaml named them.
This check lists the tracked lockfiles with git, reads the JSON report of the scan and
fails when the two sets differ, so a lockfile Trivy skips turns the job red. It also
prints every finding of the report, because the JSON format replaces Trivy's table.

Usage: python3 -I tools/ci/trivy_coverage.py --report trivy-results.json
"""

import argparse
import json
import pathlib
import subprocess
import sys

# Pathspecs of the lockfiles the scan must cover; `*` also matches a slash.
LOCKFILES = ["go.mod", "*/go.mod", "*package-lock.json", ".github/requirements/*.txt", ".config/reuse/requirements.txt"]
LANGUAGE_CLASS = "lang-pkgs"
MAX_TARGETS = 256
GIT_TIMEOUT_S = 60


class CoverageError(Exception):
    """A report that does not cover the tracked lockfiles."""


def tracked_lockfiles(root: pathlib.Path) -> set[str]:
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-z", "--", *LOCKFILES],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as err:
        raise CoverageError(f"git ls-files did not complete: {err}") from err
    if listed.returncode != 0:
        raise CoverageError(f"git ls-files failed: {listed.stderr.strip()}")
    names = {name for name in listed.stdout.split("\0") if name}
    if not names or len(names) > MAX_TARGETS:
        raise CoverageError(f"{len(names)} tracked lockfiles, expected 1 to {MAX_TARGETS}")
    return names


def scanned_lockfiles(report: dict) -> set[str]:
    results = report.get("Results")
    if not isinstance(results, list) or len(results) > MAX_TARGETS:
        raise CoverageError("the report holds no Results list within the target bound")
    return {result["Target"] for result in results if result.get("Class") == LANGUAGE_CLASS}


def compare(expected: set[str], scanned: set[str]) -> None:
    missing = sorted(expected - scanned)
    extra = sorted(scanned - expected)
    if missing or extra:
        raise CoverageError(
            f"Trivy scanned {len(scanned)} lockfiles, {len(expected)} are tracked; "
            f"not scanned: {missing}; scanned but not expected: {extra}"
        )


def findings(report: dict) -> list[str]:
    lines = []
    for result in report.get("Results", []):
        for vuln in result.get("Vulnerabilities") or []:
            lines.append(
                f"{result['Target']}: {vuln.get('Severity')} {vuln.get('VulnerabilityID')} "
                f"{vuln.get('PkgName')} {vuln.get('InstalledVersion')} -> {vuln.get('FixedVersion')}"
            )
    return lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", required=True, type=pathlib.Path)
    parser.add_argument("--root", default=pathlib.Path.cwd(), type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        for line in findings(report):
            print(line, file=sys.stderr)
        expected = tracked_lockfiles(args.root)
        compare(expected, scanned_lockfiles(report))
    except (OSError, json.JSONDecodeError, CoverageError) as err:
        print(f"::error::Trivy coverage: {err}", file=sys.stderr)
        return 1
    print(f"Trivy scanned all {len(expected)} tracked lockfiles: {', '.join(sorted(expected))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
