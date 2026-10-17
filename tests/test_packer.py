"""Automated verification suite for Packer HCL2 templates and configuration.

Validates Packer configuration syntax (packer validate), variable declarations,
type safety, description completeness, and source builder declarations.
Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked assertions.
"""

import os
import re
import subprocess
from pathlib import Path

from tests.harness.live import skip_or_fail

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKER_DIR = REPO_ROOT / "packer"
VARIABLES_FILE = PACKER_DIR / "variables.pkr.hcl"
SOURCES_FILE = PACKER_DIR / "sources.pkr.hcl"
VERSIONS_FILE = PACKER_DIR / "versions.pkr.hcl"


class TestPackerIntegrity:
    def test_packer_validate(self) -> None:
        """Verify Packer configuration passes validation with packer validate ."""
        result = subprocess.run(
            ["packer", "validate", "."],
            cwd=str(PACKER_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stderr or result.stdout
        if result.returncode != 0 and "Unsupported Packer Core version" in output:
            skip_or_fail(f"installed packer does not satisfy required_version: {output.strip()}", os.environ)
        assert result.returncode == 0, f"Packer validation failed: {output}"

    def test_variables_declarations(self) -> None:
        """Verify all declared variables in variables.pkr.hcl specify type and description."""
        assert VARIABLES_FILE.exists(), "packer/variables.pkr.hcl is missing"
        content = VARIABLES_FILE.read_text(encoding="utf-8")

        var_blocks = re.findall(r'variable\s*"([^"]+)"\s*\{([^}]+)\}', content)
        assert len(var_blocks) >= 10, f"Expected >= 10 variables, found {len(var_blocks)}"

        for var_name, body in var_blocks:
            assert "type" in body, f"Variable '{var_name}' is missing 'type' declaration"
            assert "description" in body, f"Variable '{var_name}' is missing 'description' field"

    def test_sources_declarations(self) -> None:
        """Verify sources.pkr.hcl defines QEMU and Proxmox builders with proper cloud-init paths."""
        assert SOURCES_FILE.exists(), "packer/sources.pkr.hcl is missing"
        content = SOURCES_FILE.read_text(encoding="utf-8")

        assert 'source "qemu" "image"' in content, "Missing QEMU image source builder"
        assert 'source "proxmox-clone" "template"' in content, "Missing Proxmox template source builder"
        assert "meta-data" in content and "user-data" in content, (
            "QEMU builder must reference cloud-init meta-data and user-data"
        )

    def test_versions_pkr_plugins(self) -> None:
        """Verify versions.pkr.hcl specifies required plugins for qemu and proxmox."""
        assert VERSIONS_FILE.exists(), "packer/versions.pkr.hcl is missing"
        content = VERSIONS_FILE.read_text(encoding="utf-8")

        assert "required_version" in content, "Missing required_version in versions.pkr.hcl"
        assert "qemu" in content, "Missing qemu plugin declaration in versions.pkr.hcl"
        assert "proxmox" in content, "Missing proxmox plugin declaration in versions.pkr.hcl"
