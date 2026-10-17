# Copyright 2026 Lusoris
"""Automated verification suite for Packer and plugin toolchain pins.

Validates that Packer core and plugin versions in packer/versions.pkr.hcl strictly
match the single source of truth in versions.json under .build, ensures workflow
files use dynamic step outputs rather than hardcoded literals in setup-packer, and
confirms every SHA digest is a 64-character lowercase hex string. Each invariant
ships positive and negative drift test cases.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "versions.json"
VERSIONS_HCL_PATH = REPO_ROOT / "packer" / "versions.pkr.hcl"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
HEX_64_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a dictionary from key-value pairs, refusing duplicate keys."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key in JSON: {key!r}")
        result[key] = value
    return result


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    """Load JSON manifest with strict duplicate key rejection."""
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)


def extract_hcl_pins(hcl_content: str) -> dict[str, str]:
    """Extract required_version, qemu version, and proxmox version from HCL."""
    pins: dict[str, str] = {}
    req = re.search(r'required_version\s*=\s*"([^"]+)"', hcl_content)
    if req:
        pins["required_version"] = req.group(1)

    qemu = re.search(r'qemu\s*=\s*\{[^}]*version\s*=\s*"([^"]+)"', hcl_content, re.DOTALL)
    if qemu:
        pins["qemu_version"] = qemu.group(1)

    proxmox = re.search(r'proxmox\s*=\s*\{[^}]*version\s*=\s*"([^"]+)"', hcl_content, re.DOTALL)
    if proxmox:
        pins["proxmox_version"] = proxmox.group(1)

    return pins


def check_packer_hcl_pins(hcl_content: str, manifest: dict[str, Any]) -> list[str]:
    """Verify HCL pins match versions.json build.* exactly. Return drift errors."""
    errors: list[str] = []
    pins = extract_hcl_pins(hcl_content)

    expected_packer = f"= {manifest['build']['packer']['version']}"
    if pins.get("required_version") != expected_packer:
        errors.append(f"required_version drift: expected {expected_packer!r}, found {pins.get('required_version')!r}")

    expected_qemu = f"= {manifest['build']['packer_plugins']['qemu']['version']}"
    if pins.get("qemu_version") != expected_qemu:
        errors.append(f"qemu version drift: expected {expected_qemu!r}, found {pins.get('qemu_version')!r}")

    expected_proxmox = f"= {manifest['build']['packer_plugins']['proxmox']['version']}"
    if pins.get("proxmox_version") != expected_proxmox:
        errors.append(f"proxmox version drift: expected {expected_proxmox!r}, found {pins.get('proxmox_version')!r}")

    return errors


def find_setup_packer_literal_versions(workflow_path: Path, content: str) -> list[str]:
    """Find setup-packer steps with literal versions rather than dynamic expressions."""
    errors: list[str] = []
    try:
        data = yaml.safe_load(content)
    except Exception as exc:
        return [f"{workflow_path}: failed to parse YAML: {exc}"]

    if not isinstance(data, dict):
        return []

    jobs = data.get("jobs", {})
    if not isinstance(jobs, dict):
        return []

    for job_name, job_data in jobs.items():
        if not isinstance(job_data, dict):
            continue
        for idx, step in enumerate(job_data.get("steps", [])):
            if not isinstance(step, dict):
                continue
            if "setup-packer" in str(step.get("uses", "")):
                version = str(step.get("with", {}).get("version", ""))
                is_expr = version.startswith("${{") and version.endswith("}}")
                if not is_expr or re.match(r"^\d+\.\d+", version):
                    errors.append(
                        f"{workflow_path.name}:{job_name}:step[{idx}] setup-packer literal version: {version!r}"
                    )
    return errors


def collect_build_sha_fields(build_data: dict[str, Any]) -> dict[str, str]:
    """Collect all fields containing 'sha' from the build manifest section."""
    shas: dict[str, str] = {}
    for k, v in build_data.get("packer", {}).items():
        if "sha" in k:
            shas[f"build.packer.{k}"] = str(v)
    for plugin_name, plugin_data in build_data.get("packer_plugins", {}).items():
        if isinstance(plugin_data, dict):
            for k, v in plugin_data.items():
                if "sha" in k:
                    shas[f"build.packer_plugins.{plugin_name}.{k}"] = str(v)
    return shas


def check_sha_fields_valid_hex(shas: dict[str, str]) -> list[str]:
    """Verify that every collected SHA is a 64-character lowercase hex string."""
    errors: list[str] = []
    for key, val in shas.items():
        if not HEX_64_PATTERN.fullmatch(val):
            errors.append(f"{key} is not 64 lowercase hex characters: {val!r}")
    return errors


# --- Tests ----------------------------------------------------------------------------


def test_manifest_rejects_duplicate_keys() -> None:
    """Verify that the JSON loader strictly refuses duplicate keys."""
    duplicate_json = '{"key": "first", "key": "second"}'
    with pytest.raises(ValueError, match="duplicate key in JSON: 'key'"):
        json.loads(duplicate_json, object_pairs_hook=reject_duplicate_keys)


def test_packer_hcl_pins_match_manifest() -> None:
    """Verify versions.pkr.hcl required_version and plugins match versions.json build.*."""
    manifest = load_manifest()
    content = VERSIONS_HCL_PATH.read_text(encoding="utf-8")
    errors = check_packer_hcl_pins(content, manifest)
    assert errors == [], f"Packer HCL pins drift detected: {errors}"


@pytest.mark.parametrize("pin", ["packer", "qemu", "proxmox"])
def test_packer_hcl_pins_detects_drift(pin: str) -> None:
    """Verify check_packer_hcl_pins reports drift when one versions.json pin moves."""
    manifest = load_manifest()
    content = VERSIONS_HCL_PATH.read_text(encoding="utf-8")
    entry = manifest["build"]["packer"] if pin == "packer" else manifest["build"]["packer_plugins"][pin]
    entry["version"] = "0.0.0"
    errors = check_packer_hcl_pins(content, manifest)
    assert len(errors) == 1, f"Expected one drift error for {pin}, found {errors}"


def test_no_workflow_has_literal_packer_version() -> None:
    """Verify all workflow setup-packer steps use dynamic outputs, not literals."""
    workflow_files = sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml"))
    assert len(workflow_files) > 0, "No workflow files discovered"
    all_errors: list[str] = []
    for wf in workflow_files:
        errors = find_setup_packer_literal_versions(wf, wf.read_text(encoding="utf-8"))
        all_errors.extend(errors)
    assert all_errors == [], f"Literal setup-packer version found in workflows: {all_errors}"


def test_workflows_reject_literal_packer_version() -> None:
    """Verify find_setup_packer_literal_versions catches literal versions."""
    ci_workflow = WORKFLOWS_DIR / "ci.yml"
    content = ci_workflow.read_text(encoding="utf-8")
    mutated = content.replace("${{ steps.packer-pin.outputs.version }}", '"1.16.1"', 1)
    errors = find_setup_packer_literal_versions(ci_workflow, mutated)
    assert len(errors) > 0, "Expected detection of literal setup-packer version"


def test_every_build_sha_is_64_hex() -> None:
    """Verify all SHA fields in versions.json build section are 64 hex characters."""
    manifest = load_manifest()
    assert "build" in manifest, "Manifest missing 'build' section"
    shas = collect_build_sha_fields(manifest["build"])
    assert len(shas) >= 4, f"Expected >= 4 SHA fields in build section, found {len(shas)}"
    errors = check_sha_fields_valid_hex(shas)
    assert errors == [], f"Invalid SHA fields: {errors}"


@pytest.mark.parametrize(
    "invalid_sha",
    [
        "not_a_sha",
        "1ee97a23df2180919352029030e20b45c176861125421fd3a06c1d78a0565a4",  # 63 chars
        "1EE97A23DF2180919352029030E20B45C176861125421FD3A06C1D78A0565A47",  # uppercase
        "1ee97a23df2180919352029030e20b45c176861125421fd3a06c1d78a0565a47g",  # non-hex
        "",
    ],
)
def test_sha_validator_rejects_invalid_hex(invalid_sha: str) -> None:
    """Verify check_sha_fields_valid_hex rejects non-64 hex strings."""
    test_shas = {"test.sha": invalid_sha}
    errors = check_sha_fields_valid_hex(test_shas)
    assert len(errors) == 1, f"Expected 1 error for {invalid_sha!r}, got {len(errors)}"
    assert "is not 64 lowercase hex characters" in errors[0]
