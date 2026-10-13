# Copyright 2026 Lusoris
"""Verification that the hook proof fails unless every hook behaves as issue #80 requires.

`tools/ci/prove_hooks.py` runs the hooks of lefthook.yml in a temporary clone. It needs the
pinned Praetor engine, which CI does not install, so the tests below replace each command
with a scripted reply: the run passes only when both checks pass and both planted commits
are refused with their reason, HEAD in place and the baseline unchanged.
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


class Clone:
    """A scripted clone: each command gets the reply the test sets."""

    def __init__(self, tmp_path: Path) -> None:
        self.path = tmp_path
        (tmp_path / proof.BASELINE).write_text("{}", encoding="utf-8")
        (tmp_path / "tools" / "ci").mkdir(parents=True)
        for name in (proof.CONTEXT_FILE, proof.PLANT_FILE):
            (tmp_path / name).write_text("", encoding="utf-8")
        self.checks = {"compile-context": 0, "audit": 0}
        self.commit = {"status": 1, "reasons": [proof.CONTEXT_REASON, proof.PLANT_REASON], "moves": False}
        self.touch_baseline = False
        self.heads = 0

    def run(self, args: list[str], cwd: Path) -> tuple[int, str]:
        if args[:2] == proof.ENGINE:
            return self.checks[args[2]], ""
        if args[1] == "rev-parse":
            return 0, f"head{self.heads}"
        if args[1] == "commit":
            if self.commit["moves"]:
                self.heads += 1
            if self.touch_baseline:
                with (self.path / proof.BASELINE).open("a", encoding="utf-8") as handle:
                    handle.write(" ")
            return self.commit["status"], " ".join(self.commit["reasons"])
        return 0, ""


@pytest.fixture
def clone(tmp_path, monkeypatch):
    fake = Clone(tmp_path)
    monkeypatch.setattr(proof, "run", fake.run)
    return fake


def test_refusing_hooks_pass(clone):
    lines = proof.prove(clone.path)
    assert [line.split(":")[0] for line in lines] == ["positive", "negative", "boundary"]


@pytest.mark.parametrize("check", ["compile-context", "audit"])
def test_planted_failing_check_fails(clone, check):
    clone.checks[check] = 1
    with pytest.raises(proof.ProofError, match="on the fresh clone"):
        proof.prove(clone.path)


def test_planted_accepted_commit_fails(clone):
    clone.commit["status"] = 0
    with pytest.raises(proof.ProofError, match="negative: the commit was accepted"):
        proof.prove(clone.path)


def test_planted_moved_head_fails(clone):
    clone.commit["moves"] = True
    with pytest.raises(proof.ProofError, match="HEAD moved"):
        proof.prove(clone.path)


@pytest.mark.parametrize(("reason", "case"), [(proof.CONTEXT_REASON, "negative"), (proof.PLANT_REASON, "boundary")])
def test_planted_refusal_without_its_reason_fails(clone, reason, case):
    clone.commit["reasons"].remove(reason)
    with pytest.raises(proof.ProofError, match=f"{case}: refused without naming"):
        proof.prove(clone.path)


def test_planted_baseline_change_fails(clone):
    clone.touch_baseline = True
    with pytest.raises(proof.ProofError, match=f"boundary: {proof.BASELINE} changed"):
        proof.prove(clone.path)


def test_planted_commit_restores_the_file(clone):
    target = clone.path / proof.PLANT_FILE
    status, _output, heads = proof.planted_commit(clone.path, proof.PLANT_FILE, proof.PLANT, "test")
    assert status == 1 and heads == ("head0", "head0")
    # The scripted reset does not restore; the real one does. The plant itself was written.
    assert target.read_text(encoding="utf-8") == proof.PLANT


def test_failed_setup_step_fails(monkeypatch):
    monkeypatch.setattr(proof, "run", lambda args, cwd: (128, "fatal: no origin"))
    with pytest.raises(proof.ProofError, match="exited 128"):
        proof.must(["git", "remote", "get-url", "origin"], ROOT)


def test_main_reports_a_failed_proof(monkeypatch, capsys):
    monkeypatch.setattr(proof, "run", lambda args, cwd: (1, "planted"))
    assert proof.main([]) == 1
    assert "::error::hook proof failed" in capsys.readouterr().err


def test_proof_source_holds_no_planted_call():
    assert proof.PLANT.strip() not in SCRIPT.read_text(encoding="utf-8")
