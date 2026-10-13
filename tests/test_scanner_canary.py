# Copyright 2026 Lusoris
"""Verification that the scanner canary fails unless its scanner refuses the plants.

`tools/ci/scanner_canary.py` runs before the Gitleaks and Semgrep scans of ci.yml and
security-scans.yml. It plants findings outside the checkout and fails the job unless the
scanner exits non-zero and reports every planted rule. The tests below run the canary
against a stub scanner that passes, fails, omits a rule or writes no report, check that
the plants match the repository's own rules, and check the workflow wiring.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "ci" / "scanner_canary.py"
GITLEAKS_CONFIG = ROOT / ".gitleaks.toml"
WORKFLOWS = ROOT / ".github" / "workflows"
CANARY = "python3 -I tools/ci/scanner_canary.py"
GITLEAKS_SCAN = re.compile(r"^(\S*gitleaks) git ")

_spec = importlib.util.spec_from_file_location("scanner_canary", SCRIPT)
canary = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(canary)

# A scanner stand-in: writes the report the test asks for and exits with its status.
STUB = """
import json, os, sys
report, kind = sys.argv[1], os.environ["STUB_KIND"]
rules = [rule for rule in os.environ["STUB_RULES"].split(",") if rule]
if os.environ.get("STUB_REPORT", "1") == "1":
    if kind == "gitleaks":
        body = [{"RuleID": rule} for rule in rules]
    else:
        body = {"results": [{"check_id": rule} for rule in rules]}
    with open(report, "w", encoding="utf-8") as handle:
        json.dump(body, handle)
sys.exit(int(os.environ["STUB_EXIT"]))
"""


@pytest.fixture
def stub(tmp_path, monkeypatch):
    """Replace each scanner command with the stub; return a function that sets its reply."""
    script = tmp_path / "stub_scanner.py"
    script.write_text(STUB, encoding="utf-8")
    for name, (plants, _command, rules) in list(canary.SCANNERS.items()):
        monkeypatch.setitem(
            canary.SCANNERS,
            name,
            (plants, lambda _binary, _target, report: [sys.executable, "-I", str(script), str(report)], rules),
        )

    def reply(kind: str, status: int, rules: list[str], report: bool = True) -> None:
        monkeypatch.setenv("STUB_KIND", kind)
        monkeypatch.setenv("STUB_EXIT", str(status))
        monkeypatch.setenv("STUB_RULES", ",".join(rules))
        monkeypatch.setenv("STUB_REPORT", "1" if report else "0")

    return reply


@pytest.mark.parametrize("scanner", sorted(canary.SCANNERS))
def test_scanner_that_refuses_every_plant_passes(stub, scanner):
    stub(scanner, 1, sorted(canary.SCANNERS[scanner][0]))
    canary.run(scanner, "unused")


@pytest.mark.parametrize("scanner", sorted(canary.SCANNERS))
def test_planted_passing_scanner_fails(stub, scanner):
    stub(scanner, 0, sorted(canary.SCANNERS[scanner][0]))
    with pytest.raises(canary.CanaryError, match="exited 0"):
        canary.run(scanner, "unused")


@pytest.mark.parametrize("scanner", sorted(canary.SCANNERS))
def test_planted_scanner_missing_a_rule_fails(stub, scanner):
    stub(scanner, 1, sorted(canary.SCANNERS[scanner][0])[1:])
    with pytest.raises(canary.CanaryError, match="did not report"):
        canary.run(scanner, "unused")


@pytest.mark.parametrize("scanner", sorted(canary.SCANNERS))
def test_scanner_that_cannot_scan_fails(stub, scanner):
    stub(scanner, 2, sorted(canary.SCANNERS[scanner][0]))
    with pytest.raises(canary.CanaryError, match="could not scan"):
        canary.run(scanner, "unused")


@pytest.mark.parametrize("scanner", sorted(canary.SCANNERS))
def test_scanner_without_a_report_fails(stub, scanner):
    stub(scanner, 1, [], report=False)
    with pytest.raises(canary.CanaryError, match="no report"):
        canary.run(scanner, "unused")


@pytest.mark.parametrize(
    ("parse", "report"),
    [(canary.gitleaks_rules, {"RuleID": "x"}), (canary.semgrep_rules, []), (canary.semgrep_rules, {"results": 1})],
    ids=["gitleaks-object", "semgrep-list", "semgrep-results-scalar"],
)
def test_malformed_reports_fail(parse, report):
    with pytest.raises(canary.CanaryError):
        parse(report)


def test_main_reports_a_failed_canary(stub, capsys):
    stub("gitleaks", 0, [])
    assert canary.main(["gitleaks", "--binary", "unused"]) == 1
    assert "::error::gitleaks canary failed" in capsys.readouterr().err


def test_plant_writes_every_planted_file(tmp_path):
    for plants in (canary.GITLEAKS_PLANTS, canary.SEMGREP_PLANTS):
        canary.plant(tmp_path, plants)
        for name, content in plants.values():
            assert (tmp_path / name).read_text(encoding="utf-8") == content


def test_cosign_plant_matches_the_repository_rule():
    rules = tomllib.loads(GITLEAKS_CONFIG.read_text(encoding="utf-8"))["rules"]
    pattern = next(rule["regex"] for rule in rules if rule["id"] == "no-cosign-private-key")
    assert re.search(pattern, canary.GITLEAKS_PLANTS["no-cosign-private-key"][1])
    assert not re.search(pattern, SCRIPT.read_text(encoding="utf-8")), "canary source holds a finding"


def test_canary_source_holds_no_planted_text():
    source = SCRIPT.read_text(encoding="utf-8")
    for plants in (canary.GITLEAKS_PLANTS, canary.SEMGREP_PLANTS):
        for _name, content in plants.values():
            assert content.strip() not in source


def workflow_jobs() -> list[tuple[str, dict]]:
    jobs = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        jobs.extend((f"{path.name}:{name}", job) for name, job in data.get("jobs", {}).items())
    return jobs


def test_every_gitleaks_scan_runs_the_canary_first():
    scans = 0
    for label, job in workflow_jobs():
        for step in job.get("steps", []):
            lines = [line.strip() for line in step.get("run", "").splitlines()]
            for index, line in enumerate(lines):
                match = GITLEAKS_SCAN.match(line)
                if match:
                    scans += 1
                    expected = f"{CANARY} gitleaks --binary {match.group(1)}"
                    assert expected in lines[:index], f"{label} scans without the canary"
    assert scans >= 1


def test_every_semgrep_scan_runs_the_canary_first():
    scans = 0
    for label, job in workflow_jobs():
        runs = [step.get("run", "") for step in job.get("steps", [])]
        for index, script in enumerate(runs):
            if re.search(r"(^|\s)semgrep\s.*\s\.$", script.strip()):
                scans += 1
                earlier = [line.strip() for run in runs[:index] for line in run.splitlines()]
                assert f"{CANARY} semgrep --binary semgrep" in earlier, f"{label} scans without the canary"
    assert scans >= 1


def test_canary_steps_carry_no_bypass():
    for label, job in workflow_jobs():
        for step in job.get("steps", []):
            if CANARY in step.get("run", ""):
                assert "continue-on-error" not in step, label
                assert "|| true" not in step["run"], label
