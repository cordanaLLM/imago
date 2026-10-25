# Copyright 2026 Lusoris
"""Verification of the per-job path filters in .github/path-filters.yml (ADR-0027).

A filtered job runs its draft step, checks out, runs dorny/paths-filter on the shared
filter file and gates every later step on the filter named after the job. A pull request
that changes none of its paths passes the job without running the work; a push or a
scheduled run runs every step. These tests hold each filtered job to that shape, the
filter keys equal to the filtered jobs, and every filter pattern to a tracked file.
"""

from __future__ import annotations

import re
import subprocess
from functools import cache
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
FILTER_FILE = ".github/path-filters.yml"
FILTER_ACTION = "dorny/paths-filter@"
CHECKOUT_ACTION = "actions/checkout@"
# Anchored filters the job filters combine; no job reads them by name.
BUILDING_BLOCKS = {"packer", "shell", "go", "python", "docs", "workflows"}
FILTERED_WORKFLOWS = ("ci.yml", "security-scans.yml")


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def gate(job_id: str) -> str:
    return f"github.event_name != 'pull_request' || steps.filter.outputs.{job_id} == 'true'"


def notice_condition(job_id: str) -> str:
    return f"github.event_name == 'pull_request' && steps.filter.outputs.{job_id} != 'true'"


def is_gated(condition: str | None, job_id: str) -> bool:
    """The step runs only under the job's gate: bare, or as the right conjunct."""
    if condition == gate(job_id):
        return True
    return isinstance(condition, str) and condition.endswith(f") && ({gate(job_id)})") and condition.startswith("(")


def filter_index(steps: list[dict]) -> int | None:
    found = [i for i, step in enumerate(steps) if step.get("uses", "").startswith(FILTER_ACTION)]
    return found[0] if len(found) == 1 else None


def filtered_job_findings(job_id: str, job: dict) -> list[str]:
    """Every way this filtered job could run unfiltered work or skip its filter."""
    steps = job.get("steps") or []
    index = filter_index(steps)
    if index is None:
        return ["not exactly one paths-filter step"]
    findings = []
    step = steps[index]
    if step.get("id") != "filter":
        findings.append("filter step id is not 'filter'")
    if step.get("if") != "github.event_name == 'pull_request'":
        findings.append(f"filter step condition {step.get('if')!r}")
    if (step.get("with") or {}).get("filters") != FILTER_FILE:
        findings.append("filter step does not read the shared filter file")
    if not any(s.get("uses", "").startswith(CHECKOUT_ACTION) for s in steps[:index]):
        findings.append("no checkout before the filter step")
    rest = steps[index + 1 :]
    if not rest or rest[0].get("if") != notice_condition(job_id) or "uses" in rest[0]:
        findings.append("second step after the filter is not the notice step")
    for later in rest[1:]:
        if not is_gated(later.get("if"), job_id):
            findings.append(f"step {later.get('name') or later.get('uses')!r} not gated: {later.get('if')!r}")
    return findings


def filtered_jobs() -> list[tuple[str, dict]]:
    return [
        (job_id, job)
        for name in FILTERED_WORKFLOWS
        for job_id, job in load(WORKFLOWS / name)["jobs"].items()
        if filter_index(job.get("steps") or []) is not None
        or any(step.get("uses", "").startswith(FILTER_ACTION) for step in job.get("steps") or [])
    ]


def filters() -> dict:
    return load(REPO_ROOT / FILTER_FILE)


def flatten(patterns: list) -> list[str]:
    """A job filter is a list of patterns and of anchored lists of patterns, one level deep."""
    flat: list[str] = []
    for item in patterns:
        nested = item if isinstance(item, list) else [item]
        assert all(isinstance(pattern, str) for pattern in nested), f"filter nests deeper than one level: {item!r}"
        flat.extend(nested)
    return flat


def glob_regex(pattern: str) -> re.Pattern[str]:
    """picomatch semantics for the shapes used: '**/' any directories, '**' anything, '*' one segment."""
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


@cache
def tracked_files() -> tuple[str, ...]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True, timeout=30)
    return tuple(name for name in result.stdout.decode("utf-8").split("\0") if name)


def test_filtered_jobs_are_the_expected_set():
    assert {job_id for job_id, _ in filtered_jobs()} == {
        "lint-packer",
        "lint-shell",
        "lint-workflows",
        "lint-python",
        "test-go",
        "test-python",
        "docs-strict",
        "semgrep",
        "trivy",
        "govulncheck",
    }


@pytest.mark.parametrize("job_id,job", filtered_jobs(), ids=[job_id for job_id, _ in filtered_jobs()])
def test_filtered_job_shape(job_id, job):
    assert filtered_job_findings(job_id, job) == []


def test_filter_keys_equal_filtered_jobs_and_building_blocks():
    assert set(filters()) == {job_id for job_id, _ in filtered_jobs()} | BUILDING_BLOCKS


@pytest.mark.parametrize("key", sorted(filters()))
def test_every_pattern_matches_a_tracked_file(key):
    for pattern in flatten(filters()[key]):
        regex = glob_regex(pattern)
        assert any(regex.match(name) for name in tracked_files()), f"{key}: {pattern} matches no tracked file"


@pytest.mark.parametrize("job_id,job", filtered_jobs(), ids=[job_id for job_id, _ in filtered_jobs()])
def test_filter_file_change_runs_every_filtered_job(job_id, job):
    """Editing the filters or the job's own workflow must run the job."""
    patterns = [glob_regex(p) for p in flatten(filters()[job_id])]
    (workflow,) = [name for name in FILTERED_WORKFLOWS if job_id in load(WORKFLOWS / name)["jobs"]]
    for path in (FILTER_FILE, f".github/workflows/{workflow}"):
        assert any(regex.match(path) for regex in patterns), f"{job_id}: {path} not in its filter"


CHECKOUT = {"uses": "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"}


def good_steps(job_id: str) -> list[dict]:
    return [
        {"name": "Stop on a draft pull request"},
        CHECKOUT,
        {
            "id": "filter",
            "if": "github.event_name == 'pull_request'",
            "uses": "dorny/paths-filter@ceb8a2b8f2d89434be7ff52d3de7ec3738c5cc9d",
            "with": {"filters": FILTER_FILE},
        },
        {"if": notice_condition(job_id), "run": "echo"},
        {"if": gate(job_id), "run": "make"},
        {"if": f"(!cancelled()) && ({gate(job_id)})", "run": "upload"},
    ]


def test_good_filtered_job_passes():
    assert filtered_job_findings("x", {"steps": good_steps("x")}) == []


def planted(mutate) -> dict:
    steps = good_steps("x")
    mutate(steps)
    return {"steps": steps}


@pytest.mark.parametrize(
    "job",
    [
        planted(lambda s: s[4].pop("if")),
        planted(lambda s: s[4].update({"if": gate("y")})),
        planted(lambda s: s[5].update({"if": f"!cancelled() || {gate('x')}"})),
        planted(lambda s: s[4].update({"if": f"{gate('x')} || always()"})),
        planted(lambda s: s[2]["with"].update({"filters": "other.yml"})),
        planted(lambda s: s[2].update({"id": "paths"})),
        planted(lambda s: s[2].pop("if")),
        planted(lambda s: s.pop(1)),
        planted(lambda s: s.pop(3)),
        planted(lambda s: s.pop(2)),
    ],
    ids=[
        "ungated-step",
        "wrong-filter-key",
        "or-cancelled",
        "or-always",
        "other-filter-file",
        "renamed-id",
        "filter-on-push",
        "no-checkout",
        "no-notice",
        "no-filter",
    ],
)
def test_planted_filtered_jobs_are_refused(job):
    assert filtered_job_findings("x", job)


@pytest.mark.parametrize(
    "pattern,hit,miss",
    [
        ("**/*.py", "a/b/c.py", "a/b/c.pyc"),
        ("**/*.py", "c.py", "c.txt"),
        ("cmd/**", "cmd/a/b.go", "cmdx/a.go"),
        (".github/*.json", ".github/a.json", ".github/rulesets/main.json"),
        ("scripts/*.sh", "scripts/a.sh", "scripts/x/a.sh"),
        (".github/requirements/**", ".github/requirements/sast.txt", ".github/other/sast.txt"),
    ],
)
def test_glob_regex_semantics(pattern, hit, miss):
    regex = glob_regex(pattern)
    assert regex.match(hit) and not regex.match(miss)


@pytest.mark.parametrize(
    "path",
    [
        ".github/requirements/sast.txt",
        ".github/requirements/sast-overrides.txt",
    ],
)
def test_test_python_filter_matches_sast_requirements(path: str) -> None:
    """Modifying SAST locks or overrides must run the pytest suite (governance floor checks, #204)."""
    patterns = [glob_regex(p) for p in flatten(filters()["test-python"])]
    assert any(regex.match(path) for regex in patterns), f"test-python: {path} not in its filter"
