# Copyright 2026 Lusoris
"""Verification that every scanner of security-scans.yml fails its job on a finding.

A scanner that prints its findings and exits 0 leaves the job green. Trivy exits 0 unless
`exit-code` is set, Semgrep unless `--error` is given, and Gitleaks unless `--exit-code`
is non-zero. Each test below reads the step from the workflow and refuses the planted
variant that would pass with findings.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "security-scans.yml"
TRIVY_ACTION = "aquasecurity/trivy-action@"
SEMGREP_FAILS = re.compile(r"(^|\s)semgrep\s(.*\s)?--error(\s|$)")
GITLEAKS_FAILS = re.compile(r"(^|\s)\S*gitleaks\s(.*\s)?--exit-code[ =]1(\s|$)")


def steps(job: str) -> list[dict]:
    with WORKFLOW.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)["jobs"][job]["steps"]


def trivy_fails(step: dict) -> bool:
    return str(step.get("with", {}).get("exit-code", "")) == "1"


def run_lines(job: str) -> list[str]:
    return [line for step in steps(job) for line in step.get("run", "").splitlines()]


def test_trivy_fails_on_a_finding():
    scans = [step for step in steps("trivy") if step.get("uses", "").startswith(TRIVY_ACTION)]
    assert len(scans) == 1
    assert trivy_fails(scans[0])


@pytest.mark.parametrize(
    "inputs",
    [{}, {"exit-code": "0"}, {"exit-code": ""}, {"exit-code": "10"}],
    ids=["unset", "zero", "empty", "other"],
)
def test_planted_trivy_inputs_pass_with_findings(inputs):
    assert not trivy_fails({"uses": TRIVY_ACTION, "with": inputs})


def test_semgrep_fails_on_a_finding():
    assert any(SEMGREP_FAILS.search(line) for line in run_lines("semgrep"))


def test_gitleaks_fails_on_a_finding():
    assert any(GITLEAKS_FAILS.search(line) for line in run_lines("gitleaks"))


@pytest.mark.parametrize(
    ("pattern", "line"),
    [
        (SEMGREP_FAILS, "semgrep --config p/ci ."),
        (SEMGREP_FAILS, "semgrep --error-free --config p/ci ."),
        (GITLEAKS_FAILS, "/tmp/gitleaks git --redact ."),
        (GITLEAKS_FAILS, "/tmp/gitleaks git --exit-code 0 ."),
        (GITLEAKS_FAILS, "/tmp/gitleaks git --exit-code 10 ."),
    ],
    ids=["semgrep-no-error", "semgrep-other-flag", "gitleaks-unset", "gitleaks-zero", "gitleaks-ten"],
)
def test_planted_commands_pass_with_findings(pattern, line):
    assert not pattern.search(line)
