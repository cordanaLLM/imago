# Copyright 2026 Lusoris
"""Tests for the upstream package source pre-flight (tools/ci/upstream_sources.py).

The ROCm provisioner fetched a key name, release and apt suite that repo.radeon.com does not
publish, and the build failed with a 404 about 20 minutes in. These tests keep the pre-flight
and the provisioner on the same URLs and require the check to run before the Packer build.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "ci" / "upstream_sources.py"
ROCM_SCRIPT = REPO_ROOT / "packer" / "provisioners" / "32-gpu-amd-rocm.sh"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release-matrix.yml"
MANIFEST = json.loads((REPO_ROOT / "versions.json").read_text(encoding="utf-8"))

_SPEC = importlib.util.spec_from_file_location("upstream_sources", TOOL)
assert _SPEC is not None and _SPEC.loader is not None
upstream_sources = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(upstream_sources)


def answering(published: set[str]):
    return lambda url: 200 if url in published else 404


def test_rocm_urls_follow_versions_json() -> None:
    amd = MANIFEST["drivers"]["amd"]
    urls = upstream_sources.rocm_urls(MANIFEST)
    assert urls[0] == f"{amd['rocm_repo']}/rocm.gpg.key"
    for key in ("rocm_bleeding_version", "rocm_legacy_version"):
        assert f"{amd['rocm_repo']}/apt/{amd[key]}/dists/{amd['rocm_apt_suite']}/Release" in urls


def test_check_passes_when_every_source_answers(capsys: pytest.CaptureFixture[str]) -> None:
    published = set(upstream_sources.source_urls(MANIFEST))
    assert upstream_sources.main(["check"], fetch=answering(published)) == 0
    assert "3 of 3" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rocm_bleeding_version", "10.0"),
        ("rocm_legacy_version", "7.14"),
        ("rocm_apt_suite", "resolute"),
    ],
)
def test_check_refuses_an_unpublished_pin(
    field: str, value: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    published = set(upstream_sources.source_urls(MANIFEST))
    planted = copy.deepcopy(MANIFEST)
    planted["drivers"]["amd"][field] = value
    path = tmp_path / "versions.json"
    path.write_text(json.dumps(planted), encoding="utf-8")
    assert upstream_sources.main(["check", "--manifest", str(path)], fetch=answering(published)) == 1
    err = capsys.readouterr().err
    assert "404" in err and value in err


def test_check_reports_every_missing_url() -> None:
    urls = upstream_sources.source_urls(MANIFEST)
    assert upstream_sources.missing(urls, answering(set())) == [f"404 {url}" for url in urls]


def test_provisioner_fetches_the_checked_urls() -> None:
    """The provisioner must build the same key and apt URL the pre-flight checks."""
    script = ROCM_SCRIPT.read_text(encoding="utf-8")
    assert '"${ROCM_REPO}/rocm.gpg.key"' in script
    assert "${ROCM_REPO}/apt/${ROCM_VERSION} ${ROCM_APT_SUITE} main" in script
    assert "repo.radeon.com/rocm/" not in script.replace("o=repo.radeon.com", "")


def test_provisioner_fails_on_a_failed_index_update() -> None:
    script = ROCM_SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"apt-get update\s*\|\|", script) is None


def test_preflight_runs_before_the_packer_build() -> None:
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["build-matrix"]["steps"]
    names = [step.get("name", "") for step in steps]
    check = names.index("Check Upstream Package Sources")
    assert "tools/ci/upstream_sources.py check" in steps[check]["run"]
    assert check < names.index("Build Image with Packer")
