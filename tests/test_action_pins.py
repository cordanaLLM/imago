# Copyright 2026 Lusoris
"""Verification that the action pin and workflow audit check fails closed.

`tools/ci/action_pins.py` runs zizmor online over the workflows (`action-pins.yml`) and
fails on an action reference that is not pinned to a commit of its repository, and on the
template-injection, permission, job-name, credential, concurrency and superfluous-action
audits. The tests below run the check against a stub zizmor: it passes a clean scan, fails
on each gated finding, refuses to run without a token or with the offline switches,
refuses a zizmor that does not report the planted workflow for every named audit, and
accepts only the exit codes zizmor documents. The exception file excuses a finding only
while its entry is valid: an expired, overlong, malformed, repeated or unmatched entry
fails the check. The tests also hold the workflow wiring and the hash-pinned install, and
require every tool a workflow downloads to come from a release and to match a checksum.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "ci" / "action_pins.py"
WORKFLOWS = ROOT / ".github" / "workflows"
WORKFLOW = WORKFLOWS / "action-pins.yml"
REQUIREMENTS = ROOT / ".github" / "requirements"
EXCEPTIONS = ROOT / ".github" / "zizmor-exceptions.json"

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

    exceptions = tmp_path / "exceptions.json"
    exceptions.write_text("[]", encoding="utf-8")

    def reply(canary: str = ALL_PLANTED, target: str = "", canary_exit: int = 14, target_exit: int = 0) -> None:
        monkeypatch.setenv("STUB_CANARY_FINDINGS", canary)
        monkeypatch.setenv("STUB_TARGET_FINDINGS", target)
        monkeypatch.setenv("STUB_CANARY_EXIT", str(canary_exit))
        monkeypatch.setenv("STUB_TARGET_EXIT", str(target_exit))

    def excepting(*entries: dict) -> None:
        exceptions.write_text(json.dumps(list(entries)), encoding="utf-8")

    reply.args = ["--binary", "unused", "--exceptions", str(exceptions), ".github/workflows"]
    reply.excepting = excepting
    reply.file = exceptions
    return reply


def test_clean_workflows_pass(stub, capsys):
    stub()
    assert pins.main(stub.args) == 0
    out = capsys.readouterr().out
    assert f"refused {', '.join(pins.AUDITS)}" in out
    assert "0 finding(s)" in out


def test_gated_audits_are_the_pin_and_workflow_audits():
    assert set(pins.AUDITS) == {
        "anonymous-definition",
        "artipacked",
        "concurrency-limits",
        "excessive-permissions",
        "impostor-commit",
        "ref-version-mismatch",
        "superfluous-actions",
        "template-injection",
        "undocumented-permissions",
        "unpinned-uses",
    }


@pytest.mark.parametrize("audit", pins.AUDITS)
def test_each_gated_finding_fails_with_its_file_line_and_fix(stub, capsys, audit):
    stub(target=f"{audit}@42", target_exit=13)
    assert pins.main(stub.args) == 1
    assert f"::error file=.github/workflows/ci.yml,line=42::{audit}: {pins.ADVICE[audit]}" in capsys.readouterr().out


def test_findings_of_other_audits_do_not_fail(stub):
    stub(target="dangerous-triggers@3,cache-poisoning@9", target_exit=14)
    assert pins.main(stub.args) == 0


@pytest.mark.parametrize("audit", pins.AUDITS)
def test_canary_missing_an_audit_fails(stub, capsys, audit):
    stub(canary=",".join(f"{other}@1" for other in pins.AUDITS if other != audit))
    assert pins.main(stub.args) == 1
    assert f"did not report the planted workflow for: {audit}" in capsys.readouterr().err


def test_unknown_audit_name_fails_closed(stub, monkeypatch, capsys):
    monkeypatch.setattr(pins, "AUDITS", (*pins.AUDITS, "renamed-audit"))
    stub()
    assert pins.main(stub.args) == 1
    assert "for: renamed-audit" in capsys.readouterr().err


@pytest.mark.parametrize("status", [1, 2, 3, 10, 15])
def test_undocumented_or_error_exit_fails(stub, capsys, status):
    stub(target_exit=status)
    assert pins.main(stub.args) == 1
    assert f"exit {status}" in capsys.readouterr().err


@pytest.mark.parametrize("status", [0, 11, 12, 13, 14])
def test_documented_exit_codes_are_accepted(stub, status):
    stub(target_exit=status)
    assert pins.main(stub.args) == 0


def test_canary_error_exit_fails(stub, capsys):
    stub(canary_exit=1)
    assert pins.main(stub.args) == 1
    assert "action-pins-canary-" in capsys.readouterr().err


def test_missing_token_fails(stub, monkeypatch, capsys):
    stub()
    monkeypatch.delenv("GH_TOKEN")
    assert pins.main(stub.args) == 1
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


def test_plant_holds_one_defect_per_audit():
    plant = yaml.safe_load(pins.PLANT)
    job = plant["jobs"]["plant"]
    uses = [step["uses"] for step in job["steps"] if "uses" in step]
    assert len(uses) == 4
    assert any(ref.endswith("@0000000000000000000000000000000000000001") for ref in uses)
    assert any(len(ref.split("@")[1]) != 40 for ref in uses), "no tag-pinned step for unpinned-uses"
    assert plant["permissions"] == "write-all", "no grant for excessive-permissions"
    assert "name" not in job, "no anonymous job for anonymous-definition"
    assert "contents: write\n" in pins.PLANT, "no uncommented grant for undocumented-permissions"
    assert any("${{" in step.get("run", "") for step in job["steps"]), "no expansion for template-injection"
    checkouts = [step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@")]
    assert any("with" not in step for step in checkouts), "no token-keeping checkout for artipacked"
    assert "concurrency" not in plant and "concurrency" not in job, "a concurrency group hides concurrency-limits"
    assert any(ref.startswith("peter-evans/create-pull-request@") for ref in uses), "no step for superfluous-actions"


TODAY = datetime.date(2026, 10, 14)


def entry(**fields: str) -> dict:
    """An exception for the stub finding, valid on TODAY unless a field overrides it."""
    return {
        "rule": "artipacked",
        "path": ".github/workflows/ci.yml",
        "reason": "category D: the engine renders this file",
        "expires": str(TODAY + datetime.timedelta(days=30)),
    } | fields


def live(**fields: str) -> dict:
    """The same exception, valid on the day the test runs."""
    today = datetime.datetime.now(datetime.UTC).date()
    return entry(expires=str(today + datetime.timedelta(days=30))) | fields


def test_excepted_finding_passes_with_a_warning(stub, capsys):
    stub(target="artipacked@32", target_exit=13)
    stub.excepting(live())
    assert pins.main(stub.args) == 0
    out = capsys.readouterr().out
    assert "::warning file=.github/workflows/ci.yml,line=32::artipacked excepted until" in out
    assert "0 finding(s) in .github/workflows, 1 excepted" in out


def test_exception_covers_only_its_audit(stub, capsys):
    stub(target="artipacked@32,concurrency-limits@4", target_exit=13)
    stub.excepting(live())
    assert pins.main(stub.args) == 1
    assert "line=4::concurrency-limits: " in capsys.readouterr().out


def test_exception_covers_only_its_path(stub, capsys):
    stub(target="artipacked@32", target_exit=13)
    stub.excepting(live(path=".github/workflows/other.yml"))
    assert pins.main(stub.args) == 1
    assert "matches no finding, remove it: artipacked on .github/workflows/other.yml" in capsys.readouterr().err


def test_unmatched_exception_fails(stub, capsys):
    stub()
    stub.excepting(live())
    assert pins.main(stub.args) == 1
    assert "matches no finding, remove it: artipacked on .github/workflows/ci.yml" in capsys.readouterr().err


def test_expired_exception_fails(stub, capsys):
    stub(target="artipacked@32", target_exit=13)
    stub.excepting(live(expires="2026-01-01"))
    assert pins.main(stub.args) == 1
    assert "expired on 2026-01-01" in capsys.readouterr().err


def test_repeated_exception_fails(stub, capsys):
    stub(target="artipacked@32", target_exit=13)
    stub.excepting(live(), live(reason="category D: listed again"))
    assert pins.main(stub.args) == 1
    assert "artipacked on .github/workflows/ci.yml is listed twice" in capsys.readouterr().err


def test_repeated_key_fails(stub, capsys):
    stub(target="artipacked@32", target_exit=13)
    stub.file.write_text(json.dumps([live()])[:-2] + ', "rule": "artipacked"}]', encoding="utf-8")
    assert pins.main(stub.args) == 1
    assert "repeats the key rule" in capsys.readouterr().err


def test_exception_file_must_be_a_list(stub, capsys):
    stub()
    stub.file.write_text(json.dumps(live()), encoding="utf-8")
    assert pins.main(stub.args) == 1
    assert "must be a JSON list" in capsys.readouterr().err


def test_missing_exception_file_fails(stub, capsys):
    stub()
    stub.file.unlink()
    assert pins.main(stub.args) == 1


@pytest.mark.parametrize("field", pins.EXCEPTION_FIELDS)
def test_exception_missing_a_field_fails(field):
    planted = entry()
    del planted[field]
    with pytest.raises(pins.PinCheckError, match="needs exactly the fields"):
        pins.check_entry(planted, TODAY)


def test_exception_with_an_extra_field_fails():
    with pytest.raises(pins.PinCheckError, match="needs exactly the fields"):
        pins.check_entry(entry(owner="someone"), TODAY)


@pytest.mark.parametrize("field", pins.EXCEPTION_FIELDS)
def test_exception_with_an_empty_field_fails(field):
    with pytest.raises(pins.PinCheckError, match="empty or non-text"):
        pins.check_entry(entry(**{field: " "}), TODAY)


def test_exception_for_an_ungated_audit_fails():
    with pytest.raises(pins.PinCheckError, match="does not gate"):
        pins.check_entry(entry(rule="dangerous-triggers"), TODAY)


@pytest.mark.parametrize("reason", ["the engine renders this file", "category E: other", "see category D: later"])
def test_exception_reason_without_its_category_fails(reason):
    with pytest.raises(pins.PinCheckError, match="must start with 'category"):
        pins.check_entry(entry(reason=reason), TODAY)


def test_exception_with_a_malformed_date_fails():
    with pytest.raises(ValueError):
        pins.check_entry(entry(expires="next spring"), TODAY)


@pytest.mark.parametrize(
    ("category", "days", "valid"),
    [
        ("A", 90, True),
        ("A", 91, False),
        ("B", 3, True),
        ("B", 4, False),
        ("C", 10, True),
        ("C", 11, False),
        ("D", 90, True),
        ("D", 91, False),
        ("D", 0, True),
        ("D", -1, False),
    ],
)
def test_exception_expiry_bounds_by_category(category, days, valid):
    planted = entry(reason=f"category {category}: planted", expires=str(TODAY + datetime.timedelta(days=days)))
    if valid:
        assert pins.check_entry(planted, TODAY) == ("artipacked", ".github/workflows/ci.yml")
    else:
        with pytest.raises(pins.PinCheckError, match="expired|runs past"):
            pins.check_entry(planted, TODAY)


def test_exception_path_is_normalised():
    assert pins.check_entry(entry(path=".github//workflows/./ci.yml"), TODAY)[1] == ".github/workflows/ci.yml"


def test_committed_exceptions_are_valid_and_point_at_real_files():
    today = datetime.datetime.now(datetime.UTC).date()
    excepted = pins.load_exceptions(EXCEPTIONS, today)
    assert set(excepted) == {
        ("superfluous-actions", ".github/workflows/sync-kernel-manifest.yml"),
    }
    for (_rule, path), item in excepted.items():
        assert (ROOT / path).is_file()
        if path.endswith("praetor-docs.yml"):
            assert "cordanaLLM/praetor#" in item["reason"], "an engine-owned finding names its engine issue"


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
    assert {
        ".github/workflows/**",
        ".github/requirements/pins.txt",
        ".github/zizmor-exceptions.json",
        "tools/ci/action_pins.py",
    } <= set(on["pull_request"]["paths"])
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
    assert "--exceptions .github/zizmor-exceptions.json" in check["run"]
    assert "continue-on-error" not in check and "continue-on-error" not in job


def test_zizmor_is_pinned_by_hash():
    lock = (REQUIREMENTS / "pins.txt").read_text(encoding="utf-8")
    assert "zizmor==" in (REQUIREMENTS / "pins.in").read_text(encoding="utf-8")
    block = lock.split("zizmor==", 1)[1]
    assert block.split("\\", 1)[0].strip().count(".") == 2
    assert "--hash=sha256:" in block


# A download in a run step is pinned the way an action is: it names a release, and the file
# must match a checksum before it runs. A branch or the latest release changes under the
# same commit, and a script piped into a shell runs before anything checks it.
DOWNLOAD = re.compile(r"\b(curl|wget)\b")
URL = re.compile(r"https?://[^\s\"')]+")
MOVING_REF = re.compile(r"/(main|master|HEAD)(/|$)|/refs/heads/|/releases/latest\b")
PIPED_SCRIPT = re.compile(r"(ba)?sh\s+-c\s+\"\$\((curl|wget)|\b(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba)?sh\b")


def run_steps() -> list[tuple[str, dict]]:
    steps = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        with path.open(encoding="utf-8") as handle:
            jobs = yaml.safe_load(handle).get("jobs", {})
        for job_id, job in jobs.items():
            for index, step in enumerate(job.get("steps", [])):
                if "run" in step:
                    steps.append((f"{path.name} {job_id} step {index + 1}", step))
    return steps


def download_steps() -> list[tuple[str, dict]]:
    return [(where, step) for where, step in run_steps() if DOWNLOAD.search(step["run"])]


def test_the_guard_sees_the_known_downloads():
    names = {step.get("name") for _, step in download_steps()}
    assert {"Install Workflow Linters", "Run Gitleaks CLI against full history"} <= names


def test_downloads_name_a_release_not_a_branch():
    moving = [
        (where, url) for where, step in download_steps() for url in URL.findall(step["run"]) if MOVING_REF.search(url)
    ]
    assert moving == []


def test_no_step_pipes_a_download_into_a_shell():
    assert [where for where, step in run_steps() if PIPED_SCRIPT.search(step["run"])] == []


def test_every_download_is_checked_against_a_checksum():
    assert [where for where, step in download_steps() if "sha256sum -c" not in step["run"]] == []


def test_actionlint_matches_the_checksum_written_in_the_workflow():
    with (WORKFLOWS / "ci.yml").open(encoding="utf-8") as handle:
        steps = yaml.safe_load(handle)["jobs"]["lint-workflows"]["steps"]
    install = next(step for step in steps if step.get("name") == "Install Workflow Linters")
    assert re.fullmatch(r"\d+\.\d+\.\d+", install["env"]["ACTIONLINT_VERSION"])
    assert re.fullmatch(r"[0-9a-f]{64}", install["env"]["ACTIONLINT_SHA256"])
    run = install["run"]
    assert run.startswith("set -euo pipefail\n")
    assert "releases/download/v${ACTIONLINT_VERSION}/" in run
    assert 'echo "${ACTIONLINT_SHA256}  /tmp/${archive}" | sha256sum -c -' in run
    # A checksum file fetched next to the archive comes from the same place as the archive.
    assert "checksums" not in run
