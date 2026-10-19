# Copyright 2026 Lusoris
"""Verification of the pull request job shape the required-checks aggregator relies on (ADR-0027).

`.github/workflows/required-aggregator.yml` accepts no skipped check. That holds only
while no job a pull request starts can be skipped: every such job begins with the draft
step, carries no job condition and needs no other job, and its workflow restarts on
`ready_for_review`. A job with nothing to check passes through its path filter instead
of skipping (tests/test_path_filters.py). These tests hold every pull request job to that
shape and refuse planted jobs that break it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
AGGREGATOR = WORKFLOWS / "required-aggregator.yml"
RULESET = REPO_ROOT / ".github" / "rulesets" / "main.json"
VERSION = re.compile(r"\d+\.\d+")
WAIT_STEP = "Wait for every other check; each must succeed"
WAIT_SCRIPT = "tools/ci/wait_gate_checks.py"
READY = "ready_for_review"

DRAFT_STEP = {
    "name": "Stop on a draft pull request",
    "if": "github.event.pull_request.draft == true",
    "shell": "bash",
    "env": {
        "TITLE": "Gate not run on a draft",
        "MESSAGE": (
            "The gate did not run because the pull request is a draft."
            " It runs when the pull request is marked ready for review."
        ),
    },
    "run": ('echo "::error title=$TITLE::$MESSAGE"\necho "$MESSAGE" >> "$GITHUB_STEP_SUMMARY"\nexit 1\n'),
}


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def triggers(document: dict) -> dict:
    """The `on` mapping; PyYAML reads an unquoted `on` key as the boolean True."""
    on = document.get("on", document.get(True))
    if isinstance(on, str):
        return {on: None}
    if isinstance(on, list):
        return dict.fromkeys(on)
    return on or {}


def pull_request_workflows() -> list[tuple[Path, dict]]:
    return [
        (path, document)
        for path in sorted(WORKFLOWS.glob("*.yml"))
        if "pull_request" in triggers(document := load(path))
    ]


def pull_request_jobs() -> list[tuple[str, dict]]:
    return [
        (f"{path.name}:{job_id}", job)
        for path, document in pull_request_workflows()
        for job_id, job in (document.get("jobs") or {}).items()
    ]


def job_findings(job: dict) -> list[str]:
    """Every way this job could skip, or run its work, on a pull request."""
    findings = []
    steps = job.get("steps") or []
    if not steps or steps[0] != DRAFT_STEP:
        findings.append("first step is not the draft step")
    if any(step == DRAFT_STEP for step in steps[1:]):
        findings.append("draft step repeated after the first step")
    if "if" in job:
        findings.append(f"job condition {job['if']!r}")
    if "needs" in job:
        findings.append(f"needs {job['needs']!r}")
    if "uses" in job:
        findings.append("calls a reusable workflow")
    return findings


def test_pull_request_jobs_exist():
    assert len(pull_request_jobs()) >= 10


@pytest.mark.parametrize("job_id,job", pull_request_jobs(), ids=[name for name, _ in pull_request_jobs()])
def test_every_pull_request_job_has_the_draft_shape(job_id, job):
    assert job_findings(job) == [], job_id


@pytest.mark.parametrize("path,document", pull_request_workflows(), ids=[p.name for p, _ in pull_request_workflows()])
def test_pull_request_triggers_restart_on_ready_for_review(path, document):
    trigger = triggers(document)["pull_request"] or {}
    assert READY in trigger.get("types", []), path.name


GOOD_JOB = {"name": "x", "steps": [DRAFT_STEP, {"run": "true"}]}


@pytest.mark.parametrize(
    "job",
    [
        {"name": "x", "steps": [{"run": "true"}]},
        {"name": "x", "steps": [{"run": "true"}, DRAFT_STEP]},
        {"name": "x", "steps": [{**DRAFT_STEP, "shell": "sh"}]},
        {"name": "x", "steps": [{**DRAFT_STEP, "run": "exit 0\n"}]},
        {"name": "x", "steps": [{**DRAFT_STEP, "if": "github.event.pull_request.draft != true"}]},
        {**GOOD_JOB, "if": "github.event.pull_request.draft != true"},
        {**GOOD_JOB, "needs": "changes"},
        {"name": "x", "uses": "./.github/workflows/other.yml"},
        {"name": "x", "steps": []},
    ],
    ids=["no-draft", "draft-late", "wrong-shell", "draft-passes", "inverted", "job-if", "needs", "reusable", "empty"],
)
def test_planted_jobs_are_refused(job):
    assert job_findings(job)


def test_good_job_passes():
    assert job_findings(GOOD_JOB) == []


def jobs_running(command: str) -> list[dict]:
    starts = re.compile(rf"^\s*{command}\b", re.M)
    return [
        job
        for path in sorted(WORKFLOWS.glob("*.yml"))
        for job in (load(path).get("jobs") or {}).values()
        if any(starts.search(step.get("run", "")) for step in job.get("steps", []))
    ]


def test_codespell_runs_on_every_event():
    """codespell reads the whole tree, so no path filter may skip it.

    Inside the workflow-gated job it was skipped on a pull request that changed only Go
    files, and the misspelling reached main.
    """
    jobs = jobs_running("codespell")
    assert len(jobs) == 1, f"{len(jobs)} jobs run codespell"
    job = jobs[0]
    assert "if" not in job, job.get("if")
    assert "needs" not in job, job.get("needs")
    for step in job["steps"][1:]:
        assert "if" not in step, step


def wait_step() -> dict:
    (step,) = [s for s in load(AGGREGATOR)["jobs"]["required-checks"]["steps"] if s.get("name") == WAIT_STEP]
    return step


def test_aggregator_accepts_no_skip():
    document = load(AGGREGATOR)
    assert "MAY_SKIP" not in (document.get("env") or {})
    step = wait_step()
    assert "uses" not in step
    assert step["run"].startswith(f"python3 -I {WAIT_SCRIPT} ")
    assert "--own required-checks" in step["run"]


GATE_EVENTS = {"push", "pull_request", "merge_group"}
MATRIX_SAMPLE = "sample-flavor"


def aggregator_filter() -> re.Pattern[str]:
    """The `KEEP_CHECKS` pattern of the wait step; the script keeps a check whose name it matches."""
    return re.compile(wait_step()["env"]["KEEP_CHECKS"])


def job_names(gate: bool) -> list[str]:
    """Job names of the workflows a push or pull request starts (gate) or never starts."""
    names = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        document = load(path)
        if bool(GATE_EVENTS & set(triggers(document))) != gate:
            continue
        for job_id, job in (document.get("jobs") or {}).items():
            if "uses" in job and job["uses"].startswith("./.github/workflows/"):
                called_path = REPO_ROOT / job["uses"].removeprefix("./")
                if called_path.exists():
                    called_doc = load(called_path)
                    caller_id = job.get("name", job_id)
                    for cjob_id, cjob in (called_doc.get("jobs") or {}).items():
                        cname = re.sub(r"\$\{\{[^}]*\}\}", MATRIX_SAMPLE, cjob.get("name", cjob_id))
                        names.append(f"{caller_id} / {cname}")
                continue
            names.append(re.sub(r"\$\{\{[^}]*\}\}", MATRIX_SAMPLE, job.get("name", job_id)))
    return names


def test_aggregator_waits_for_every_gate_check():
    """No job a push or pull request starts and no required context may fall out of the wait (ADR-0035)."""
    keep = aggregator_filter()
    names = job_names(gate=True) + required_contexts()
    assert len(names) > 19
    assert [name for name in names if not keep.search(name)] == []


def test_aggregator_skips_only_jobs_no_gate_event_starts():
    """A manual release-matrix build on main's head must not hold required-checks past its bound."""
    keep = aggregator_filter()
    names = job_names(gate=False)
    assert f"Build Image ({MATRIX_SAMPLE})" in names
    assert f"release / Build Image ({MATRIX_SAMPLE})" in names
    assert [name for name in names if keep.search(name)] == []


@pytest.mark.parametrize(
    "name",
    [
        "Build Image",
        "release / Build Image",
        "Sign the Release Checksums v2",
        "release / Sign the Release Checksums v2",
        "Run Build Image (x)",
        "Go Build & Unit Tests",
        "required-checks",
    ],
)
def test_planted_gate_names_are_waited_for(name):
    """Names that only resemble an excluded job stay in the wait."""
    assert aggregator_filter().search(name)


def required_contexts() -> list[str]:
    rules = json.loads(RULESET.read_text(encoding="utf-8"))["rules"]
    (checks,) = [rule for rule in rules if rule["type"] == "required_status_checks"]
    return [check["context"] for check in checks["parameters"]["required_status_checks"]]


def test_required_contexts_name_no_toolchain_version():
    """A version bump from the update bot must not rename a required check."""
    contexts = required_contexts()
    assert len(contexts) == 19
    assert [name for name in contexts if VERSION.search(name)] == []


@pytest.mark.parametrize("name", ["Go 1.27 Build & Unit Tests", "Python 3.14 Tests", "Node 24.1"])
def test_planted_versioned_context_is_found(name):
    assert VERSION.search(name)
