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

    def test_51_stargz_snapshotter_execution(self, tmp_path: Path, require_bash) -> None:
        """Verify 51-stargz-snapshotter.sh configures service and containerd proxy plugin idempotently."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "51-stargz-snapshotter.sh"

        res = sandbox.run_script(script, env_vars={"STARGZ_VERSION": "0.18.2"})
        assert res.returncode == 0, f"Script failed with stderr: {res.stderr}"

        # containerd config has proxy plugin block
        containerd_conf = res.read_file("etc/containerd/config.toml")
        assert containerd_conf is not None
        assert "[proxy_plugins.stargz]" in containerd_conf
        assert 'type = "snapshot"' in containerd_conf
        assert 'address = "/run/containerd-stargz-grpc/containerd-stargz-grpc.sock"' in containerd_conf

        # Systemd service and config created
        svc = res.read_file("etc/systemd/system/stargz-snapshotter.service")
        assert svc is not None
        assert "ExecStart=/usr/local/bin/containerd-stargz-grpc" in svc
        assert "--log-level=info" in svc

        cfg = res.read_file("etc/containerd-stargz-grpc/config.toml")
        assert cfg is not None

        sys_cmds = res.find_commands("systemctl")
        assert any("enable" in cmd and "stargz-snapshotter" in cmd for cmd in sys_cmds)

        # Idempotency check: second run should not duplicate the proxy plugin block
        res2 = sandbox.run_script(script, env_vars={"STARGZ_VERSION": "0.18.2"})
        assert res2.returncode == 0
        containerd_conf2 = res2.read_file("etc/containerd/config.toml")
        assert containerd_conf2.count("[proxy_plugins.stargz]") == 1

    def test_51_stargz_snapshotter_checksum_mismatch(self, tmp_path: Path, require_bash) -> None:
        """Negative: checksum mismatch must fail closed and install nothing."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "51-stargz-snapshotter.sh"

        res = sandbox.run_script(script, env_vars={"STARGZ_VERSION": "0.18.2", "MOCK_MISMATCH_SHA": "1"})
        assert res.returncode != 0
        assert "Checksum verification failed" in res.stderr
        assert res.read_file("etc/containerd/config.toml") is None
        assert res.read_file("etc/systemd/system/stargz-snapshotter.service") is None

    def test_51_stargz_snapshotter_boundaries(self, tmp_path: Path, require_bash) -> None:
        """Boundary: unknown architecture and missing STARGZ_VERSION must fail nonzero."""
        script = PROVISIONERS_DIR / "51-stargz-snapshotter.sh"

        # Boundary 1: unknown arch
        sandbox_mips = MockSandbox(tmp_path / "mips", arch="mips64")
        res_mips = sandbox_mips.run_script(script, env_vars={"STARGZ_VERSION": "0.18.2"})
        assert res_mips.returncode != 0
        assert "Unsupported architecture" in res_mips.stderr

        # Boundary 2: missing STARGZ_VERSION
        sandbox_no_ver = MockSandbox(tmp_path / "no_ver")
        res_no_ver = sandbox_no_ver.run_script(script, env_vars={"STARGZ_VERSION": ""})
        assert res_no_ver.returncode != 0

    def test_62_hpc_enroot_execution(self, tmp_path: Path, require_bash) -> None:
        """Positive: apt-get called with both ./debs and version verification succeeds."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "62-hpc-enroot.sh"

        res = sandbox.run_script(script, env_vars={"ENROOT_VERSION": "3.4.1"})
        assert res.returncode == 0, f"Script failed with stderr: {res.stderr}"

        apt_cmds = res.find_commands("apt-get")
        assert any(
            "install" in cmd and "enroot_3.4.1-1_amd64.deb" in cmd and "enroot+caps_3.4.1-1_amd64.deb" in cmd
            for cmd in apt_cmds
        )

    def test_62_hpc_enroot_version_mismatch(self, tmp_path: Path, require_bash) -> None:
        """Negative: version mismatch fails closed."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "62-hpc-enroot.sh"

        res = sandbox.run_script(script, env_vars={"ENROOT_VERSION": "3.4.1", "MOCK_ENROOT_VERSION": "1.0.0"})
        assert res.returncode != 0
        assert "enroot version check failed" in res.stderr

    def test_62_hpc_enroot_boundaries(self, tmp_path: Path, require_bash) -> None:
        """Boundary: missing ENROOT_VERSION must fail nonzero."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "62-hpc-enroot.sh"

        res = sandbox.run_script(script, env_vars={"ENROOT_VERSION": ""})
        assert res.returncode != 0

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

    def test_80_netboot_initrd_execution(self, tmp_path: Path, require_bash) -> None:
        """Verify 80-netboot-initrd.sh installs imago-netroot module and runs dracut."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "80-netboot-initrd.sh"
        res = sandbox.run_script(script)
        assert res.returncode == 0, f"Script failed with stderr: {res.stderr}"

        setup_sh = res.read_file("usr/lib/dracut/modules.d/95imago-netroot/module-setup.sh")
        assert setup_sh is not None, "module-setup.sh was not installed"
        assert "dmsquash-live" in setup_sh

        verify_sh = res.read_file("usr/lib/dracut/modules.d/95imago-netroot/imago-netroot-verify.sh")
        assert verify_sh is not None, "imago-netroot-verify.sh was not installed"
        assert "imago.root-sha256=" in verify_sh

        dracut_cmds = res.find_commands("dracut")
        assert len(dracut_cmds) >= 1
        assert any("--no-hostonly" in cmd and "imago-netboot" in cmd for cmd in dracut_cmds)

        assert any("lsinitrd /boot/imago-netboot.initrd" in cmd for cmd in res.find_commands("lsinitrd"))
        links = [c for c in res.find_commands("ln") if c.endswith(" /boot/imago-netboot.vmlinuz")]
        assert len(links) == 1 and links[0].startswith("ln -sfn vmlinuz-"), res.commands_log

    @pytest.mark.parametrize(
        "listing",
        [
            "dracut modules:\\nimago-netroot\\nusr/sbin/dmsquash-live-root",
            "dracut modules:\\nlivenet\\nusr/sbin/dmsquash-live-root\\nusr/sbin/dmsquash-live-root.orig",
        ],
        ids=["original-not-renamed", "module-missing"],
    )
    def test_80_netboot_initrd_refuses_an_unwrapped_initrd(self, tmp_path: Path, require_bash, listing: str) -> None:
        """dracut ignores a failing module install(); the read-back of the built initrd does not."""
        sandbox = MockSandbox(tmp_path)
        res = sandbox.run_script(PROVISIONERS_DIR / "80-netboot-initrd.sh", env_vars={"MOCK_LSINITRD_LISTING": listing})
        assert res.returncode != 0

    def test_98_structure_test_execution_positive(self, tmp_path: Path, require_bash) -> None:
        """Positive: downloads CST, verifies checksum, executes host driver, cleans up."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "98-structure-test.sh"

        cfg_dir = sandbox.sandbox_root / "tmp" / "structure-tests"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "common.yaml").write_text("schemaVersion: 2.0.0\n", encoding="utf-8")

        res = sandbox.run_script(script, env_vars={"CST_VERSION": "1.22.1", "FLAVOR": "base-generic"})
        assert res.returncode == 0, f"Script failed with stderr: {res.stderr}"

        curl_cmds = res.find_commands("curl")
        assert any("container-structure-test-linux-amd64" in cmd for cmd in curl_cmds)
        assert any("checksums.txt" in cmd for cmd in curl_cmds)

        cst_cmds = res.find_commands("container-structure-test")
        assert len(cst_cmds) == 1
        assert "--driver host" in cst_cmds[0]
        assert "--force" in cst_cmds[0]
        assert "--config /tmp/structure-tests/common.yaml" in cst_cmds[0]
        assert "k8s.yaml" not in cst_cmds[0]
        assert "enroot.yaml" not in cst_cmds[0]

        rm_cmds = res.find_commands("rm")
        assert any("/usr/local/bin/container-structure-test" in cmd for cmd in rm_cmds)
        assert any("/tmp/structure-tests" in cmd for cmd in rm_cmds)

    def test_98_structure_test_checksum_mismatch(self, tmp_path: Path, require_bash) -> None:
        """Negative: checksum mismatch must fail closed and never run CST."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "98-structure-test.sh"

        cfg_dir = sandbox.sandbox_root / "tmp" / "structure-tests"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "common.yaml").write_text("schemaVersion: 2.0.0\n", encoding="utf-8")

        res = sandbox.run_script(
            script,
            env_vars={"CST_VERSION": "1.22.1", "FLAVOR": "base-generic", "MOCK_MISMATCH_SHA": "1"},
        )
        assert res.returncode != 0
        assert "Checksum verification failed" in res.stderr
        assert not res.has_command("container-structure-test")

    def test_98_structure_test_missing_checksum_line(self, tmp_path: Path, require_bash) -> None:
        """Negative: checksums.txt lacking the asset line must fail closed."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "98-structure-test.sh"

        cfg_dir = sandbox.sandbox_root / "tmp" / "structure-tests"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "common.yaml").write_text("schemaVersion: 2.0.0\n", encoding="utf-8")

        res = sandbox.run_script(
            script,
            env_vars={"CST_VERSION": "1.22.1", "FLAVOR": "base-generic", "MOCK_CST_MISSING_LINE": "1"},
        )
        assert res.returncode != 0
        assert "Asset container-structure-test-linux-amd64 not found in checksums.txt" in res.stderr
        assert not res.has_command("container-structure-test")

    def test_98_structure_test_cst_nonzero_exit_fails(self, tmp_path: Path, require_bash) -> None:
        """Negative: nonzero exit from CST must fail the provisioner script."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "98-structure-test.sh"

        cfg_dir = sandbox.sandbox_root / "tmp" / "structure-tests"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "common.yaml").write_text("schemaVersion: 2.0.0\n", encoding="utf-8")

        res = sandbox.run_script(
            script,
            env_vars={"CST_VERSION": "1.22.1", "FLAVOR": "base-generic", "MOCK_CST_FAIL": "assertion-failed"},
        )
        assert res.returncode != 0
        assert "Container structure tests failed for flavor 'base-generic'" in res.stderr

    def test_98_structure_test_unknown_architecture(self, tmp_path: Path, require_bash) -> None:
        """Boundary: unsupported architecture must fail closed."""
        sandbox = MockSandbox(tmp_path, arch="mips64")
        script = PROVISIONERS_DIR / "98-structure-test.sh"

        res = sandbox.run_script(script, env_vars={"CST_VERSION": "1.22.1", "FLAVOR": "base-generic"})
        assert res.returncode != 0
        assert "Unsupported architecture" in res.stderr

    def test_98_structure_test_config_selection(self, tmp_path: Path, require_bash) -> None:
        """Verify dynamic config selection via filesystem and binary markers."""
        # Scenario 1: k8s marker present -> k8s.yaml included
        sandbox_k8s = MockSandbox(tmp_path / "k8s")
        cfg_dir_k8s = sandbox_k8s.sandbox_root / "tmp" / "structure-tests"
        cfg_dir_k8s.mkdir(parents=True, exist_ok=True)
        (cfg_dir_k8s / "common.yaml").write_text("schemaVersion: 2.0.0\n", encoding="utf-8")
        (cfg_dir_k8s / "k8s.yaml").write_text("schemaVersion: 2.0.0\n", encoding="utf-8")

        marker_k8s = sandbox_k8s.sandbox_root / "etc" / "systemd" / "system"
        marker_k8s.mkdir(parents=True, exist_ok=True)
        (marker_k8s / "stargz-snapshotter.service").touch()

        script = PROVISIONERS_DIR / "98-structure-test.sh"
        res_k8s = sandbox_k8s.run_script(script, env_vars={"CST_VERSION": "1.22.1", "FLAVOR": "k8s-node-generic"})
        assert res_k8s.returncode == 0, f"k8s selection failed: {res_k8s.stderr}"
        cst_cmds_k8s = res_k8s.find_commands("container-structure-test")
        assert len(cst_cmds_k8s) == 1
        assert "--config /tmp/structure-tests/common.yaml" in cst_cmds_k8s[0]
        assert "--config /tmp/structure-tests/k8s.yaml" in cst_cmds_k8s[0]
        assert "enroot.yaml" not in cst_cmds_k8s[0]

        # Scenario 2: enroot marker present -> enroot.yaml included
        sandbox_enroot = MockSandbox(tmp_path / "enroot")
        cfg_dir_enroot = sandbox_enroot.sandbox_root / "tmp" / "structure-tests"
        cfg_dir_enroot.mkdir(parents=True, exist_ok=True)
        (cfg_dir_enroot / "common.yaml").write_text("schemaVersion: 2.0.0\n", encoding="utf-8")
        (cfg_dir_enroot / "enroot.yaml").write_text("schemaVersion: 2.0.0\n", encoding="utf-8")

        res_enroot = sandbox_enroot.run_script(
            script,
            env_vars={"CST_VERSION": "1.22.1", "FLAVOR": "ai-infer-nvidia", "MOCK_HAS_ENROOT": "1"},
        )
        assert res_enroot.returncode == 0, f"enroot selection failed: {res_enroot.stderr}"
        cst_cmds_enroot = res_enroot.find_commands("container-structure-test")
        assert len(cst_cmds_enroot) == 1
        assert "--config /tmp/structure-tests/common.yaml" in cst_cmds_enroot[0]
        assert "--config /tmp/structure-tests/enroot.yaml" in cst_cmds_enroot[0]
        assert "k8s.yaml" not in cst_cmds_enroot[0]

    def test_98_structure_test_boundaries(self, tmp_path: Path, require_bash) -> None:
        """Boundary: missing required environment variables must fail nonzero."""
        sandbox = MockSandbox(tmp_path)
        script = PROVISIONERS_DIR / "98-structure-test.sh"

        res_no_cst = sandbox.run_script(script, env_vars={"CST_VERSION": "", "FLAVOR": "base-generic"})
        assert res_no_cst.returncode != 0

        res_no_flv = sandbox.run_script(script, env_vars={"CST_VERSION": "1.22.1", "FLAVOR": ""})
        assert res_no_flv.returncode != 0


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
            ("80-netboot-initrd.sh", "dracut"),
            ("80-netboot-initrd.sh", "lsinitrd"),
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
