# Copyright 2026 Lusoris
"""Automated verification suite executing shell provisioners in a hermetic mock sandbox.

Verifies runtime execution under 'set -euo pipefail', environment variable expansion,
package installation commands, service masking, and generated system configurations.
"""

import os
from pathlib import Path

import pytest

from tests.harness.live import skip_or_fail
from tests.harness.mock_runner import GIT_BASH, MockSandbox

REPO_ROOT = Path(__file__).resolve().parent.parent
PROVISIONERS_DIR = REPO_ROOT / "packer" / "provisioners"


def check_bash(bash: Path | None) -> None:
    """Skip, or in CI fail, when no bash runs the mock sandbox."""
    if not bash or not bash.exists():
        skip_or_fail(f"Bash required for mock execution tests, not found (got {bash})", os.environ)


@pytest.fixture
def require_bash():
    check_bash(GIT_BASH)


class TestProvisionersExecution:
    def test_00_base_strip_execution(self, tmp_path: Path, require_bash) -> None:
        """Verify 00-base-strip.sh executes cleanly, purges snapd, and hardens OpenSSH."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "00-base-strip.sh"

        res = sandbox.run_script(script)
        assert res.returncode == 0, f"Script failed with stderr: {res.stderr}"

        # Assert OpenSSH config generated with dual-stack and CIS baseline
        ssh_conf = res.read_file("etc/ssh/sshd_config.d/00-hardened-sshd.conf")
        assert ssh_conf is not None, "00-hardened-sshd.conf was not created"
        assert "AddressFamily any" in ssh_conf
        assert "PermitRootLogin no" in ssh_conf
        assert "chacha20-poly1305" in ssh_conf

        # Assert package purge command
        apt_cmds = res.find_commands("apt-get")
        assert any("purge" in cmd and "snapd" in cmd for cmd in apt_cmds)
        assert any("purge" in cmd and "lxd" in cmd for cmd in apt_cmds)

    def test_20_kernel_sysctl_execution(self, tmp_path: Path, require_bash) -> None:
        """Verify 20-kernel-sysctl.sh sets BBR, syncookies, and kernel profiles."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "20-kernel-sysctl.sh"

        res = sandbox.run_script(script, env_vars={"KERNEL_PROFILE": "ai-infer"})
        assert res.returncode == 0, f"Script failed with stderr: {res.stderr}"

        sysctl_conf = res.read_file("etc/sysctl.d/99-lusoris.conf")
        assert sysctl_conf is not None, "99-lusoris.conf was not created"
        assert "net.ipv4.tcp_syncookies = 1" in sysctl_conf
        assert "net.ipv4.tcp_congestion_control = bbr" in sysctl_conf
        assert "net.core.default_qdisc = fq" in sysctl_conf

        blacklist_conf = res.read_file("etc/modprobe.d/blacklist-uncommon.conf")
        assert blacklist_conf is not None
        assert "install dccp /bin/true" in blacklist_conf

    def test_25_baremetal_tuning_execution(self, tmp_path: Path, require_bash) -> None:
        """Verify 25-baremetal-tuning.sh requests parted and configures mq-deadline."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "25-baremetal-tuning.sh"

        res = sandbox.run_script(script)
        assert res.returncode == 0, f"Script failed with stderr: {res.stderr}"

        # Assert parted package is requested, not partprobe
        apt_cmds = res.find_commands("apt-get")
        assert any("parted" in cmd for cmd in apt_cmds)
        assert not any("partprobe" in cmd for cmd in apt_cmds)

        udev_rules = res.read_file("etc/udev/rules.d/60-baremetal-storage.rules")
        assert udev_rules is not None
        assert "mq-deadline" in udev_rules

    def test_32_gpu_amd_rocm_dynamic_architecture(self, tmp_path: Path, require_bash) -> None:
        """Verify 32-gpu-amd-rocm.sh resolves architecture dynamically without hardcoding."""
        sandbox = MockSandbox(tmp_path, arch="arm64")
        script = PROVISIONERS_DIR / "32-gpu-amd-rocm.sh"

        res = sandbox.run_script(script)
        assert res.returncode == 0, f"Script failed with stderr: {res.stderr}"

        dpkg_cmds = res.find_commands("dpkg")
        assert any("--print-architecture" in cmd for cmd in dpkg_cmds)

    def test_40_docker_runtime_execution(self, tmp_path: Path, require_bash) -> None:
        """Verify 40-docker-runtime.sh generates daemon.json and uses dynamic arch."""
        sandbox = MockSandbox(tmp_path, arch="amd64")
        script = PROVISIONERS_DIR / "40-docker-runtime.sh"

        res = sandbox.run_script(script)
        assert res.returncode == 0, f"Script failed with stderr: {res.stderr}"

        daemon_json = res.read_file("etc/docker/daemon.json")
        assert daemon_json is not None
        assert "log-driver" in daemon_json
        assert "max-size" in daemon_json

    def test_50_k8s_runtime_containerd2_cri(self, tmp_path: Path, require_bash) -> None:
        """Verify 50-k8s-runtime.sh generates containerd 2.x CRI runtime schema with crun."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "50-k8s-runtime.sh"

        res = sandbox.run_script(script)
        assert res.returncode == 0, f"Script failed with stderr: {res.stderr}"

        containerd_conf = res.read_file("etc/containerd/config.toml")
        assert containerd_conf is not None
        assert "crun" in containerd_conf
        assert 'plugins."io.containerd.cri.v1.runtime".containerd.runtimes.crun' in containerd_conf

    def test_75_appliance_vision_cdi_version(self, tmp_path: Path, require_bash) -> None:
        """Verify 75-appliance-vision.sh writes CDI specification with version '0.6.0'."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "75-appliance-vision.sh"

        res = sandbox.run_script(script)
        assert res.returncode == 0, f"Script failed with stderr: {res.stderr}"

        cdi_spec = res.read_file("etc/cdi/coral.yaml")
        assert cdi_spec is not None
        assert 'cdiVersion: "0.6.0"' in cdi_spec

    def test_79_appliance_game_architecture_guard(self, tmp_path: Path, require_bash) -> None:
        """Verify 79-appliance-game.sh only adds i386 on amd64 and bypasses on arm64."""
        # Scenario 1: amd64 host
        sandbox_amd64 = MockSandbox(tmp_path / "amd64", arch="amd64")
        script = PROVISIONERS_DIR / "79-appliance-game.sh"
        res_amd64 = sandbox_amd64.run_script(script)
        assert res_amd64.returncode == 0
        dpkg_cmds_amd64 = res_amd64.find_commands("dpkg")
        assert any("--add-architecture i386" in cmd for cmd in dpkg_cmds_amd64)

        # Scenario 2: arm64 host
        sandbox_arm64 = MockSandbox(tmp_path / "arm64", arch="arm64")
        res_arm64 = sandbox_arm64.run_script(script)
        assert res_arm64.returncode == 0
        dpkg_cmds_arm64 = res_arm64.find_commands("dpkg")
        assert not any("--add-architecture i386" in cmd for cmd in dpkg_cmds_arm64)


class TestProvisionersFailClosed:
    """A provisioner step that fails must fail the build instead of being swallowed."""

    @pytest.mark.parametrize(
        ("script_name", "failing_command"),
        [
            ("00-base-strip.sh", "apt-mark"),
            ("32-gpu-amd-rocm.sh", "usermod"),
            ("40-docker-runtime.sh", "usermod"),
            ("75-appliance-vision.sh", "usermod"),
            ("79-appliance-game.sh", "debconf-set-selections"),
        ],
    )
    def test_failed_step_fails_the_script(
        self, tmp_path: Path, require_bash, script_name: str, failing_command: str
    ) -> None:
        sandbox = MockSandbox(tmp_path)
        res = sandbox.run_script(PROVISIONERS_DIR / script_name, env_vars={"MOCK_FAIL": failing_command})
        assert res.returncode != 0, f"{script_name} ignored a failed {failing_command}"
        assert res.has_command(failing_command), f"{failing_command} was never reached"

    def test_group_membership_is_requested(self, tmp_path: Path, require_bash) -> None:
        """The mocked usermod records the call, so it never reaches the host's real usermod."""
        sandbox = MockSandbox(tmp_path)
        res = sandbox.run_script(PROVISIONERS_DIR / "40-docker-runtime.sh")
        assert res.returncode == 0, f"Script failed with stderr: {res.stderr}"
        assert "usermod -aG docker ubuntu" in res.commands_log

    def test_unloadable_module_is_reported_not_fatal(self, tmp_path: Path, require_bash) -> None:
        """Boundary: a module the build kernel cannot load is reported and the build goes on."""
        sandbox = MockSandbox(tmp_path)
        res = sandbox.run_script(
            PROVISIONERS_DIR / "20-kernel-sysctl.sh",
            env_vars={"KERNEL_PROFILE": "ai-infer", "MOCK_FAIL": "modprobe"},
        )
        assert res.returncode == 0, f"Script failed with stderr: {res.stderr}"
        assert "Module overlay did not load" in res.stderr
