# Copyright 2026 Lusoris
"""Verification that the action pin check fails closed.

`tools/ci/action_pins.py` runs zizmor online over the workflows (`action-pins.yml`) and
fails on an action reference that is not pinned to a commit of its repository. The tests
below run the check against a stub zizmor: it passes a clean scan, fails on each pin
finding, refuses to run without a token or with the offline switches, refuses a zizmor
that does not report the planted workflow for every named audit, and accepts only the
exit codes zizmor documents. They also hold the workflow wiring and the hash-pinned
install.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "ci" / "action_pins.py"
WORKFLOW = ROOT / ".github" / "workflows" / "action-pins.yml"
REQUIREMENTS = ROOT / ".github" / "requirements"

_spec = importlib.util.spec_from_file_location("action_pins", SCRIPT)
pins = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pins)

# A zizmor stand-in: the canary target and the real target each get their own reply.
# STUB_<SIDE>_FINDINGS is a comma list of audit@line; STUB_<SIDE>_EXIT is the exit code.
STUB = """
import json, os, sys
side = "CANARY" if "action-pins-canary-" in sys.argv[-1] else "TARGET"
findings = []
for item in filter(None, os.environ.get(f"STUB_{side}_FINDINGS", "").split(",")):
    ident, line = item.split("@")
    findings.append({
        "ident": ident,
        "locations": [{
            "symbolic": {"key": {"Local": {"verbatim_path": ".github/workflows/ci.yml"}}},
            "concrete": {"location": {"start_point": {"row": int(line) - 1, "column": 0}}},
        }],
    })
print(json.dumps(findings))
sys.exit(int(os.environ.get(f"STUB_{side}_EXIT", "0")))
"""
ALL_PLANTED = ",".join(f"{audit}@1" for audit in pins.AUDITS)


@pytest.fixture
def stub(tmp_path, monkeypatch):
    """Run the stub instead of zizmor, with a token set and the offline switches unset."""
    script = tmp_path / "stub_zizmor.py"
    script.write_text(STUB, encoding="utf-8")
    real = pins.command
    monkeypatch.setattr(
        pins, "command", lambda binary, target: [sys.executable, "-I", str(script), *real(binary, target)[1:]]
    )
    for name in (*pins.TOKEN_ENV, *pins.OFFLINE_ENV):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GH_TOKEN", "planted-token")

    def reply(canary: str = ALL_PLANTED, target: str = "", canary_exit: int = 14, target_exit: int = 0) -> None:
        monkeypatch.setenv("STUB_CANARY_FINDINGS", canary)
        monkeypatch.setenv("STUB_TARGET_FINDINGS", target)
        monkeypatch.setenv("STUB_CANARY_EXIT", str(canary_exit))
        monkeypatch.setenv("STUB_TARGET_EXIT", str(target_exit))

    return reply


def test_clean_workflows_pass(stub, capsys):
    stub()
    assert pins.main(["--binary", "unused", ".github/workflows"]) == 0
    out = capsys.readouterr().out
    assert "refused impostor-commit, ref-version-mismatch, unpinned-uses" in out
    assert "0 finding(s)" in out


@pytest.mark.parametrize("audit", pins.AUDITS)
def test_each_pin_finding_fails_with_its_file_and_line(stub, capsys, audit):
    stub(target=f"{audit}@42", target_exit=13)
    assert pins.main(["--binary", "unused", ".github/workflows"]) == 1
    assert f"::error file=.github/workflows/ci.yml,line=42::{audit}:" in capsys.readouterr().out


def test_findings_of_other_audits_do_not_fail(stub):
    stub(target="artipacked@3,template-injection@9", target_exit=14)
    assert pins.main(["--binary", "unused", ".github/workflows"]) == 0


@pytest.mark.parametrize("audit", pins.AUDITS)
def test_canary_missing_an_audit_fails(stub, capsys, audit):
    stub(canary=",".join(f"{other}@1" for other in pins.AUDITS if other != audit))
    assert pins.main(["--binary", "unused", ".github/workflows"]) == 1
    assert f"did not report the planted workflow for: {audit}" in capsys.readouterr().err


def test_unknown_audit_name_fails_closed(stub, monkeypatch, capsys):
    monkeypatch.setattr(pins, "AUDITS", (*pins.AUDITS, "renamed-audit"))
    stub()
    assert pins.main(["--binary", "unused", ".github/workflows"]) == 1
    assert "for: renamed-audit" in capsys.readouterr().err


@pytest.mark.parametrize("status", [1, 2, 3, 10, 15])
def test_undocumented_or_error_exit_fails(stub, capsys, status):
    stub(target_exit=status)
    assert pins.main(["--binary", "unused", ".github/workflows"]) == 1
    assert f"exit {status}" in capsys.readouterr().err


@pytest.mark.parametrize("status", [0, 11, 12, 13, 14])
def test_documented_exit_codes_are_accepted(stub, status):
    stub(target_exit=status)
    assert pins.main(["--binary", "unused", ".github/workflows"]) == 0


def test_canary_error_exit_fails(stub, capsys):
    stub(canary_exit=1)
    assert pins.main(["--binary", "unused", ".github/workflows"]) == 1
    assert "action-pins-canary-" in capsys.readouterr().err


def test_missing_token_fails(stub, monkeypatch, capsys):
    stub()
    monkeypatch.delenv("GH_TOKEN")
    assert pins.main(["--binary", "unused", ".github/workflows"]) == 1
    assert "no GitHub token" in capsys.readouterr().err


def test_empty_token_fails():
    with pytest.raises(pins.PinCheckError, match="no GitHub token"):
        pins.preflight({"GH_TOKEN": ""})


@pytest.mark.parametrize("name", pins.TOKEN_ENV)
def test_any_documented_token_variable_is_enough(name):
    pins.preflight({name: "planted-token"})


@pytest.mark.parametrize("name", pins.OFFLINE_ENV)
def test_offline_switch_fails(name):
    with pytest.raises(pins.PinCheckError, match=name):
        pins.preflight({"GH_TOKEN": "planted-token", name: "1"})


def test_malformed_output_fails(tmp_path, monkeypatch):
    script = tmp_path / "object.py"
    script.write_text("import json; print(json.dumps({'ident': 'x'}))", encoding="utf-8")
    monkeypatch.setattr(pins, "command", lambda _binary, _target: [sys.executable, "-I", str(script)])
    with pytest.raises(pins.PinCheckError, match="not a JSON list"):
        pins.scan("unused", tmp_path)


def test_command_loads_no_configuration_and_stays_online():
    args = pins.command("zizmor", Path("t"))
    assert {"--no-config", "--no-ignores", "--strict-collection"} <= set(args)
    assert args[args.index("--format") + 1] == "json"
    assert not {"--offline", "-o", "--no-online-audits", "--no-exit-codes", "--config", "-c"} & set(args)


def test_plant_holds_one_step_per_audit():
    steps = yaml.safe_load(pins.PLANT)["jobs"]["plant"]["steps"]
    uses = [step["uses"] for step in steps]
    assert len(uses) == len(pins.AUDITS)
    assert any(ref.endswith("@0000000000000000000000000000000000000001") for ref in uses)
    assert any(len(ref.split("@")[1]) != 40 for ref in uses), "no tag-pinned step for unpinned-uses"


def test_location_is_one_based():
    finding = {
        "locations": [
            {
                "symbolic": {"key": {"Local": {"verbatim_path": "a.yml"}}},
                "concrete": {"location": {"start_point": {"row": 0}}},
            }
        ]
    }
    assert pins.location(finding) == ("a.yml", 1)
    assert json.dumps(pins.location({})) == '["?", 0]'


def load_workflow() -> dict:
    with WORKFLOW.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_workflow_triggers_on_workflow_changes_weekly_and_by_hand():
    on = load_workflow()[True]  # PyYAML reads the unquoted key `on` as True.
    assert {".github/workflows/**", ".github/requirements/pins.txt", "tools/ci/action_pins.py"} <= set(
        on["pull_request"]["paths"]
    )
    assert on["schedule"] and "workflow_dispatch" in on


def test_workflow_runs_the_check_with_the_run_token_and_least_privilege():
    workflow = load_workflow()
    job = workflow["jobs"]["pins"]
    assert workflow["permissions"] == {} and job["permissions"] == {"contents": "read"}
    steps = job["steps"]
    assert steps[0]["name"] == "Stop on a draft pull request"
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["persist-credentials"] is False
    assert any(step.get("run") == "pip install --require-hashes -r .github/requirements/pins.txt" for step in steps)
    check = next(step for step in steps if "tools/ci/action_pins.py" in step.get("run", ""))
    assert check["env"] == {"GH_TOKEN": "${{ github.token }}"}
    assert "continue-on-error" not in check and "continue-on-error" not in job


def test_zizmor_is_pinned_by_hash():
    lock = (REQUIREMENTS / "pins.txt").read_text(encoding="utf-8")
    assert "zizmor==" in (REQUIREMENTS / "pins.in").read_text(encoding="utf-8")
    block = lock.split("zizmor==", 1)[1]
    assert block.split("\\", 1)[0].strip().count(".") == 2
    assert "--hash=sha256:" in block
