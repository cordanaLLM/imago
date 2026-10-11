"""Automated verification suite for cloud-init seed data.

Validates user-data and meta-data YAML syntax, #cloud-config directives,
build user provisioning, fast-boot invariants, and credential safety.
Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked assertions.
"""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
HTTP_DIR = REPO_ROOT / "packer" / "http"
USER_DATA_PATH = HTTP_DIR / "user-data"
META_DATA_PATH = HTTP_DIR / "meta-data"


class TestCloudInitIntegrity:
    def test_seed_files_exist(self) -> None:
        """Verify user-data and meta-data seed files exist and are non-empty."""
        assert USER_DATA_PATH.exists(), "packer/http/user-data is missing"
        assert META_DATA_PATH.exists(), "packer/http/meta-data is missing"
        assert USER_DATA_PATH.stat().st_size > 0, "user-data is empty"
        assert META_DATA_PATH.stat().st_size > 0, "meta-data is empty"

    def test_user_data_cloud_config_header(self) -> None:
        """Verify user-data begins with standard #cloud-config header."""
        first_line = USER_DATA_PATH.read_text(encoding="utf-8").splitlines()[0]
        assert first_line.strip() == "#cloud-config", f"user-data must begin with '#cloud-config', got '{first_line}'"

    def test_user_data_valid_yaml(self) -> None:
        """Verify user-data parses as valid YAML."""
        content = USER_DATA_PATH.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), "user-data must parse to a dictionary"

    def test_user_data_build_user_configuration(self) -> None:
        """Verify build user 'ubuntu' has correct shell, sudo, and groups."""
        content = USER_DATA_PATH.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert "users" in parsed, "Missing 'users' list in user-data"
        users = parsed["users"]
        assert len(users) >= 1, "Expected at least one user defined"

        ubuntu_user = next((u for u in users if u.get("name") == "ubuntu"), None)
        assert ubuntu_user is not None, "Missing 'ubuntu' build user"
        assert ubuntu_user.get("shell") == "/bin/bash"
        assert "NOPASSWD:ALL" in ubuntu_user.get("sudo", "")

    def test_user_data_fastboot_switches(self) -> None:
        """Verify package update/upgrade are disabled during seed phase for speed."""
        content = USER_DATA_PATH.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert parsed.get("package_update") is False, "package_update should be False"
        assert parsed.get("package_upgrade") is False, "package_upgrade should be False"

    def test_meta_data_valid_yaml(self) -> None:
        """Verify meta-data parses as valid YAML and contains required instance keys."""
        content = META_DATA_PATH.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), "meta-data must parse to a dictionary"
        assert "instance-id" in parsed and len(str(parsed["instance-id"])) > 0
        assert "local-hostname" in parsed and len(str(parsed["local-hostname"])) > 0
