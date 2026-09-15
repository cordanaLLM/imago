"""Automated verification suite for repository governance and project standards.

Validates presence of core governance contracts (AGENTS.md, CLAUDE.md, LICENSE),
semantic versioning format in VERSION, linter and scanner configurations,
and required CI/CD workflows.
Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked assertions.
"""

from pathlib import Path
import os
import re
import subprocess

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKER_DIR = REPO_ROOT / "packer"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


class TestGovernanceIntegrity:
    def test_core_files_exist(self) -> None:
        """Verify all core configuration, governance, and manifest files exist."""
        required_files = [
            REPO_ROOT / "AGENTS.md",
            REPO_ROOT / "CLAUDE.md",
            REPO_ROOT / "README.md",
            REPO_ROOT / "FLAVORS.md",
            REPO_ROOT / "LICENSE",
            REPO_ROOT / "VERSION",
            REPO_ROOT / "SECURITY.md",
            REPO_ROOT / "CONTRIBUTING.md",
            REPO_ROOT / "CODE_OF_CONDUCT.md",
            REPO_ROOT / "GOVERNANCE.md",
            REPO_ROOT / "SUPPORT.md",
            REPO_ROOT / "MAINTAINERS.md",
            REPO_ROOT / "CHANGELOG.md",
            REPO_ROOT / "mkdocs.yml",
            REPO_ROOT / "Makefile",
            REPO_ROOT / "versions.json",
            REPO_ROOT / "versions.schema.json",
            REPO_ROOT / ".pre-commit-config.yaml",
            REPO_ROOT / ".yamllint.yml",
            REPO_ROOT / ".gitleaks.toml",
            REPO_ROOT / ".markdownlint.json",
            REPO_ROOT / ".codespellrc",
            REPO_ROOT / "release-please-config.json",
            REPO_ROOT / ".release-please-manifest.json",
            REPO_ROOT / "renovate.json",
            REPO_ROOT / "requirements-test.txt",
            REPO_ROOT / ".github" / "epics.json",
            REPO_ROOT / ".github" / "milestones.json",
            REPO_ROOT / "go.mod",
            REPO_ROOT / "cmd" / "imago" / "main.go",
            REPO_ROOT / "docs" / "hardware" / "architectures-and-form-factors.md",
            REPO_ROOT / "docs" / "standards" / "hardware-market-and-datacenter-survey.md",
            REPO_ROOT / "docs" / "standards" / "flavor-hardening-standards.md",
            REPO_ROOT / "docs" / "standards" / "image-optimization-and-hardening.md",
            REPO_ROOT / "docs" / "standards" / "open-standards-architecture.md",
            REPO_ROOT / "docs" / "platforms" / "macos.md",
            REPO_ROOT / "docs" / "platforms" / "windows.md",
            REPO_ROOT / "docs" / "operations" / "maintenance-cadence.md",
            REPO_ROOT / "docs" / "tools" / "cli-mcp.md",
            REPO_ROOT / "scripts" / "audit-repository-health.sh",
        ]
        for file_path in required_files:
            assert file_path.exists(), f"Missing required file: {file_path}"
            assert file_path.stat().st_size > 0, f"File is empty: {file_path}"

    def test_version_file_semver(self) -> None:
        """Verify VERSION file adheres strictly to semantic versioning (X.Y.Z)."""
        version_path = REPO_ROOT / "VERSION"
        assert version_path.exists(), "VERSION file is missing"
        version_str = version_path.read_text(encoding="utf-8").strip()
        assert re.match(r"^\d+\.\d+\.\d+$", version_str), (
            f"VERSION '{version_str}' does not conform to semver format (X.Y.Z)"
        )

    def test_license_terms_and_copyright(self) -> None:
        """Verify LICENSE file contains Apache 2.0 terms and README/mkdocs state copyright."""
        license_path = REPO_ROOT / "LICENSE"
        assert license_path.exists(), "LICENSE file is missing"
        content = license_path.read_text(encoding="utf-8")
        assert "Apache License" in content, "Missing Apache License terms in LICENSE"
        assert "Version 2.0" in content, "Missing Version 2.0 declaration in LICENSE"

        readme_content = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        assert "Lusoris Authors" in readme_content, "Missing Lusoris copyright in README.md"

        mkdocs_content = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
        assert "The Lusoris Authors" in mkdocs_content, "Missing Lusoris copyright in mkdocs.yml"

    def test_agent_directives_parity(self) -> None:
        """Verify AGENTS.md and CLAUDE.md reference principles.md contract."""
        agents_md = REPO_ROOT / "AGENTS.md"
        claude_md = REPO_ROOT / "CLAUDE.md"
        assert agents_md.exists() and claude_md.exists()

        agents_content = agents_md.read_text(encoding="utf-8")
        claude_content = claude_md.read_text(encoding="utf-8")

        assert "docs/principles.md" in agents_content, "AGENTS.md must cite docs/principles.md"
        assert "docs/principles.md" in claude_content, "CLAUDE.md must cite docs/principles.md"

    def test_required_github_workflows_present(self) -> None:
        """Verify all mandatory GitHub Actions CI/CD workflows exist."""
        required_workflows = [
            "ci.yml",
            "required-aggregator.yml",
            "pages.yml",
            "release-matrix.yml",
            "release-please.yml",
            "scorecard.yml",
            "security-scans.yml",
            "supply-chain.yml",
            "pr-project-gate.yml",
            "codeql.yml",
        ]
        for wf_name in required_workflows:
            wf_file = WORKFLOWS_DIR / wf_name
            assert wf_file.exists(), f"Mandatory workflow missing: {wf_name}"
            assert wf_file.stat().st_size > 0, f"Workflow is empty: {wf_name}"

    def test_audit_repository_health_script_executable(self) -> None:
        """Verify audit-repository-health.sh is present and executable."""
        audit_script = REPO_ROOT / "scripts" / "audit-repository-health.sh"
        assert audit_script.exists(), "scripts/audit-repository-health.sh missing"
        if os.name == "nt":
            res = subprocess.run(
                ["git", "ls-files", "-s", "scripts/audit-repository-health.sh"],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                check=False,
            )
            assert res.stdout.startswith("100755"), "scripts/audit-repository-health.sh not executable in git"
        else:
            assert audit_script.stat().st_mode & 0o111, "scripts/audit-repository-health.sh not executable"
