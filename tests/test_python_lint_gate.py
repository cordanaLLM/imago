# Copyright 2026 Lusoris
"""Verification of the Ruff gate and of its dated exemptions.

`make lint` and the Ruff job of ci.yml run `ruff check .` and `ruff format --check .`
over every Python file. Four files written by `praetorctl adopt` are not edited by hand;
ruff.toml lists each with the exact rules it breaks and keeps it from the formatter, and
every such line names the engine issue and the last valid day. These tests fail when a
line lacks that note, when the day has passed and when an exemption is no longer needed.
"""

from __future__ import annotations

import datetime
import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
RUFF_TOML = REPO_ROOT / "ruff.toml"
MAKEFILE = REPO_ROOT / "Makefile"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
LINT_LOCK = REPO_ROOT / ".github" / "requirements" / "lint.txt"

# The note every exemption line of ruff.toml ends with: the engine issue and the last valid day.
EXEMPTION_NOTE = re.compile(r" # cordanaLLM/praetor#(?P<issue>[1-9][0-9]*), ends (?P<end>\d{4}-\d{2}-\d{2})$")
# One line under [lint.per-file-ignores] and one in the formatter's exclude list.
LINES_PER_EXEMPT_FILE = 2
# 90 days after the decision of 2026-10-11 that admitted the exemptions; none may end later.
LATEST_EXEMPTION_END = datetime.date(2027, 1, 9)
RUFF_BOUND_S = 60
GATE_COMMANDS = ("ruff check .", "ruff format --check .")


def ruff_ignores() -> dict[str, set[str]]:
    """Return the per-file rule lists of ruff.toml."""
    config = tomllib.loads(RUFF_TOML.read_text(encoding="utf-8"))
    return {path: set(rules) for path, rules in config["lint"].get("per-file-ignores", {}).items()}


def ruff_format_excludes() -> set[str]:
    """Return the paths ruff.toml keeps from the formatter."""
    config = tomllib.loads(RUFF_TOML.read_text(encoding="utf-8"))
    return set(config["format"].get("exclude", []))


def exemption_lines(path: str) -> list[str]:
    """Return the lines of ruff.toml that exempt `path`."""
    lines = RUFF_TOML.read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line.strip().startswith(f'"{path}"')]


def exemption_end(line: str) -> datetime.date:
    """Return the last valid day an exemption line names; a line without the note fails."""
    note = EXEMPTION_NOTE.search(line)
    assert note, f"ruff.toml exemption line names no engine issue and end date: {line.strip()}"
    return datetime.date.fromisoformat(note["end"])


def exemption_ends() -> dict[str, list[datetime.date]]:
    """Return the end dates of every exempted path, one per ruff.toml line that names it."""
    paths = sorted(set(ruff_ignores()) | ruff_format_excludes())
    return {path: [exemption_end(line) for line in exemption_lines(path)] for path in paths}


def ended(ends: dict[str, list[datetime.date]], today: datetime.date) -> list[str]:
    """Return the paths with an end date before `today`; the end date itself still counts."""
    return sorted(path for path, days in ends.items() if any(day < today for day in days))


def run_ruff(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    """Run ruff from the repository root; a workstation without ruff fails, it does not skip."""
    ruff = shutil.which("ruff")
    assert ruff, "ruff is not installed; the lint gate and this test need it (.github/requirements/lint.txt)"
    return subprocess.run(
        [ruff, *arguments], cwd=REPO_ROOT, capture_output=True, text=True, timeout=RUFF_BOUND_S, check=False
    )


def reported_rules(path: str) -> set[str]:
    """Return the rules ruff reports for `path` when no per-file rule list applies."""
    res = run_ruff(["check", "--no-cache", "--output-format", "json", "--config", "lint.per-file-ignores = {}", path])
    assert res.returncode in (0, 1), f"ruff check failed on {path}: {res.stderr}"
    return {finding["code"] for finding in json.loads(res.stdout)}


def formatter_accepts(path: str) -> bool:
    """Say whether `path` is formatted as ruff.toml asks, with no formatter exclusion applied."""
    res = run_ruff(["format", "--check", "--no-cache", "--config", "format.exclude = []", path])
    assert res.returncode in (0, 1), f"ruff format failed on {path}: {res.stderr}"
    return res.returncode == 0


class TestRuffExemptions:
    def test_both_ruff_lists_name_the_same_files(self) -> None:
        """A file exempt from rules is kept from the formatter and the reverse, nothing else."""
        assert ruff_ignores(), "ruff.toml lists no exempt file; remove these tests with the lists"
        assert set(ruff_ignores()) == ruff_format_excludes()

    def test_every_exemption_line_names_the_engine_issue_and_an_end_date(self) -> None:
        """Each exempt file has its two lines, and both carry the note."""
        for path, days in exemption_ends().items():
            assert len(days) == LINES_PER_EXEMPT_FILE, f"expected two ruff.toml lines for {path}, found {len(days)}"

    def test_no_exemption_has_passed_its_date(self) -> None:
        """An exemption past its end date fails here, like a missing one."""
        ends = exemption_ends()
        assert ended(ends, datetime.date.today()) == []
        too_late = sorted(path for path, days in ends.items() if any(day > LATEST_EXEMPTION_END for day in days))
        assert too_late == [], f"end date after {LATEST_EXEMPTION_END}: {too_late}"

    @pytest.mark.parametrize(
        ("days_after_end", "expected"),
        [(-1, []), (0, []), (1, ["a.py"])],
    )
    def test_end_date_is_the_last_valid_day(self, days_after_end: int, expected: list[str]) -> None:
        """The day before and the end date itself pass; the day after is reported."""
        end = datetime.date(2027, 1, 9)
        today = end + datetime.timedelta(days=days_after_end)
        assert ended({"a.py": [end, end]}, today) == expected

    def test_every_listed_rule_still_reports(self) -> None:
        """A rule list that no longer matches what ruff reports must be corrected or removed."""
        ignores = ruff_ignores()
        assert ignores
        for path, rules in sorted(ignores.items()):
            assert (REPO_ROOT / path).is_file(), f"{path} is listed in ruff.toml and does not exist"
            assert reported_rules(path) == rules, f"ruff.toml lists {sorted(rules)} for {path}"

    def test_every_formatter_exclusion_is_still_needed(self) -> None:
        """A file the formatter accepts must leave the exclusion list."""
        excludes = ruff_format_excludes()
        assert excludes
        accepted = sorted(path for path in excludes if formatter_accepts(path))
        assert accepted == [], f"the formatter accepts these files; remove their exclusion: {accepted}"

    def test_a_clean_file_reports_no_rule(self) -> None:
        """The probe itself must tell a clean file from a listed one."""
        assert reported_rules("tests/test_python_lint_gate.py") == set()
        assert formatter_accepts("tests/test_python_lint_gate.py")


class TestRuffGateWiring:
    def test_make_lint_runs_both_ruff_commands(self) -> None:
        """`make lint` runs the linter and the formatter check over the whole tree."""
        makefile = MAKEFILE.read_text(encoding="utf-8")
        recipe = makefile[makefile.index("\nlint:") : makefile.index("All lint checks passed")]
        for command in GATE_COMMANDS:
            assert f"@{command}\n" in recipe, f"`make lint` does not run `{command}`"

    def test_ci_runs_both_ruff_commands_from_the_hash_lock(self) -> None:
        """One CI job installs ruff from the lint lock and runs the two commands of `make lint`."""
        workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
        job = workflow["jobs"]["lint-python"]
        runs = [step.get("run", "") for step in job["steps"]]
        assert any("pip install --require-hashes -r .github/requirements/lint.txt" in run for run in runs)
        for command in GATE_COMMANDS:
            assert command in [run.strip() for run in runs], f"the Ruff job does not run `{command}`"

    def test_lint_lock_pins_ruff(self) -> None:
        """The lock names one exact ruff version."""
        pins = [line for line in LINT_LOCK.read_text(encoding="utf-8").splitlines() if line.startswith("ruff==")]
        assert len(pins) == 1, f"expected one ruff pin in {LINT_LOCK.name}, found {pins}"
