# Copyright 2026 Lusoris
"""Verification that every scanner of security-scans.yml fails its job on a finding.

A scanner that prints its findings and exits 0 leaves the job green. Trivy exits 0 unless
`exit-code` is set, Semgrep unless `--error` is given, and Gitleaks unless `--exit-code`
is non-zero. Govulncheck exits 0 with `-json` or any `-format` but text, and a shell that
skips it or ignores its status passes as well. Each test below reads the step from the
workflow and refuses the planted variant that would pass with findings.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.harness.mock_runner import GIT_BASH
from tests.test_provisioners_execution import check_bash

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "security-scans.yml"
TOOL_MODULE = ROOT / "tools" / "govulncheck"
TRIVY_ACTION = "aquasecurity/trivy-action@"
SEMGREP_FAILS = re.compile(r"(^|\s)semgrep\s(.*\s)?--error(\s|$)")
GITLEAKS_FAILS = re.compile(r"(^|\s)\S*gitleaks\s(.*\s)?--exit-code[ =]1(\s|$)")
# The pinned scanner of tools/govulncheck/go.mod, run on every package of the repository.
GOVULNCHECK_SCAN = 'go -C tools/govulncheck tool govulncheck -C "$PWD" ./...'
# Shapes that let the step pass although govulncheck found something or did not run.
GOVULNCHECK_HIDERS = re.compile(r"\|\||;\s*(true|:|exit)\b|(^|\s)-(json|format)\b|command -v|(^|\s)which\s")
STEP_TIMEOUT_S = 30
# The only condition the scan step may carry: the job's path filter (ADR-0027), which
# runs the scan on every push and scheduled run.
GOVULNCHECK_GATE = "github.event_name != 'pull_request' || steps.filter.outputs.govulncheck == 'true'"


def steps(job: str) -> list[dict]:
    with WORKFLOW.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)["jobs"][job]["steps"]


def trivy_fails(step: dict) -> bool:
    return str(step.get("with", {}).get("exit-code", "")) == "1"


def govulncheck_fails(step: dict) -> bool:
    script = step.get("run", "")
    lines = [line.strip() for line in script.splitlines() if line.strip()]
    return (
        lines == ["set -euo pipefail", GOVULNCHECK_SCAN]
        and not GOVULNCHECK_HIDERS.search(script)
        and not step.get("continue-on-error")
        and step.get("if", GOVULNCHECK_GATE) == GOVULNCHECK_GATE
    )


def govulncheck_step() -> dict:
    scans = [step for step in steps("govulncheck") if "tool govulncheck" in step.get("run", "")]
    assert len(scans) == 1
    return scans[0]


def run_with_stub_go(script: str, tmp_path: Path, status: int) -> int:
    """Run the step script with a `go` that exits `status`, as govulncheck would."""
    check_bash(GIT_BASH)
    stub = tmp_path / "go"
    stub.write_text(f"#!/bin/sh\nexit {status}\n", encoding="utf-8")
    stub.chmod(0o755)
    env = {"PATH": f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}"}
    res = subprocess.run(
        [str(GIT_BASH), "-c", script], env=env, capture_output=True, timeout=STEP_TIMEOUT_S, check=False
    )
    return res.returncode


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


def test_govulncheck_fails_on_a_finding():
    assert govulncheck_fails(govulncheck_step())


@pytest.mark.parametrize(
    "step",
    [
        {"run": "set -euo pipefail\n" + GOVULNCHECK_SCAN.replace("./...", "-json ./...")},
        {"run": "set -euo pipefail\n" + GOVULNCHECK_SCAN.replace("./...", "-format sarif ./...")},
        {"run": "set -euo pipefail\n" + GOVULNCHECK_SCAN + " || true"},
        {"run": "set -euo pipefail\n" + GOVULNCHECK_SCAN + "; exit 0"},
        {"run": "set -euo pipefail\ncommand -v go && " + GOVULNCHECK_SCAN},
        {"run": "set -euo pipefail\ngo run golang.org/x/vuln/cmd/govulncheck@latest ./..."},
        {"run": GOVULNCHECK_SCAN},
        {"run": "set -euo pipefail\n" + GOVULNCHECK_SCAN, "continue-on-error": True},
        {"run": "set -euo pipefail\n" + GOVULNCHECK_SCAN, "if": "hashFiles('go.sum') != ''"},
        {
            "run": "set -euo pipefail\n" + GOVULNCHECK_SCAN,
            "if": f"({GOVULNCHECK_GATE}) && github.event_name != 'schedule'",
        },
    ],
    ids=[
        "json",
        "sarif",
        "or-true",
        "exit-0",
        "skip-if-missing",
        "unpinned",
        "no-errexit",
        "continue",
        "cond",
        "no-schedule",
    ],
)
def test_planted_govulncheck_steps_pass_with_findings(step):
    assert not govulncheck_fails(step)


@pytest.mark.parametrize(("status", "fails"), [(0, False), (1, True), (3, True)], ids=["clean", "error", "found"])
def test_govulncheck_step_returns_the_scanner_status(tmp_path, status, fails):
    assert (run_with_stub_go(govulncheck_step()["run"], tmp_path, status) != 0) == fails


def test_govulncheck_runs_on_the_weekly_schedule():
    with WORKFLOW.open(encoding="utf-8") as handle:
        workflow = yaml.safe_load(handle)
    assert workflow[True]["schedule"]
    assert "if" not in workflow["jobs"]["govulncheck"]
    assert govulncheck_step()["if"] == GOVULNCHECK_GATE


def test_govulncheck_is_pinned_in_its_own_module():
    mod = (TOOL_MODULE / "go.mod").read_text(encoding="utf-8")
    assert re.search(r"(?m)^tool golang\.org/x/vuln/cmd/govulncheck$", mod)
    pin = re.search(r"(?m)^\s*golang\.org/x/vuln (v\d+\.\d+\.\d+)\b", mod)
    assert pin
    assert f"golang.org/x/vuln {pin.group(1)} h1:" in (TOOL_MODULE / "go.sum").read_text(encoding="utf-8")
    assert "golang.org/x/vuln" not in (ROOT / "go.mod").read_text(encoding="utf-8")
