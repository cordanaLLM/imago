# Copyright 2026 Lusoris
"""Automated verification suite for container-structure-test integration.

Validates that every Packer build wires the structure-tests file provisioner
before its shell provisioner, positions 98-structure-test.sh immediately before
99-cleanup.sh, and ensures all test configurations conform to schema 2.0.0.
Also executes live host driver verification with planted pass and fail fixtures.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.harness.live import skip_or_fail
from tests.harness.mock_runner import GIT_BASH, MockSandbox

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILDS_HCL_PATH = REPO_ROOT / "packer" / "builds.pkr.hcl"
CONFIGS_DIR = REPO_ROOT / "packer" / "structure-tests"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "structure-tests"
PROVISIONERS_DIR = REPO_ROOT / "packer" / "provisioners"
# A host driver run over a few files returns in well under a second.
CST_RUN_BOUND_S = 60
# The provisioners whose files common.yaml checks; every build runs them.
BASE_PROVISIONERS = (
    "00-base-strip.sh",
    "05-hypervisor-agents.sh",
    "10-network-time.sh",
    "20-kernel-sysctl.sh",
)
BASE_ENV = {"FLAVOR": "base-generic", "BM_GEN": "generic", "KERNEL_PROFILE": "generic"}


def find_cst_bin() -> Path | None:
    env_bin = os.environ.get("IMAGO_CST_BIN")
    if env_bin and Path(env_bin).exists():
        return Path(env_bin)
    which_bin = shutil.which("container-structure-test")
    return Path(which_bin) if which_bin else None


def run_cst(cst_bin: Path, config: Path) -> subprocess.CompletedProcess[str]:
    cmd = [str(cst_bin), "test", "--driver", "host", "--force", "--metadata", "/dev/null"]
    return subprocess.run(
        [*cmd, "--no-color", "--config", str(config)],
        capture_output=True,
        text=True,
        timeout=CST_RUN_BOUND_S,
        check=False,
    )


def rebase_file_tests(config: dict, root: Path) -> dict:
    """Keep the file tests of `config` and point their paths into `root`.

    Command tests need the booted guest (systemctl, enroot) and stay with the Packer build.
    """
    rebased: dict = {"schemaVersion": config["schemaVersion"]}
    for key in ("fileContentTests", "fileExistenceTests"):
        tests = [dict(t, path=f"{root}{t['path']}") for t in config.get(key, [])]
        if tests:
            rebased[key] = tests
    return rebased


def write_base_tree(tmp_path: Path) -> Path:
    """Run the base provisioners in the mock sandbox; return the root they wrote into."""
    stub_dir = tmp_path / "stubs"
    stub_dir.mkdir()
    # 10-network-time.sh validates its configuration with `chronyd -p`, which the sandbox lacks.
    chronyd = stub_dir / "chronyd"
    chronyd.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8", newline="\n")
    chronyd.chmod(0o755)
    sandbox = MockSandbox(tmp_path / "sandbox")
    env = dict(BASE_ENV, PATH=f"{stub_dir}{os.pathsep}{os.environ['PATH']}")
    for script in BASE_PROVISIONERS:
        res = sandbox.run_script(PROVISIONERS_DIR / script, env)
        assert res.returncode == 0, f"{script} failed in the sandbox: {res.stderr[-800:]}"
    return sandbox.sandbox_root


class TestStructureTestsWiring:
    def test_builds_file_and_shell_provisioner_wiring(self) -> None:
        """Verify all builds wire file provisioner before shell and 98 directly before 99."""
        assert BUILDS_HCL_PATH.exists(), "packer/builds.pkr.hcl is missing"
        content = BUILDS_HCL_PATH.read_text(encoding="utf-8")

        build_blocks = re.findall(r"build\s*\{.*?\n\}", content, re.DOTALL)
        assert len(build_blocks) >= 44, f"Expected >= 44 build blocks, found {len(build_blocks)}"

        verified = 0
        for block in build_blocks:
            name_m = re.search(r'name\s*=\s*"([^"]+)"', block)
            assert name_m is not None, "Build block missing name"
            build_name = name_m.group(1)

            file_idx = block.find('provisioner "file"')
            shell_idx = block.find('provisioner "shell"')
            assert file_idx != -1, f"Build '{build_name}' missing provisioner 'file'"
            assert shell_idx != -1, f"Build '{build_name}' missing provisioner 'shell'"
            assert file_idx < shell_idx, (
                f"Build '{build_name}' must declare provisioner 'file' before provisioner 'shell'"
            )

            # Packer requires a directory upload's destination to exist; without a trailing slash on
            # the source, Packer creates /tmp/structure-tests itself inside the existing /tmp.
            assert 'source      = "${path.root}/structure-tests"\n' in block, (
                f"Build '{build_name}' must upload packer/structure-tests without a trailing slash"
            )
            assert 'destination = "/tmp"\n' in block, f"Build '{build_name}' must upload structure-tests into /tmp"

            scripts = re.findall(r'"[^"]*provisioners/([^"]+)"', block)
            assert "98-structure-test.sh" in scripts, f"Build '{build_name}' missing 98-structure-test.sh in scripts"
            assert "99-cleanup.sh" in scripts, f"Build '{build_name}' missing 99-cleanup.sh in scripts"

            idx_98 = scripts.index("98-structure-test.sh")
            idx_99 = scripts.index("99-cleanup.sh")
            assert idx_98 + 1 == idx_99, (
                f"Build '{build_name}' must list 98-structure-test.sh immediately before 99-cleanup.sh"
            )
            verified += 1

        assert verified == len(build_blocks), f"Verified {verified} builds, expected {len(build_blocks)}"


class TestStructureTestsConfigs:
    def test_configs_validity_and_schema(self) -> None:
        """Verify structure-tests configurations are valid YAML, schema 2.0.0, and non-empty."""
        assert CONFIGS_DIR.exists() and CONFIGS_DIR.is_dir(), "packer/structure-tests is missing"
        config_files = sorted(CONFIGS_DIR.glob("*.yaml"))
        config_names = {f.name for f in config_files}

        expected = {"common.yaml", "k8s.yaml", "enroot.yaml"}
        assert expected <= config_names, f"Missing required configs: {expected - config_names}"

        for cfg_file in config_files:
            data = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
            assert isinstance(data, dict), f"Config {cfg_file.name} must parse as dictionary"
            assert data.get("schemaVersion") == "2.0.0", f"Config {cfg_file.name} must specify schemaVersion '2.0.0'"

            test_keys = ("commandTests", "fileContentTests", "fileExistenceTests")
            total_tests = sum(len(data.get(k, [])) for k in test_keys)
            assert total_tests >= 1, f"Config {cfg_file.name} must contain at least 1 test, found {total_tests}"


@pytest.fixture
def cst_bin() -> Path:
    found = find_cst_bin()
    if found is None:
        skip_or_fail("container-structure-test binary required for live verification", os.environ)
    return found


@pytest.fixture
def base_tree(tmp_path: Path) -> Path:
    if not GIT_BASH:
        skip_or_fail("bash is required to run the provisioners in the sandbox", os.environ)
    return write_base_tree(tmp_path)


def rebased_common(base_tree: Path, out: Path) -> Path:
    config = yaml.safe_load((CONFIGS_DIR / "common.yaml").read_text(encoding="utf-8"))
    out.write_text(yaml.safe_dump(rebase_file_tests(config, base_tree)), encoding="utf-8")
    return out


class TestStructureTestsLive:
    def test_planted_fail_case(self, cst_bin: Path) -> None:
        """The host driver fails on the planted missing path and names the test."""
        res = run_cst(cst_bin, FIXTURES_DIR / "planted-fail.yaml")
        assert res.returncode != 0, "Planted failure fixture unexpectedly passed"
        assert "planted-failure-nonexistent-path" in res.stdout + res.stderr

    def test_planted_pass_case(self, cst_bin: Path) -> None:
        """The host driver passes on a file every Linux host carries (/etc/os-release)."""
        res = run_cst(cst_bin, FIXTURES_DIR / "planted-pass.yaml")
        assert res.returncode == 0, f"Planted pass fixture failed: {res.stderr}\n{res.stdout}"

    def test_common_file_tests_pass_on_provisioned_tree(self, cst_bin: Path, base_tree: Path, tmp_path: Path) -> None:
        """The file tests of common.yaml hold on the files the base provisioners write."""
        res = run_cst(cst_bin, rebased_common(base_tree, tmp_path / "common.yaml"))
        assert res.returncode == 0, f"common.yaml file tests failed on the provisioned tree:\n{res.stdout}"

    def test_common_file_tests_fail_on_planted_drift(self, cst_bin: Path, base_tree: Path, tmp_path: Path) -> None:
        """A provisioned file that lost one expected line fails its content test."""
        conf = base_tree / "etc" / "modules-load.d" / "unraid-virtfs.conf"
        lines = conf.read_text(encoding="utf-8").splitlines()
        assert "9p" in lines, "planted drift needs the 9p line the provisioner writes"
        conf.write_text("\n".join(line for line in lines if line != "9p") + "\n", encoding="utf-8")
        res = run_cst(cst_bin, rebased_common(base_tree, tmp_path / "common.yaml"))
        assert res.returncode != 0, "removing the 9p line did not fail common.yaml"
        assert "unraid-virtfs modules-load configuration" in res.stdout
