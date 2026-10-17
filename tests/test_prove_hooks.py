# Copyright 2026 Lusoris
"""Verification that the hook proof fails unless every hook behaves as issue #80 requires.

`tools/ci/prove_hooks.py` runs the hooks of lefthook.yml in a temporary clone. It needs the
pinned Praetor engine, which CI does not install, so the tests below replace each command
with a scripted reply: the run passes only when every check passes, every planted commit and
pre-push job is refused with its reason and HEAD in place, the baseline is unchanged and the
gofmt job commits the formatted file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "ci" / "prove_hooks.py"

_spec = importlib.util.spec_from_file_location("prove_hooks", SCRIPT)
proof = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(proof)

REFUSED_COMMITS = {
    "negative": proof.CONTEXT_REASON,
    "boundary": proof.PLANT_REASON,
    "govet": proof.VET_REASON,
    "reuse-lint": proof.LICENCE_REASON,
}
REFUSED_PUSHES = {
    "flavor-audit": proof.FLAVOR_REASON,
    "audit": proof.PLANT_REASON,
    "security": proof.VULN_REASON,
    "gate": proof.GATE_REASON,
}


class Clone:
    """A scripted clone: each command gets the reply the test sets."""

    def __init__(self, tmp_path: Path) -> None:
        self.path = tmp_path
        (tmp_path / proof.BASELINE).write_text("{}", encoding="utf-8")
        for name in (proof.CONTEXT_FILE, proof.PLANT_FILE, proof.FLAVOR_FILE):
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text("", encoding="utf-8")
        self.checks = {"compile-context": 0, "audit": 0}
        # Commit replies by case name: (status, output, moves HEAD).
        self.commits = {name: [1, reason, False] for name, reason in REFUSED_COMMITS.items()}
        self.commits["gofmt"] = [0, "", True]
        self.commits["failing test"] = [0, "", True]
        self.committed = proof.FORMATTED
        # Pre-push replies by job: the first run is on the clean clone, the second on the plant.
        self.pushes = {job: [[0, ""], [1, reason]] for job, reason in REFUSED_PUSHES.items()}
        self.push_runs = dict.fromkeys(REFUSED_PUSHES, 0)
        self.touch_baseline = False
        self.heads = 0

    def commit(self, message: str) -> tuple[int, str]:
        status, output, moves = self.commits[message.removeprefix("test: planted ")]
        if moves:
            self.heads += 1
        if self.touch_baseline and message.endswith("boundary"):
            with (self.path / proof.BASELINE).open("a", encoding="utf-8") as handle:
                handle.write(" ")
        return status, output

    def push(self, job: str) -> tuple[int, str]:
        reply = self.pushes[job][min(self.push_runs[job], 1)]
        self.push_runs[job] += 1
        return reply[0], reply[1]

    def run(self, args: list[str], cwd: Path) -> tuple[int, str]:
        if args[:2] == proof.ENGINE:
            return self.checks[args[2]], ""
        if args[:5] == proof.PUSH:
            return self.push(args[5])
        if args[:2] == ["git", "rev-parse"]:
            return 0, f"head{self.heads}"
        if args[:2] == ["git", "commit"]:
            return self.commit(args[-1])
        if args[:2] == ["git", "show"]:
            return 0, self.committed
        return 0, ""


@pytest.fixture
def clone(tmp_path, monkeypatch):
    fake = Clone(tmp_path)
    monkeypatch.setattr(proof, "run", fake.run)
    return fake


def test_refusing_hooks_pass(clone):
    lines = proof.prove(clone.path)
    assert [line.split(":")[0] for line in lines] == [
        "positive",
        "negative",
        "boundary",
        "pre-commit govet",
        "pre-commit reuse-lint",
        "pre-commit gofmt",
        "pre-push positive",
        "pre-push flavor-audit",
        "pre-push audit",
        "pre-push security",
        "pre-push gate",
    ]
    assert clone.push_runs == dict.fromkeys(REFUSED_PUSHES, 2)


def test_skip_gate_names_the_skip(clone):
    lines = proof.prove(clone.path, skip_gate=True)
    assert lines[-1] == "pre-push gate: skipped (--skip-gate), not proven"
    assert clone.push_runs["gate"] == 0


@pytest.mark.parametrize("check", ["compile-context", "audit"])
def test_planted_failing_check_fails(clone, check):
    clone.checks[check] = 1
    with pytest.raises(proof.ProofError, match="on the fresh clone"):
        proof.prove(clone.path)


@pytest.mark.parametrize("case", REFUSED_COMMITS)
def test_planted_accepted_commit_fails(clone, case):
    clone.commits[case][0] = 0
    with pytest.raises(proof.ProofError, match=f"^{case}: the planted defect was accepted"):
        proof.prove(clone.path)


@pytest.mark.parametrize("case", REFUSED_COMMITS)
def test_planted_moved_head_fails(clone, case):
    clone.commits[case][2] = True
    with pytest.raises(proof.ProofError, match=f"^{case}: HEAD moved"):
        proof.prove(clone.path)


@pytest.mark.parametrize(("case", "reason"), REFUSED_COMMITS.items())
def test_planted_refusal_without_its_reason_fails(clone, case, reason):
    clone.commits[case][1] = "refused for another reason"
    with pytest.raises(proof.ProofError, match=f"^{case}: refused without naming"):
        proof.prove(clone.path)


def test_planted_baseline_change_fails(clone):
    clone.touch_baseline = True
    with pytest.raises(proof.ProofError, match=f"boundary: {proof.BASELINE} changed"):
        proof.prove(clone.path)


def test_planted_refused_format_commit_fails(clone):
    clone.commits["gofmt"] = [1, "gofmt failed", False]
    with pytest.raises(proof.ProofError, match="^gofmt: the commit was refused"):
        proof.prove(clone.path)


def test_planted_unformatted_commit_fails(clone):
    clone.committed = proof.UNFORMATTED
    with pytest.raises(proof.ProofError, match="^gofmt: .* was committed unformatted"):
        proof.prove(clone.path)


@pytest.mark.parametrize("job", REFUSED_PUSHES)
def test_planted_failing_push_job_on_the_clean_clone_fails(clone, job):
    clone.pushes[job][0] = [1, "planted"]
    with pytest.raises(proof.ProofError, match=f"^pre-push {job} exited 1 on the fresh clone"):
        proof.prove(clone.path)


@pytest.mark.parametrize("job", REFUSED_PUSHES)
def test_planted_accepted_push_fails(clone, job):
    clone.pushes[job][1] = [0, ""]
    with pytest.raises(proof.ProofError, match=f"^pre-push {job}: the planted defect was accepted"):
        proof.prove(clone.path)


@pytest.mark.parametrize("job", REFUSED_PUSHES)
def test_planted_push_refusal_without_its_reason_fails(clone, job):
    clone.pushes[job][1] = [1, "refused for another reason"]
    with pytest.raises(proof.ProofError, match=f"^pre-push {job}: refused without naming"):
        proof.prove(clone.path)


def test_gate_refusal_by_a_broken_devcontainer_fails(clone):
    clone.pushes["gate"][1] = [1, "5. [FAIL] Race-Detector Tests\nno space left on device"]
    with pytest.raises(proof.ProofError, match="^pre-push gate: refused without naming"):
        proof.prove(clone.path)


def test_refused_gate_plant_commit_fails(clone):
    clone.commits["failing test"] = [1, "vet failed", False]
    with pytest.raises(proof.ProofError, match="^gate: the commit was refused"):
        proof.prove(clone.path)


def test_planted_commit_restores_the_file(clone):
    target = clone.path / proof.PLANT_FILE
    status, _output, heads = proof.planted_commit(clone.path, proof.PLANT_FILE, proof.PLANT, "test: planted boundary")
    assert status == 1 and heads == ("head0", "head0")
    # The scripted reset does not restore; the real one does. The plant itself was written.
    assert target.read_text(encoding="utf-8") == proof.PLANT


def test_plant_creates_a_missing_file(tmp_path):
    proof.plant(tmp_path, proof.VET_FILE, proof.VET)
    assert (tmp_path / proof.VET_FILE).read_text(encoding="utf-8") == proof.VET


def test_failed_setup_step_fails(monkeypatch):
    monkeypatch.setattr(proof, "run", lambda args, cwd: (128, "fatal: no origin"))
    with pytest.raises(proof.ProofError, match="exited 128"):
        proof.must(["git", "remote", "get-url", "origin"], ROOT)


def test_main_reports_a_failed_proof(monkeypatch, capsys):
    monkeypatch.setattr(proof, "run", lambda args, cwd: (1, "planted"))
    assert proof.main([]) == 1
    assert "::error::hook proof failed" in capsys.readouterr().err


def test_proof_source_holds_no_planted_text():
    source = SCRIPT.read_text(encoding="utf-8")
    assert proof.PLANT.strip() not in source
    assert proof.LICENCE.strip() not in source
