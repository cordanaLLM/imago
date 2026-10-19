# Copyright 2026 Lusoris
"""Verification of SLSA v1 Build L3 provenance and reusable release workflow wiring.

Ensures that the image build and signing identity live in a reusable workflow
(.github/workflows/release-build.yml), that artifact provenance is attested with
actions/attest inside the build job over each flavor's checksum file, that caller
and build-matrix grant attestations: write, that sign job has no attest step, and that
the HISS-11 exception for release-matrix.yml is removed from .standards.yaml.
Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked assertions.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.test_renovate_pr_metadata import reject_duplicate_keys

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
MATRIX_PATH = WORKFLOWS / "release-matrix.yml"
BUILD_PATH = WORKFLOWS / "release-build.yml"
STANDARDS_PATH = ROOT / ".standards.yaml"
FLAVOR_CHECKSUMS = "packer/output-images/${{ matrix.flavor }}/checksums-${{ matrix.flavor }}.sha256"


class UniqueKeyLoader(yaml.SafeLoader):
    """YAML loader rejecting duplicate keys in mappings."""

    pass


def _construct_mapping(loader: yaml.Loader, node: yaml.MappingNode, deep: bool = False) -> dict[str, Any]:
    loader.flatten_mapping(node)
    pairs = [(loader.construct_object(k, deep=deep), loader.construct_object(v, deep=deep)) for k, v in node.value]
    return reject_duplicate_keys(pairs)


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.load(handle, Loader=UniqueKeyLoader)


def _check_caller_workflow(matrix_doc: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    matrix_jobs = matrix_doc.get("jobs", {})
    if any("steps" in job for job in matrix_jobs.values()):
        findings.append("release-matrix.yml job must not define steps")

    release_job = matrix_jobs.get("release", {})
    if release_job.get("uses") != "./.github/workflows/release-build.yml":
        findings.append("caller job must use ./.github/workflows/release-build.yml")

    caller_perms = release_job.get("permissions", {})
    if caller_perms.get("attestations") != "write":
        findings.append("caller job lacks attestations: write")
    return findings


def _check_build_matrix_steps(steps: list[dict[str, Any]]) -> list[str]:
    findings: list[str] = []
    build_idx = next((i for i, s in enumerate(steps) if "make build" in s.get("run", "")), None)
    attest_idx = next(
        (i for i, s in enumerate(steps) if s.get("with", {}).get("subject-checksums") == FLAVOR_CHECKSUMS),
        None,
    )
    upload_idx = next((i for i, s in enumerate(steps) if "gh release upload" in s.get("run", "")), None)

    if attest_idx is None:
        findings.append(f"build-matrix job lacks attest step with subject-checksums {FLAVOR_CHECKSUMS}")
        return findings

    attest_step = steps[attest_idx]
    if attest_step.get("if") != "github.event_name == 'release'":
        findings.append("attest step in build-matrix lacks if: github.event_name == 'release'")

    if build_idx is not None and upload_idx is not None and not (build_idx < attest_idx < upload_idx):
        findings.append("attest step is not between build step and upload step")

    for i in range(attest_idx):
        step = steps[i]
        uses = step.get("uses", "")
        run_cmd = step.get("run", "")
        if "download-artifact" in uses or "gh run download" in run_cmd or "cache" in uses:
            findings.append("download-artifact or cache restore step precedes attest in build-matrix")
            break

    return findings


def _check_build_matrix_job(build_doc: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    build_jobs = build_doc.get("jobs", {})
    matrix_job = build_jobs.get("build-matrix", {})
    perms = matrix_job.get("permissions", {})
    if perms.get("id-token") != "write":
        findings.append("build-matrix job lacks id-token: write")
    if perms.get("attestations") != "write":
        findings.append("build-matrix job lacks attestations: write")
    findings.extend(_check_build_matrix_steps(matrix_job.get("steps", [])))
    return findings


def _check_sign_job(build_doc: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    build_jobs = build_doc.get("jobs", {})
    sign_job = build_jobs.get("sign", {})
    steps = sign_job.get("steps", [])

    if any(s.get("id") == "attest" or "actions/attest" in s.get("uses", "") for s in steps):
        findings.append("sign job must not contain attest step")

    verify_step = next((s for s in steps if "cosign verify-blob" in s.get("run", "")), None)
    if verify_step:
        run_cmd = verify_step.get("run", "")
        if "GITHUB_WORKFLOW_REF" in run_cmd:
            findings.append("cosign verify identity references GITHUB_WORKFLOW_REF")
        if ".github/workflows/release-build.yml" not in run_cmd:
            findings.append("cosign verify identity does not reference release-build.yml")
    return findings


def _check_standards(standards_doc: dict[str, Any] | None) -> list[str]:
    if standards_doc is None:
        return []
    return [
        "HISS-11 exception for release-matrix.yml found in .standards.yaml"
        for exc in standards_doc.get("exceptions", [])
        if exc.get("rule") == "HISS-11" and ".github/workflows/release-matrix.yml" in exc.get("path", "")
    ]


def check_release_provenance(
    matrix_doc: dict[str, Any],
    build_doc: dict[str, Any],
    standards_doc: dict[str, Any] | None = None,
) -> list[str]:
    """Audit release workflows and standards for SLSA L3 provenance requirements."""
    return (
        _check_caller_workflow(matrix_doc)
        + _check_build_matrix_job(build_doc)
        + _check_sign_job(build_doc)
        + _check_standards(standards_doc)
    )


def test_positive_provenance_wiring() -> None:
    matrix = load_yaml(MATRIX_PATH)
    build = load_yaml(BUILD_PATH)
    standards = load_yaml(STANDARDS_PATH)
    assert check_release_provenance(matrix, build, standards) == []


def test_build_matrix_attest_step_order_and_checksums() -> None:
    build = load_yaml(BUILD_PATH)
    steps = build["jobs"]["build-matrix"]["steps"]
    build_idx = next(i for i, s in enumerate(steps) if "make build" in s.get("run", ""))
    attest_idx = next(i for i, s in enumerate(steps) if s.get("with", {}).get("subject-checksums") == FLAVOR_CHECKSUMS)
    upload_idx = next(i for i, s in enumerate(steps) if "gh release upload" in s.get("run", ""))
    assert build_idx < attest_idx < upload_idx
    attest_step = steps[attest_idx]
    assert attest_step.get("id") == "attest"
    assert "actions/attest@" in attest_step.get("uses", "")
    assert attest_step.get("if") == "github.event_name == 'release'"


def test_no_download_or_cache_before_attest_in_build_matrix() -> None:
    build = load_yaml(BUILD_PATH)
    steps = build["jobs"]["build-matrix"]["steps"]
    attest_idx = next(i for i, s in enumerate(steps) if s.get("id") == "attest")
    for step in steps[:attest_idx]:
        assert "download-artifact" not in step.get("uses", "")
        assert "gh run download" not in step.get("run", "")
        assert "cache" not in step.get("uses", "")


def test_attestations_permission_granted_on_caller_and_build_matrix() -> None:
    matrix = load_yaml(MATRIX_PATH)
    build = load_yaml(BUILD_PATH)
    assert matrix["jobs"]["release"]["permissions"]["attestations"] == "write"
    assert build["jobs"]["build-matrix"]["permissions"]["id-token"] == "write"
    assert build["jobs"]["build-matrix"]["permissions"]["attestations"] == "write"


def test_sign_job_has_no_attest_step() -> None:
    build = load_yaml(BUILD_PATH)
    sign_steps = build["jobs"]["sign"]["steps"]
    assert not any(s.get("id") == "attest" or "actions/attest" in s.get("uses", "") for s in sign_steps)


def test_caller_uses_reusable_workflow() -> None:
    matrix = load_yaml(MATRIX_PATH)
    assert matrix["jobs"]["release"]["uses"] == "./.github/workflows/release-build.yml"


def test_release_matrix_has_no_steps() -> None:
    matrix = load_yaml(MATRIX_PATH)
    assert "steps" not in matrix
    assert all("steps" not in job for job in matrix.get("jobs", {}).values())


def test_standards_holds_no_hiss11_exception() -> None:
    standards = load_yaml(STANDARDS_PATH)
    hiss11 = [
        exc
        for exc in standards.get("exceptions", [])
        if exc.get("rule") == "HISS-11" and ".github/workflows/release-matrix.yml" in exc.get("path", "")
    ]
    assert hiss11 == []


def test_loader_rejects_duplicate_keys() -> None:
    duplicate_yaml = "key: first\nkey: second\n"
    with pytest.raises(ValueError, match="duplicate key in JSON: 'key'"):
        yaml.load(duplicate_yaml, Loader=UniqueKeyLoader)


def _mutate_move_attest_into_sign(matrix: dict, build: dict) -> None:
    b_steps = build["jobs"]["build-matrix"]["steps"]
    attest_step = next(s for s in b_steps if s.get("id") == "attest")
    build["jobs"]["build-matrix"]["steps"] = [s for s in b_steps if s.get("id") != "attest"]
    build["jobs"]["sign"]["steps"].append(attest_step)


def _mutate_insert_download_before_attest(matrix: dict, build: dict) -> None:
    b_steps = build["jobs"]["build-matrix"]["steps"]
    attest_idx = next(i for i, s in enumerate(b_steps) if s.get("id") == "attest")
    b_steps.insert(attest_idx, {"uses": "actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333"})


def _mutate_move_attest_before_build(matrix: dict, build: dict) -> None:
    b_steps = build["jobs"]["build-matrix"]["steps"]
    attest_step = next(s for s in b_steps if s.get("id") == "attest")
    filtered = [s for s in b_steps if s.get("id") != "attest"]
    filtered.insert(0, attest_step)
    build["jobs"]["build-matrix"]["steps"] = filtered


def _mutate_drop_caller_attestations(matrix: dict, build: dict) -> None:
    matrix["jobs"]["release"]["permissions"].pop("attestations", None)


def _mutate_cosign_identity_workflow_ref(matrix: dict, build: dict) -> None:
    for step in build["jobs"]["sign"]["steps"]:
        if "cosign verify-blob" in step.get("run", ""):
            step["run"] = step["run"].replace(
                "https://github.com/${GITHUB_REPOSITORY}/.github/workflows/release-build.yml@${GITHUB_REF}",
                "https://github.com/${GITHUB_WORKFLOW_REF}",
            )


@pytest.mark.parametrize(
    ("mutator", "expected_fragment"),
    [
        (_mutate_move_attest_into_sign, "sign job must not contain attest step"),
        (_mutate_insert_download_before_attest, "download-artifact or cache restore step precedes attest"),
        (_mutate_move_attest_before_build, "attest step is not between build step and upload step"),
        (_mutate_drop_caller_attestations, "caller job lacks attestations: write"),
        (_mutate_cosign_identity_workflow_ref, "cosign verify identity references GITHUB_WORKFLOW_REF"),
    ],
)
def test_mutants_report_findings(mutator: Any, expected_fragment: str) -> None:
    matrix = copy.deepcopy(load_yaml(MATRIX_PATH))
    build = copy.deepcopy(load_yaml(BUILD_PATH))
    mutator(matrix, build)
    findings = check_release_provenance(matrix, build)
    assert any(expected_fragment in f for f in findings), f"Expected {expected_fragment!r} in {findings}"
