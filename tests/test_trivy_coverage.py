# Copyright 2026 Lusoris
"""Verification that the Trivy job fails when a tracked lockfile goes unscanned.

Trivy reads pip dependencies only from files named requirements.txt, so the pinned
lockfiles under .github/requirements/ were never scanned and the job passed. The job now
passes .github/trivy.yaml, which names them, and runs tools/ci/trivy_coverage.py on the
JSON report. The tests below run the coverage check on reports with and without the pip
lockfiles, and check that the config pattern and the workflow wiring stay in place.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "ci" / "trivy_coverage.py"
CONFIG = ROOT / ".github" / "trivy.yaml"
WORKFLOW = ROOT / ".github" / "workflows" / "security-scans.yml"
TRIVY_ACTION = "aquasecurity/trivy-action@"
REPORT = "trivy-results.json"
SCRIPT_TIMEOUT_S = 60

_spec = importlib.util.spec_from_file_location("trivy_coverage", SCRIPT)
coverage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(coverage)


def tracked() -> set[str]:
    return coverage.tracked_lockfiles(ROOT)


def pip_lockfiles() -> set[str]:
    return {name for name in tracked() if name.startswith(".github/requirements/")}


def report(targets: set[str], extra_results: list[dict] | None = None) -> dict:
    results = [{"Target": name, "Class": coverage.LANGUAGE_CLASS} for name in sorted(targets)]
    return {"Results": results + (extra_results or [])}


def run_script(tmp_path: Path, content: dict) -> subprocess.CompletedProcess:
    path = tmp_path / REPORT
    path.write_text(json.dumps(content), encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--report", str(path), "--root", str(ROOT)],
        capture_output=True,
        text=True,
        timeout=SCRIPT_TIMEOUT_S,
        check=False,
    )


def trivy_step() -> dict:
    with WORKFLOW.open(encoding="utf-8") as handle:
        steps = yaml.safe_load(handle)["jobs"]["trivy"]["steps"]
    scans = [step for step in steps if step.get("uses", "").startswith(TRIVY_ACTION)]
    assert len(scans) == 1
    return scans[0]


def test_tracked_lockfiles_include_every_pip_lockfile():
    on_disk = {f".github/requirements/{p.name}" for p in (ROOT / ".github" / "requirements").glob("*.txt")}
    assert on_disk
    assert pip_lockfiles() == on_disk
    assert "go.mod" in tracked()


def test_report_of_every_lockfile_passes(tmp_path):
    res = run_script(tmp_path, report(tracked()))
    assert res.returncode == 0, res.stderr
    assert f"all {len(tracked())} tracked lockfiles" in res.stdout


def test_planted_report_without_pip_lockfiles_fails(tmp_path):
    # Trivy without .github/trivy.yaml reported exactly this set.
    res = run_script(tmp_path, report(tracked() - pip_lockfiles()))
    assert res.returncode == 1
    assert "::error::Trivy coverage" in res.stderr
    for name in pip_lockfiles():
        assert name in res.stderr


def test_reuse_requirements_are_a_tracked_lockfile(tmp_path):
    # Trivy reads any file named requirements.txt, so the hash-pinned REUSE lock is in every report.
    assert ".config/reuse/requirements.txt" in tracked()
    res = run_script(tmp_path, report(tracked() - {".config/reuse/requirements.txt"}))
    assert res.returncode == 1
    assert ".config/reuse/requirements.txt" in res.stderr


def test_planted_report_with_an_unexpected_target_fails(tmp_path):
    res = run_script(tmp_path, report(tracked() | {"vendor/requirements.txt"}))
    assert res.returncode == 1
    assert "vendor/requirements.txt" in res.stderr


@pytest.mark.parametrize(
    "content",
    [{}, {"Results": None}, {"Results": []}, report(set())],
    ids=["no-results", "null-results", "empty-results", "no-lockfile"],
)
def test_planted_empty_reports_fail(tmp_path, content):
    assert run_script(tmp_path, content).returncode == 1


def test_non_language_results_do_not_count(tmp_path):
    secrets = [{"Target": name, "Class": "secret"} for name in sorted(pip_lockfiles())]
    res = run_script(tmp_path, report(tracked() - pip_lockfiles(), secrets))
    assert res.returncode == 1


def test_unreadable_report_fails(tmp_path):
    path = tmp_path / REPORT
    path.write_text("{", encoding="utf-8")
    res = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--report", str(path), "--root", str(ROOT)],
        capture_output=True,
        text=True,
        timeout=SCRIPT_TIMEOUT_S,
        check=False,
    )
    assert res.returncode == 1
    assert "::error::Trivy coverage" in res.stderr


def test_findings_are_printed(tmp_path):
    vuln = {
        "VulnerabilityID": "CVE-2000-0001",
        "Severity": "HIGH",
        "PkgName": "planted",
        "InstalledVersion": "1.0",
        "FixedVersion": "1.1",
    }
    target = sorted(pip_lockfiles())[0]
    content = report(tracked())
    for result in content["Results"]:
        if result["Target"] == target:
            result["Vulnerabilities"] = [vuln]
    res = run_script(tmp_path, content)
    assert res.returncode == 0
    assert f"{target}: HIGH CVE-2000-0001 planted 1.0 -> 1.1" in res.stderr


def test_config_pattern_matches_every_pip_lockfile():
    patterns = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["scan"]["file-patterns"]
    pip = [re.compile(p.split(":", 1)[1]) for p in patterns if p.startswith("pip:")]
    assert len(pip) == 1
    for name in pip_lockfiles():
        assert pip[0].fullmatch(name), name
    assert not pip[0].fullmatch(".github/requirements/docs.in")


def test_workflow_passes_the_config_and_reads_the_report():
    inputs = trivy_step()["with"]
    assert inputs["trivy-config"] == ".github/trivy.yaml"
    assert inputs["format"] == "json"
    assert inputs["output"] == REPORT
    with WORKFLOW.open(encoding="utf-8") as handle:
        steps = yaml.safe_load(handle)["jobs"]["trivy"]["steps"]
    checks = [step for step in steps if "tools/ci/trivy_coverage.py" in step.get("run", "")]
    assert len(checks) == 1
    assert f"--report {REPORT}" in checks[0]["run"]
    gate = "github.event_name != 'pull_request' || steps.filter.outputs.trivy == 'true'"
    assert checks[0]["if"] == f"(!cancelled()) && ({gate})"
    assert steps.index(checks[0]) > steps.index(trivy_step())
