#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Prove that every refusing Git hook refuses a planted defect (issue #80).

The hooks of lefthook.yml run through the pinned Praetor engine, which no CI job installs,
so CI cannot show them refusing anything. This tool clones the committed tree into a
temporary directory, installs the hooks there and runs the cases of issue #80 for each job:

  positive  `compile-context --verify` and `audit --offline` exit 0 on the fresh clone, and
            so does every pre-push job;
  negative  a commit with a hand edit to CLAUDE.md is refused as out of sync with AGENTS.md;
  boundary  a commit that adds a banned eval call to a touched file is refused as HISS-08,
            and the recorded baseline is unchanged afterwards;
  pre-commit  a go vet finding and an unlisted licence are refused, and an unformatted Go
            file is committed in gofmt form (the gofmt job repairs, it does not refuse);
  pre-push  `lefthook run pre-push --force --command <job>` fails for a missing flavor
            template (flavor-audit), an uncommitted eval call (audit), a called vulnerable
            dependency (security) and a committed failing test (gate).

A refusal counts only when the step exits non-zero, HEAD does not move and the output names
the expected reason. The post-commit jobs only record state and refuse nothing. The checkout
this runs from is never changed. The clone takes the origin URL and default branch of the
checkout, because the audit reads both, and its push URL is disabled so nothing leaves it.
The security case fetches an old module version, so it needs network access. The gate runs
in the engine's devcontainer; `--skip-gate` leaves both gate cases out and says so.

Usage:
  python3 -I tools/ci/prove_hooks.py [--skip-gate]        (or: make prove-hooks)
"""

import argparse
import hashlib
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
STEP_TIMEOUT_S = 1800
ENGINE = ["sh", ".config/lefthook/engine.sh"]
PUSH = ["lefthook", "run", "pre-push", "--force", "--command"]
PUSH_JOBS = ("security", "flavor-audit", "audit", "gate")
# Stable, uncoloured tool output, so the reasons below match on every host locale.
QUIET_ENV = {"LC_ALL": "C", "NO_COLOR": "1"}
BASELINE = ".standards-baseline.json"
CONTEXT_FILE = "CLAUDE.md"
CONTEXT_REASON = "CLAUDE.md is out of sync with AGENTS.md"
PLANT_FILE = "tools/ci/trivy_coverage.py"
PLANT_REASON = f"[HISS-08] {PLANT_FILE}"
# Planted texts that would trip a check of this repository are assembled at run time,
# so this file holds no infraction.
PLANT = "\n\ndef planted(text):\n    return ev" + "al(text)\n"
VET_FILE = "pkg/reason/planted_vet.go"
VET = 'package reason\n\nimport "fmt"\n\nvar plantedVet = fmt.Sprintf("%d", "text")\n'
VET_REASON = 'fmt.Sprintf format %d has arg "text" of wrong type string'
LICENCE_FILE = "tools/ci/planted_licence.txt"
LICENCE = "# SPDX-" + "License-Identifier: 0BSD\n"
LICENCE_REASON = "'0BSD' found in:"
FORMAT_FILE = "pkg/reason/planted_format.go"
UNFORMATTED = "package reason\n\nfunc plantedFormat( ) int {\nreturn 1\n}\n"
FORMATTED = "package reason\n\nfunc plantedFormat() int {\n\treturn 1\n}\n"
FLAVOR_FILE = ".yamllint.yml"
FLAVOR_REASON = f"Missing Templates:\n  - {FLAVOR_FILE}"
VULN_MODULE = "gopkg.in/yaml.v2@v2.2.2"
VULN_FILE = "pkg/reason/planted_vuln.go"
# Exported: govulncheck reports an unexported, uncalled function as "imported but not called".
VULN = (
    'package reason\n\nimport "gopkg.in/yaml.v2"\n\n'
    "func PlantedVuln(data []byte) error {\n\tvar out any\n\treturn yaml.Unmarshal(data, &out)\n}\n"
)
VULN_REASON = "GO-2020-0036: gopkg.in/yaml.v2.Unmarshal is called"
GATE_FILE = "pkg/reason/planted_gate_test.go"
GATE = (
    'package reason_test\n\nimport "testing"\n\n'
    'func TestPlantedFailure(t *testing.T) {\n\tt.Fatal("planted failure")\n}\n'
)
GATE_REASON = "--- FAIL: TestPlantedFailure"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class ProofError(Exception):
    """A hook that did not behave as the case requires."""


def run(args: list[str], cwd: pathlib.Path) -> tuple[int, str]:
    env = {**os.environ, **QUIET_ENV}
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=STEP_TIMEOUT_S, check=False)
    return result.returncode, ANSI.sub("", result.stdout + result.stderr)


def must(args: list[str], cwd: pathlib.Path) -> str:
    status, output = run(args, cwd)
    if status != 0:
        raise ProofError(f"{' '.join(args[:3])} exited {status}: {output.strip()[-200:]}")
    return output.strip()


def head(clone: pathlib.Path) -> str:
    return must(["git", "rev-parse", "HEAD"], clone)


def make_clone(clone: pathlib.Path) -> None:
    """Clone the checkout, take its origin and default branch, and install the hooks."""
    url = must(["git", "remote", "get-url", "origin"], ROOT)
    default = must(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], ROOT)
    must(["git", "clone", "--quiet", str(ROOT), str(clone)], ROOT)
    must(["git", "remote", "set-url", "origin", url], clone)
    must(["git", "remote", "set-url", "--push", "origin", "no-push"], clone)
    must(["git", "symbolic-ref", "refs/remotes/origin/HEAD", f"refs/remotes/{default}"], clone)
    must(["lefthook", "install"], clone)


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expect_pass(name: str, result: tuple[int, str]) -> None:
    status, output = result
    if status != 0:
        failures = [line.strip() for line in output.splitlines() if "[FAIL]" in line]
        raise ProofError(f"{name} exited {status} on the fresh clone: {'; '.join(failures[-3:]) or 'no [FAIL] line'}")


def expect_refusal(name: str, status: int, output: str, reason: str, heads: tuple[str, str]) -> None:
    """Raise unless the step failed, left HEAD in place and named the reason."""
    if status == 0:
        raise ProofError(f"{name}: the planted defect was accepted")
    if heads[0] != heads[1]:
        raise ProofError(f"{name}: HEAD moved from {heads[0]} to {heads[1]}")
    if reason not in output:
        raise ProofError(f"{name}: refused without naming {reason!r}")


def expect_commit(name: str, status: int, output: str, heads: tuple[str, str]) -> None:
    """Raise unless the commit went through."""
    if status != 0 or heads[0] == heads[1]:
        raise ProofError(f"{name}: the commit was refused: {output.strip()[-200:]}")


def plant(clone: pathlib.Path, path: str, text: str) -> None:
    """Append text to path; a missing file is created."""
    target = clone / path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(text)


def restore(clone: pathlib.Path, base: str) -> None:
    must(["git", "reset", "--quiet", "--hard", base], clone)
    must(["git", "clean", "--quiet", "--force", "-d"], clone)


def try_commit(clone: pathlib.Path, path: str, text: str, message: str) -> tuple[int, str, tuple[str, str]]:
    """Plant text in path and try to commit it; the caller restores the clone."""
    before = head(clone)
    plant(clone, path, text)
    must(["git", "add", "--", path], clone)
    status, output = run(["git", "commit", "--quiet", "--signoff", "--no-gpg-sign", "-m", message], clone)
    return status, output, (before, head(clone))


def planted_commit(clone: pathlib.Path, path: str, text: str, message: str) -> tuple[int, str, tuple[str, str]]:
    """Plant text in path, try to commit it, then restore the clone."""
    status, output, heads = try_commit(clone, path, text, message)
    restore(clone, heads[0])
    return status, output, heads


def refused_commit(clone: pathlib.Path, name: str, path: str, text: str, reason: str) -> None:
    status, output, heads = planted_commit(clone, path, text, f"test: planted {name}")
    expect_refusal(name, status, output, reason, heads)


def prove_repair(clone: pathlib.Path) -> None:
    """The gofmt job rewrites the staged file, so the commit holds the formatted text."""
    status, output, heads = try_commit(clone, FORMAT_FILE, UNFORMATTED, "test: planted gofmt")
    committed = must(["git", "show", f"HEAD:{FORMAT_FILE}"], clone) if status == 0 else ""
    restore(clone, heads[0])
    expect_commit("gofmt", status, output, heads)
    if committed != FORMATTED.strip():
        raise ProofError(f"gofmt: {FORMAT_FILE} was committed unformatted")


def prove_commit(clone: pathlib.Path) -> list[str]:
    expect_pass("compile-context --verify", run([*ENGINE, "compile-context", "--verify"], clone))
    expect_pass("audit --offline", run([*ENGINE, "audit", "--offline"], clone))
    refused_commit(clone, "negative", CONTEXT_FILE, "\nPlanted hand edit.\n", CONTEXT_REASON)
    baseline = digest(clone / BASELINE)
    refused_commit(clone, "boundary", PLANT_FILE, PLANT, PLANT_REASON)
    if digest(clone / BASELINE) != baseline:
        raise ProofError(f"boundary: {BASELINE} changed")
    refused_commit(clone, "govet", VET_FILE, VET, VET_REASON)
    refused_commit(clone, "reuse-lint", LICENCE_FILE, LICENCE, LICENCE_REASON)
    prove_repair(clone)
    return [
        "positive: compile-context --verify and audit --offline exit 0",
        f"negative: hand edit to {CONTEXT_FILE} refused ({CONTEXT_REASON})",
        f"boundary: planted eval in {PLANT_FILE} refused ({PLANT_REASON}), {BASELINE} unchanged",
        f"pre-commit govet: {VET_FILE} refused ({VET_REASON})",
        f"pre-commit reuse-lint: {LICENCE_FILE} refused ({LICENCE_REASON})",
        f"pre-commit gofmt: {FORMAT_FILE} committed in gofmt form",
    ]


def refused_push(clone: pathlib.Path, job: str, reason: str, base: str) -> None:
    """Run one pre-push job on the planted clone, then restore the clone to base."""
    before = head(clone)
    status, output = run([*PUSH, job], clone)
    after = head(clone)
    restore(clone, base)
    expect_refusal(f"pre-push {job}", status, output, reason, (before, after))


def prove_gate(clone: pathlib.Path) -> None:
    status, output, heads = try_commit(clone, GATE_FILE, GATE, "test: planted failing test")
    if status != 0 or heads[0] == heads[1]:
        restore(clone, heads[0])
    expect_commit("gate", status, output, heads)
    refused_push(clone, "gate", GATE_REASON, heads[0])


def prove_push(clone: pathlib.Path, skip_gate: bool) -> list[str]:
    jobs = [job for job in PUSH_JOBS if not (skip_gate and job == "gate")]
    for job in jobs:
        expect_pass(f"pre-push {job}", run([*PUSH, job], clone))
    base = head(clone)
    (clone / FLAVOR_FILE).unlink()
    refused_push(clone, "flavor-audit", FLAVOR_REASON, base)
    plant(clone, PLANT_FILE, PLANT)
    refused_push(clone, "audit", PLANT_REASON, base)
    must(["env", "GOFLAGS=-mod=mod", "go", "get", VULN_MODULE], clone)
    plant(clone, VULN_FILE, VULN)
    refused_push(clone, "security", VULN_REASON, base)
    lines = [
        f"pre-push positive: {', '.join(jobs)} exit 0",
        f"pre-push flavor-audit: missing {FLAVOR_FILE} refused",
        f"pre-push audit: uncommitted eval in {PLANT_FILE} refused ({PLANT_REASON})",
        f"pre-push security: {VULN_MODULE} with a called Unmarshal refused ({VULN_REASON})",
    ]
    if skip_gate:
        return [*lines, "pre-push gate: skipped (--skip-gate), not proven"]
    prove_gate(clone)
    return [*lines, f"pre-push gate: committed failing test refused ({GATE_REASON})"]


def prove(clone: pathlib.Path, skip_gate: bool = False) -> list[str]:
    return [*prove_commit(clone), *prove_push(clone, skip_gate)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-gate", action="store_true", help="leave out both gate cases (needs the devcontainer)")
    options = parser.parse_args(argv)
    try:
        with tempfile.TemporaryDirectory(prefix="imago-hooks-") as scratch:
            clone = pathlib.Path(scratch) / "clone"
            make_clone(clone)
            print(f"clone of {head(clone)[:12]}")
            for line in prove(clone, options.skip_gate):
                print(line)
    except (ProofError, OSError, subprocess.TimeoutExpired) as error:
        print(f"::error::hook proof failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
