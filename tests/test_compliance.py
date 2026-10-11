# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""
Automated verification suite for declarative dynamic compliance profile (tests/compliance/goss.yaml).
Asserts syntax validity, CIS Level 2 / NIST SP 800-53 control mappings, and synchrony
with kernel sysctl provisioner declarations.
"""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
GOSS_SPEC = REPO_ROOT / "tests" / "compliance" / "goss.yaml"
SYSCTL_PROVISIONER = REPO_ROOT / "packer" / "provisioners" / "20-kernel-sysctl.sh"


def load_goss_profile() -> dict:
    assert GOSS_SPEC.is_file(), f"Missing {GOSS_SPEC}"
    return yaml.safe_load(GOSS_SPEC.read_text(encoding="utf-8"))


class TestComplianceIntegrity:
    """Validates Goss compliance specification integrity and cross-references with provisioners."""

    def test_goss_yaml_validity(self) -> None:
        profile = load_goss_profile()
        assert "kernel-param" in profile, "Missing 'kernel-param' section in goss.yaml"
        assert "file" in profile, "Missing 'file' section in goss.yaml"
        assert "service" in profile, "Missing 'service' section in goss.yaml"

    def test_cis_kernel_params_covered(self) -> None:
        profile = load_goss_profile()
        params = profile["kernel-param"]

        required_params = [
            "kernel.randomize_va_space",
            "kernel.dmesg_restrict",
            "kernel.kptr_restrict",
            "kernel.yama.ptrace_scope",
            "fs.suid_dumpable",
            "fs.protected_hardlinks",
            "fs.protected_symlinks",
            "net.core.bpf_jit_harden",
            "net.ipv4.tcp_syncookies",
            "net.ipv4.conf.all.rp_filter",
            "net.ipv4.conf.all.accept_redirects",
            "net.ipv4.conf.all.send_redirects",
        ]

        for param in required_params:
            assert param in params, f"Parameter '{param}' missing in goss.yaml compliance profile"

    def test_ssh_file_hardening_assertions(self) -> None:
        profile = load_goss_profile()
        files = profile["file"]

        sshd_conf = "/etc/ssh/sshd_config.d/00-hardened-sshd.conf"
        assert sshd_conf in files, f"Missing {sshd_conf} in goss.yaml"
        assert files[sshd_conf].get("mode") == "0600"
        assert files[sshd_conf].get("owner") == "root"

        contents = files[sshd_conf].get("contents", [])
        assert any("PermitRootLogin no" in c for c in contents)
        assert any("chacha20-poly1305@openssh.com" in c for c in contents)

    def test_sysctl_provisioner_synchrony(self) -> None:
        profile = load_goss_profile()
        sysctl_text = SYSCTL_PROVISIONER.read_text(encoding="utf-8")

        for param, spec in profile["kernel-param"].items():
            expected_val = str(spec.get("value"))
            pattern = f"{param} = {expected_val}"
            assert pattern in sysctl_text, f"Declared compliance parameter '{pattern}' not found in 20-kernel-sysctl.sh"
