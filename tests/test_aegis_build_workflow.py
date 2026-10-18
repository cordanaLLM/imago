# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Tests for the Aegis build workflow, request verification, and boot-once tooling."""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
from unittest import mock

import pytest
import yaml

from tools.aegis import boot_once, check_request

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "aegis-build.yml"


def load_workflow() -> dict:
    """Load and parse the aegis-build workflow YAML."""
    with WORKFLOW_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


# -----------------------------------------------------------------------------
# Workflow Structure and Policy Tests
# -----------------------------------------------------------------------------


def test_workflow_trigger_is_dispatch_only() -> None:
    """Ensure workflow triggers only on workflow_dispatch."""
    data = load_workflow()
    # PyYAML may parse the key `on` as boolean True if unquoted, or as string 'on'
    triggers = data[True] if True in data else data["on"]
    assert set(triggers.keys()) == {"workflow_dispatch"}
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert "aegis-revision" in inputs
    assert "request-sha256" in inputs
    assert inputs["aegis-revision"]["required"] is True
    assert inputs["request-sha256"]["required"] is True


def test_workflow_permissions_exact() -> None:
    """Verify top-level permissions: {} and job permissions are exact."""
    data = load_workflow()
    assert data["permissions"] == {}
    job = data["jobs"]["build"]
    assert job["permissions"] == {"contents": "write", "id-token": "write"}


def test_no_inputs_inside_run_blocks() -> None:
    """Ensure ${{ inputs.* }} is never expanded directly inside run: blocks."""
    data = load_workflow()
    job = data["jobs"]["build"]
    for step in job["steps"]:
        run_text = step.get("run", "")
        assert "${{ inputs." not in run_text, f"Step '{step.get('name')}' expands inputs in run block"


def test_prerelease_and_no_clobber() -> None:
    """Verify pre-release flag, latest=false, and strict prohibition of clobber."""
    data = load_workflow()
    job = data["jobs"]["build"]
    publish_step = next(step for step in job["steps"] if step.get("name") == "Publish Pre-Release")
    run_text = publish_step["run"]
    assert "--prerelease" in run_text
    assert "--latest=false" in run_text
    assert "--clobber" not in run_text
    assert 'tag="aegis-${cid}"' in run_text or 'tag="aegis-${cid}"' in run_text
    assert '[[ "${tag}" != aegis-* ]]' in run_text


def test_kvm_step_fails_closed() -> None:
    """Verify KVM access check fails with exit 1 and never skips or continues on error."""
    data = load_workflow()
    job = data["jobs"]["build"]
    kvm_step = next(step for step in job["steps"] if step.get("name") == "Verify KVM Read-Write Access")
    assert "continue-on-error" not in kvm_step
    assert "continue-on-error" not in job
    run_text = kvm_step["run"]
    assert "exit 1" in run_text
    assert "set -euo pipefail" in run_text
    assert "/dev/kvm" in run_text


def test_dispatch_refused_outside_main() -> None:
    """The first step refuses any ref other than refs/heads/main."""
    steps = load_workflow()["jobs"]["build"]["steps"]
    guard = steps[0]
    assert guard.get("name") == "Refuse Dispatch Outside main"
    assert '[[ "${GITHUB_REF}" != "refs/heads/main" ]]' in guard["run"]
    assert "exit 1" in guard["run"]
    assert "continue-on-error" not in guard


def test_no_silent_mkosi_fallback() -> None:
    """mkosi comes from the pinned action only; a missing mkosi or pacman fails the job."""
    steps = load_workflow()["jobs"]["build"]["steps"]
    run_texts = [step.get("run", "") for step in steps]
    assert not any("pipx" in text or "pip install" in text for text in run_texts)
    check = next(step for step in steps if step.get("name") == "Verify mkosi and pacman")
    assert "command -v mkosi >/dev/null" in check["run"]
    assert "command -v pacman >/dev/null" in check["run"]
    assert check["run"].count("exit 1") == 2


def test_mkosi_builds_with_pinned_arch_tools_tree() -> None:
    """mkosi takes repart, ukify and mkfs tools from an Arch tools tree, never from the runner host."""
    steps = load_workflow()["jobs"]["build"]["steps"]
    build = next(step for step in steps if step.get("name") == "Build Aegis Image with mkosi")
    command = next(line for line in build["run"].splitlines() if line.strip().startswith("mkosi "))
    assert "--tools-tree=yes" in command.split()
    assert "--tools-tree-distribution=arch" in command.split()
    assert "--tools-tree-snapshot" not in command


def test_release_targets_built_commit() -> None:
    """The pre-release tag points at the imago commit the workflow ran from."""
    steps = load_workflow()["jobs"]["build"]["steps"]
    publish = next(step for step in steps if step.get("name") == "Publish Pre-Release")
    assert '--target "${GITHUB_SHA}"' in publish["run"]


# -----------------------------------------------------------------------------
# Unit Tests: tools/aegis/check_request.py
# -----------------------------------------------------------------------------


def test_validate_hex_positive() -> None:
    """Valid lowercase hex strings pass validation."""
    check_request.validate_hex("0123456789abcdef", 16, "test_field")
    check_request.validate_hex("a" * 40, 40, "sha1")
    check_request.validate_hex("f" * 64, 64, "sha256")


@pytest.mark.parametrize(
    "invalid",
    ["0123456789ABCDEF", "0123456789abcdefg", "0123-4567", "   ", ""],
)
def test_validate_hex_negative_chars(invalid: str) -> None:
    """Non-lowercase or non-hex characters raise RequestCheckError."""
    with pytest.raises(check_request.RequestCheckError, match="lowercase hex"):
        check_request.validate_hex(invalid, len(invalid), "field")


@pytest.mark.parametrize(
    ("val", "expected_len"),
    [("a" * 39, 40), ("a" * 41, 40), ("b" * 63, 64), ("b" * 65, 64)],
)
def test_validate_hex_boundary_length(val: str, expected_len: int) -> None:
    """Lengths off by one on either boundary raise RequestCheckError."""
    with pytest.raises(check_request.RequestCheckError, match="must be"):
        check_request.validate_hex(val, expected_len, "boundary_field")


def test_compute_sha256_positive_and_boundary(tmp_path: pathlib.Path) -> None:
    """Verify SHA-256 calculation for empty and non-empty files."""
    empty_file = tmp_path / "empty.txt"
    empty_file.write_bytes(b"")
    empty_sha = hashlib.sha256(b"").hexdigest()
    assert check_request.compute_sha256(empty_file) == empty_sha

    data_file = tmp_path / "data.bin"
    payload = b"Aegis kernel and initrd definition test bytes"
    data_file.write_bytes(payload)
    assert check_request.compute_sha256(data_file) == hashlib.sha256(payload).hexdigest()


def test_verify_request_sha_mismatch(tmp_path: pathlib.Path) -> None:
    """SHA mismatch between actual and expected raises RequestCheckError."""
    test_file = tmp_path / "request.json"
    test_file.write_text("{}", encoding="utf-8")
    with pytest.raises(check_request.RequestCheckError, match="SHA-256 mismatch"):
        check_request.verify_request_sha(test_file, "0" * 64)


def test_read_request_revision_positive(tmp_path: pathlib.Path) -> None:
    """Read valid 40-hex revision from JSON request."""
    req_file = tmp_path / "product-input.json"
    rev = "61f2fe16bab7889e007b2fd1474b025023906e91"
    req_file.write_text(json.dumps({"revision": rev}), encoding="utf-8")
    assert check_request.read_request_revision(req_file) == rev


@pytest.mark.parametrize(
    "doc",
    [
        {},
        {"revision": 12345},
        {"revision": "not-a-valid-40-hex-revision"},
        {"revision": "61f2fe1"},
    ],
)
def test_read_request_revision_negative(tmp_path: pathlib.Path, doc: dict) -> None:
    """Invalid or missing revision field raises RequestCheckError."""
    req_file = tmp_path / "bad-req.json"
    req_file.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(check_request.RequestCheckError):
        check_request.read_request_revision(req_file)


def test_verify_imago_validate_positive(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful imago aegis validate passes."""
    req_file = tmp_path / "req.json"
    req_file.write_text("{}", encoding="utf-8")

    def mock_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="accepted", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)
    check_request.verify_imago_validate("./imago", req_file)


def test_verify_imago_validate_negative(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Rejection by imago aegis validate raises RequestCheckError."""
    req_file = tmp_path / "req.json"
    req_file.write_text("{}", encoding="utf-8")

    def mock_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="schema invalid")

    monkeypatch.setattr(subprocess, "run", mock_run)
    with pytest.raises(check_request.RequestCheckError, match="imago aegis validate rejected"):
        check_request.verify_imago_validate("./imago", req_file)


def test_verify_git_ancestor_positive_and_negative(tmp_path: pathlib.Path) -> None:
    """Verify git merge-base --is-ancestor with a real local git repository."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo, check=True)

    (repo / "f1.txt").write_text("commit 1", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "commit 1"], cwd=repo, check=True)
    c1 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    (repo / "f2.txt").write_text("commit 2", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "commit 2"], cwd=repo, check=True)
    c2 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    # c1 is ancestor of c2 -> positive
    check_request.verify_git_ancestor(repo, c1, c2)

    # c2 is not an ancestor of c1 -> negative
    with pytest.raises(check_request.RequestCheckError, match="Lineage refusal"):
        check_request.verify_git_ancestor(repo, c2, c1)


# -----------------------------------------------------------------------------
# Unit Tests: tools/aegis/boot_once.py
# -----------------------------------------------------------------------------


def test_clean_ansi() -> None:
    """Strip escape sequences from serial text."""
    raw = "\x1b[0;32m[  OK  ]\x1b[0m Reached target \x1b[1mmulti-user.target\x1b[0m."
    assert boot_once.clean_ansi(raw) == "[  OK  ] Reached target multi-user.target."


@pytest.mark.parametrize(
    "line",
    [
        "[  OK  ] Reached target multi-user.target.",
        "[  OK  ] Reached target Multi-User System.",
        "Startup finished in 1.2s (kernel) + 2.3s (userspace) = 3.5s.",
    ],
)
def test_find_marker_line_positive(tmp_path: pathlib.Path, line: str) -> None:
    """Find target marker line in log file."""
    log = tmp_path / "serial.log"
    log.write_text(f"Booting system...\n{line}\nContinuing...\n", encoding="utf-8")
    pattern = re.compile(boot_once.DEFAULT_MARKER_REGEX)
    assert boot_once.find_marker_line(log, pattern) == line


def test_find_marker_line_negative(tmp_path: pathlib.Path) -> None:
    """Return None when marker is absent or file missing."""
    log = tmp_path / "serial.log"
    log.write_text("Booting system...\nKernel panic\n", encoding="utf-8")
    pattern = re.compile(boot_once.DEFAULT_MARKER_REGEX)
    assert boot_once.find_marker_line(log, pattern) is None
    assert boot_once.find_marker_line(tmp_path / "missing.log", pattern) is None


def test_find_marker_line_boundary_first_line(tmp_path: pathlib.Path) -> None:
    """Marker on the exact first line of the file matches."""
    log = tmp_path / "serial.log"
    first = "[  OK  ] Reached target multi-user.target."
    log.write_text(first + "\n", encoding="utf-8")
    pattern = re.compile(boot_once.DEFAULT_MARKER_REGEX)
    assert boot_once.find_marker_line(log, pattern) == first


def test_poll_boot_success(tmp_path: pathlib.Path) -> None:
    """poll_boot returns matched line when marker appears."""
    log = tmp_path / "serial.log"
    marker = "Reached target multi-user.target"
    log.write_text(f"{marker}\n", encoding="utf-8")
    pattern = re.compile(boot_once.DEFAULT_MARKER_REGEX)
    proc = mock.MagicMock(spec=subprocess.Popen)
    proc.poll.return_value = None
    matched = boot_once.poll_boot(proc, log, pattern, deadline_s=5.0, poll_s=0.1)
    assert matched == marker


def test_poll_boot_premature_exit(tmp_path: pathlib.Path) -> None:
    """QEMU exiting without marker raises BootError."""
    log = tmp_path / "serial.log"
    log.write_text("Kernel crashed\n", encoding="utf-8")
    pattern = re.compile(boot_once.DEFAULT_MARKER_REGEX)
    proc = mock.MagicMock(spec=subprocess.Popen)
    proc.poll.return_value = 1
    proc.returncode = 1
    with pytest.raises(boot_once.BootError, match="exited prematurely"):
        boot_once.poll_boot(proc, log, pattern, deadline_s=5.0, poll_s=0.1)


def test_poll_boot_deadline_timeout(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Loop exhaustion without marker raises BootError."""
    log = tmp_path / "serial.log"
    log.write_text("Still booting...\n", encoding="utf-8")
    pattern = re.compile(boot_once.DEFAULT_MARKER_REGEX)
    proc = mock.MagicMock(spec=subprocess.Popen)
    proc.poll.return_value = None
    monkeypatch.setattr(boot_once.time, "sleep", lambda _s: None)
    with pytest.raises(boot_once.BootError, match="timed out"):
        boot_once.poll_boot(proc, log, pattern, deadline_s=0.2, poll_s=0.1)


def test_assemble_evidence_schema_and_fields(tmp_path: pathlib.Path) -> None:
    """Validate structure and fields of boot evidence payload."""
    log = tmp_path / "serial.log"
    log.write_text("marker log", encoding="utf-8")
    evidence = boot_once.assemble_evidence(
        "cid-001",
        "a" * 64,
        qemu_ver="QEMU emulator version 9.2.0",
        ovmf_ver="/usr/share/OVMF/OVMF_CODE_4M.fd",
        swtpm_ver="TPM emulator version 0.10.0",
        marker_line="Reached target multi-user.target",
        serial_log=log,
        serial_sha="b" * 64,
        elapsed=4.512,
    )
    assert evidence["schema"] == "imago.aegis.boot-evidence.v1"
    assert evidence["correlation-id"] == "cid-001"
    assert evidence["image-sha256"] == "a" * 64
    assert evidence["kernel-cmdline-extra"] == "console=ttyS0"
    assert evidence["marker-line"] == "Reached target multi-user.target"
    assert evidence["serial-log"] == {"name": "serial.log", "sha256": "b" * 64}
    assert evidence["wall-seconds"] == 4.512
    assert "runner-image" in evidence


def test_resolve_ovmf_explicit_and_missing(tmp_path: pathlib.Path) -> None:
    """Explicit paths succeed if files exist and fail if missing."""
    code = tmp_path / "code.fd"
    vars_file = tmp_path / "vars.fd"
    code.write_bytes(b"code")
    vars_file.write_bytes(b"vars")

    r_code, r_vars = boot_once.resolve_ovmf(code, vars_file)
    assert r_code == code and r_vars == vars_file

    with pytest.raises(boot_once.BootError, match="OVMF code file not found"):
        boot_once.resolve_ovmf(tmp_path / "nonexistent.fd", vars_file)


# -----------------------------------------------------------------------------
# Failure Evidence Tests
# -----------------------------------------------------------------------------


def boot_args(tmp_path: pathlib.Path) -> list[str]:
    """Command line for boot_once.main with every output under tmp_path."""
    return [
        "--image",
        str(tmp_path / "aegis-os.raw"),
        "--correlation-id",
        "cid-001",
        "--serial-log",
        str(tmp_path / "serial.log"),
        "--evidence",
        str(tmp_path / "boot-evidence.json"),
        "--failure-evidence",
        str(tmp_path / "boot-failure.json"),
        "--deadline",
        "600",
    ]


def test_failed_boot_writes_failure_record(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A planted boot timeout leaves a failure record bound to the serial log, and no boot evidence."""
    (tmp_path / "serial.log").write_text("Still booting...\n", encoding="utf-8")

    def timed_out(*_args: object, **_kwargs: object) -> None:
        raise boot_once.BootError("Boot timed out after 600.0 seconds without reaching marker")

    monkeypatch.setattr(boot_once, "execute_boot", timed_out)
    assert boot_once.main(boot_args(tmp_path)) == 1
    record = json.loads((tmp_path / "boot-failure.json").read_text(encoding="utf-8"))
    assert record["schema"] == "imago.aegis.boot-failure.v1"
    assert record["correlation-id"] == "cid-001"
    assert "timed out" in record["reason"]
    assert record["deadline-seconds"] == 600.0
    serial_sha = hashlib.sha256(b"Still booting...\n").hexdigest()
    assert record["serial-log"] == {"name": "serial.log", "sha256": serial_sha}
    assert not (tmp_path / "boot-evidence.json").exists()


def test_failed_boot_without_serial_log_records_null_digest(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure before QEMU wrote any output still leaves a record, with no serial digest."""

    def missing_firmware(*_args: object, **_kwargs: object) -> None:
        raise boot_once.BootError("OVMF code file not found")

    monkeypatch.setattr(boot_once, "execute_boot", missing_firmware)
    assert boot_once.main(boot_args(tmp_path)) == 1
    record = json.loads((tmp_path / "boot-failure.json").read_text(encoding="utf-8"))
    assert record["serial-log"] == {"name": "serial.log", "sha256": None}


def test_successful_boot_writes_no_failure_record(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A boot that reaches the marker leaves no failure record next to its evidence."""
    monkeypatch.setattr(boot_once, "execute_boot", lambda *_args, **_kwargs: {})
    assert boot_once.main(boot_args(tmp_path)) == 0
    assert not (tmp_path / "boot-failure.json").exists()


def test_failed_run_keeps_boot_evidence() -> None:
    """The serial log and the failure record leave the runner only when a step failed."""
    steps = load_workflow()["jobs"]["build"]["steps"]
    names = [step.get("name") for step in steps]
    keep = steps[names.index("Keep the Boot Evidence of a Failed Run")]
    assert names.index("Boot the Image Once") < names.index(keep["name"]) < names.index("Generate Checksums")
    assert keep["if"] == "failure()"
    assert "continue-on-error" not in keep
    assert re.fullmatch(r"actions/upload-artifact@[0-9a-f]{40}", keep["uses"])
    paths = keep["with"]["path"].split()
    assert paths == ["aegis-output/serial.log", "aegis-output/boot-failure.json", "aegis-output/boot-evidence.json"]
    assert 1 <= keep["with"]["retention-days"] <= 7
    boot_run = steps[names.index("Boot the Image Once")]["run"]
    assert '--failure-evidence "${out_dir}/boot-failure.json"' in boot_run
    assert '--serial-log "${out_dir}/serial.log"' in boot_run


# -----------------------------------------------------------------------------
# Consumer Contract Tests (Aegis-OS verification guarantees)
# -----------------------------------------------------------------------------


def check_boot_evidence_contract(evidence: dict[str, object], expected_id: str | None = None) -> None:
    """Verify that boot evidence carries the exact correlation-id contract."""
    assert "correlation-id" in evidence, "Evidence missing exact contract key 'correlation-id'"
    val = evidence["correlation-id"]
    assert isinstance(val, str), f"'correlation-id' must be a string, got {type(val).__name__}"
    assert len(val) > 0, "'correlation-id' must be a non-empty string"
    if expected_id is not None:
        assert val == expected_id, f"'correlation-id' mismatch: expected {expected_id!r}, got {val!r}"


def check_workflow_sha256sums_contract(workflow_data: dict) -> None:
    """Verify that the workflow sums boot-evidence.json into SHA256SUMS before cosign signs it."""
    steps = workflow_data["jobs"]["build"]["steps"]
    boot_run = next(s["run"] for s in steps if s.get("name") == "Boot the Image Once")
    assert """cid=$(jq -r '."correlation-id"' aegis/build/product-input.json)""" in boot_run
    assert '--correlation-id "${cid}"' in boot_run, "boot step must pass the request correlation-id"
    assert '--evidence "${out_dir}/boot-evidence.json"' in boot_run
    checksum_idx = next(
        idx for idx, s in enumerate(steps) if "sha256sum" in s.get("run", "") and "> SHA256SUMS" in s.get("run", "")
    )
    checksum_step = steps[checksum_idx]
    checksum_run = checksum_step.get("run", "")

    sha_match = re.search(r"sha256sum\s+(.*?)\s*>\s*SHA256SUMS", checksum_run, re.DOTALL)
    assert sha_match is not None, "Workflow missing sha256sum command redirecting to SHA256SUMS"
    summed_files = sha_match.group(1).replace("\\", "").split()
    assert "boot-evidence.json" in summed_files, "boot-evidence.json must be listed among files summed into SHA256SUMS"

    sign_idx = next(
        idx
        for idx, s in enumerate(steps)
        if "cosign sign-blob" in s.get("run", "") and "SHA256SUMS" in s.get("run", "")
    )
    assert sign_idx > checksum_idx, (
        f"cosign sign-blob step (index {sign_idx}) must execute after sha256sum step (index {checksum_idx})"
    )
    sign_run = steps[sign_idx].get("run", "")
    assert "SHA256SUMS" in sign_run, "cosign sign-blob must sign the SHA256SUMS file"


@pytest.mark.parametrize(
    "cid",
    [
        "aegis-m18-product-input-0001",  # standard positive
        "x",  # shortest non-empty id
        "k" * 64,  # long id
    ],
)
def test_assemble_evidence_correlation_id_contract(tmp_path: pathlib.Path, cid: str) -> None:
    """assemble_evidence writes the request id under the exact key correlation-id."""
    log = tmp_path / "serial.log"
    log.write_text("marker log", encoding="utf-8")
    evidence = boot_once.assemble_evidence(
        cid,
        "a" * 64,
        qemu_ver="QEMU emulator version 9.2.0",
        ovmf_ver="/usr/share/OVMF/OVMF_CODE_4M.fd",
        swtpm_ver="TPM emulator version 0.10.0",
        marker_line="Reached target multi-user.target",
        serial_log=log,
        serial_sha="b" * 64,
        elapsed=3.14,
    )
    check_boot_evidence_contract(evidence, expected_id=cid)


def test_workflow_sha256sums_and_signing_contract() -> None:
    """Workflow step writing SHA256SUMS includes boot-evidence.json and cosign signs it after."""
    workflow_data = load_workflow()
    check_workflow_sha256sums_contract(workflow_data)


def test_negative_planted_workflow_text_fails_contract() -> None:
    """A planted workflow text with boot-evidence.json removed from sha256sum fails the check."""
    raw_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "boot-evidence.json" in raw_text
    planted_text = raw_text.replace("boot-evidence.json \\\n", "")
    planted_data = yaml.safe_load(planted_text)
    with pytest.raises(AssertionError, match="boot-evidence.json"):
        check_workflow_sha256sums_contract(planted_data)


def test_negative_planted_evidence_renamed_key_fails_contract(tmp_path: pathlib.Path) -> None:
    """A planted evidence dict with correlation-id renamed to correlation_id fails the check."""
    log = tmp_path / "serial.log"
    log.write_text("marker log", encoding="utf-8")
    evidence = boot_once.assemble_evidence(
        "cid-001",
        "a" * 64,
        qemu_ver="QEMU emulator version 9.2.0",
        ovmf_ver="/usr/share/OVMF/OVMF_CODE_4M.fd",
        swtpm_ver="TPM emulator version 0.10.0",
        marker_line="Reached target multi-user.target",
        serial_log=log,
        serial_sha="b" * 64,
        elapsed=3.14,
    )
    assert "correlation-id" in evidence
    evidence["correlation_id"] = evidence.pop("correlation-id")
    with pytest.raises(AssertionError, match="correlation-id"):
        check_boot_evidence_contract(evidence)
