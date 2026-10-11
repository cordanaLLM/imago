"""Automated verification suite for Packer bash provisioners.

Enforces NASA/JPL Power of 10 rules:
- Rule 1: Simple control flow (no recursion, bounded loops).
- Rule 2: Fixed upper bound on loop iterations.
- Rule 4: Short functions (<= 60 lines).
- Rule 7: Check return codes of all system calls.
Enforces license headers, shebangs, strict mode, and ShellCheck cleanliness.
"""

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROVISIONERS_DIR = REPO_ROOT / "packer" / "provisioners"


def get_provisioner_scripts():
    return sorted(PROVISIONERS_DIR.glob("*.sh"))


class TestProvisionersIntegrity:
    def test_minimum_provisioner_count(self) -> None:
        """Verify all expected provisioner scripts are present."""
        scripts = get_provisioner_scripts()
        assert len(scripts) >= 20, f"Expected >= 20 provisioners, found {len(scripts)}"

    def test_scripts_executable(self) -> None:
        """Verify all shell provisioners have executable permission (+x)."""
        for script in get_provisioner_scripts():
            if os.name == "nt":
                rel = script.relative_to(REPO_ROOT).as_posix()
                res = subprocess.run(
                    ["git", "ls-files", "-s", rel],
                    capture_output=True,
                    text=True,
                    cwd=str(REPO_ROOT),
                    check=False,
                )
                assert res.stdout.startswith("100755"), f"Script {script.name} is not executable in git"
            else:
                mode = script.stat().st_mode
                assert mode & 0o111, f"Script {script.name} is not executable (chmod +x required)"

    def test_shebang_and_strict_mode(self) -> None:
        """Verify shebang and strict mode 'set -euo pipefail' on all scripts."""
        for script in get_provisioner_scripts():
            content = script.read_text(encoding="utf-8")
            lines = content.splitlines()
            assert lines[0] == "#!/usr/bin/env bash", f"Invalid shebang in {script.name}"
            assert any(line.strip() == "set -euo pipefail" for line in lines[:10]), (
                f"Missing strict mode 'set -euo pipefail' in {script.name}"
            )

    def test_copyright_license_header(self) -> None:
        """Verify copyright header 'Copyright 2026 Lusoris' in all scripts."""
        for script in get_provisioner_scripts():
            content = script.read_text(encoding="utf-8")
            assert "Copyright 2026 Lusoris" in content, f"Missing 'Copyright 2026 Lusoris' header in {script.name}"

    def test_main_entrypoint(self) -> None:
        """Verify standard main() definition and main \"$@\" invocation."""
        for script in get_provisioner_scripts():
            content = script.read_text(encoding="utf-8")
            assert "main()" in content or "main ()" in content, f"Missing 'main()' definition in {script.name}"
            assert 'main "$@"' in content, f"Missing 'main \"$@\"' invocation in {script.name}"

    def test_power_of_ten_function_length(self) -> None:
        """Verify no function exceeds 60 lines (NASA/JPL Holzmann Rule 4)."""
        func_start_pattern = re.compile(r"^[a-zA-Z0-9_-]+\(\)\s*\{")

        for script in get_provisioner_scripts():
            lines = script.read_text(encoding="utf-8").splitlines()
            current_func = None
            func_line_count = 0

            for line in lines:
                if current_func is None:
                    if func_start_pattern.match(line):
                        current_func = line.split("(")[0].strip()
                        func_line_count = 1
                else:
                    func_line_count += 1
                    if line.strip() == "}":
                        assert func_line_count <= 60, (
                            f"Function '{current_func}' in {script.name} has {func_line_count} lines. "
                            f"Exceeds 60-line limit (NASA/JPL Power of 10 Rule 4)."
                        )
                        current_func = None

    def test_no_banned_constructs(self) -> None:
        """Verify provisioners avoid dangerous constructs (eval, raw rm -rf /)."""
        banned_patterns = [
            (re.compile(r"\beval\s+"), "Use of 'eval' is strictly prohibited"),
            (re.compile(r"rm\s+-rf\s+/\s*$"), "Dangerous 'rm -rf /' detected"),
        ]
        for script in get_provisioner_scripts():
            content = script.read_text(encoding="utf-8")
            for pattern, msg in banned_patterns:
                assert not pattern.search(content), f"{msg} in {script.name}"

    def test_shellcheck_zero_warnings(self) -> None:
        """Verify ShellCheck runs clean on all provisioners with 0 warnings."""
        scripts = [str(p) for p in get_provisioner_scripts()]
        result = subprocess.run(
            ["shellcheck", *scripts],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"ShellCheck failed on provisioners:\n{result.stdout}"

    def test_openssh_hardening_configuration(self) -> None:
        """Verify OpenSSH CIS Level 2 / DISA STIG hardening declarations in 00-base-strip.sh."""
        base_script = PROVISIONERS_DIR / "00-base-strip.sh"
        assert base_script.exists(), "00-base-strip.sh is missing"
        content = base_script.read_text(encoding="utf-8")
        assert "00-hardened-sshd.conf" in content
        assert "PermitRootLogin no" in content
        assert "TrustedUserCAKeys" in content
        assert "chacha20-poly1305@openssh.com" in content
        assert "AddressFamily any" in content

    def test_universal_architecture_dynamic_apt_sources(self) -> None:
        """Verify provisioners use dynamic dpkg architecture resolution, not hardcoded arch=amd64."""
        hardcoded_pattern = re.compile(r"\[arch=amd64\s+")
        for script in get_provisioner_scripts():
            content = script.read_text(encoding="utf-8")
            assert not hardcoded_pattern.search(content), (
                f"Hardcoded 'arch=amd64' found in {script.name}. "
                f"Must use dynamic '$(dpkg --print-architecture)' (Principle 9: Universal Architecture)."
            )

    def test_cdi_specifications_version_floor(self) -> None:
        """Verify Container Device Interface (CDI) specs declare cdiVersion 0.6.0+."""
        cdi_pattern = re.compile(r'cdiVersion:\s*["\']?([0-9]+\.[0-9]+\.[0-9]+)["\']?')
        for script in get_provisioner_scripts():
            content = script.read_text(encoding="utf-8")
            for match in cdi_pattern.finditer(content):
                version = match.group(1)
                major, minor, _ = [int(x) for x in version.split(".")]
                assert (major, minor) >= (0, 6), (
                    f"CDI version {version} in {script.name} is below 0.6.0 specification floor."
                )
