"""Automated verification suite for repository governance and project standards.

Validates presence of core governance contracts (AGENTS.md, CLAUDE.md, LICENSE),
semantic versioning format in VERSION, linter and scanner configurations,
and required CI/CD workflows.
Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked assertions.
"""

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKER_DIR = REPO_ROOT / "packer"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
REQUIREMENTS_DIR = REPO_ROOT / ".github" / "requirements"
PIP_INSTALL = re.compile(r"\bpip3?\s+install\b(.*)$")
# The last revision published under Apache-2.0; every later one is EUPL-1.2 (ADR-0023).
APACHE_LAST_REVISION = "44a6bfa"
# Built from two parts so that this file does not carry the header it searches for.
FORMER_LICENCE_HEADER = "Licensed under the " + "Apache License"


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
            REPO_ROOT / ".github" / "requirements" / "test.in",
            REPO_ROOT / ".github" / "requirements" / "test.txt",
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

    def test_release_configuration_names_the_package_and_its_version_file(self) -> None:
        """Verify the release tool releases `imago` and writes the version to VERSION.

        The `simple` release type writes `version.txt` unless `version-file` names another
        file; a file listed under `extra-files` is rewritten only where it carries a marker,
        so a bare VERSION listed there is never updated.
        """
        config = json.loads((REPO_ROOT / "release-please-config.json").read_text(encoding="utf-8"))
        package = config["packages"]["."]
        assert package["release-type"] == "simple"
        assert package["package-name"] == "imago", "The released package is named imago"
        assert package.get("version-file") == "VERSION", "VERSION must be the version file"
        assert "VERSION" not in package.get("extra-files", []), (
            "VERSION carries no marker, so listing it under extra-files updates nothing"
        )

    def test_release_manifest_agrees_with_version_or_declares_the_first_one(self) -> None:
        """Verify the manifest holds the released version, or the first version is declared.

        Without a manifest entry the release tool takes `initial-version`; with one it bumps
        from that entry, which then has to be the version the VERSION file states.
        """
        config = json.loads((REPO_ROOT / "release-please-config.json").read_text(encoding="utf-8"))
        manifest = json.loads((REPO_ROOT / ".release-please-manifest.json").read_text(encoding="utf-8"))
        released = manifest.get(".")
        if released is None:
            first = config["packages"]["."].get("initial-version", "")
            assert re.match(r"^\d+\.\d+\.\d+$", first), (
                "No version is released yet, so initial-version must state the first one"
            )
            return
        version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        assert released == version, f"The manifest says {released} was released, VERSION says {version}"

    def test_cli_version_constant_follows_the_version_file(self) -> None:
        """Verify the version the CLI advertises is the released one and stays so.

        The constant is a second copy of VERSION. The release tool rewrites it only when
        the file is listed under `extra-files` and the line carries the marker.
        """
        config = json.loads((REPO_ROOT / "release-please-config.json").read_text(encoding="utf-8"))
        source = (REPO_ROOT / "cmd" / "imago" / "main.go").read_text(encoding="utf-8")
        match = re.search(r"^const version = \"([^\"]+)\"(.*)$", source, re.MULTILINE)
        assert match, "cmd/imago/main.go must declare the version constant"
        version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        assert match.group(1) == version, f"The CLI advertises {match.group(1)}, VERSION says {version}"
        assert "x-release-please-version" in match.group(2), (
            "Without the marker on its line the release tool leaves the constant unchanged"
        )
        assert "cmd/imago/main.go" in config["packages"]["."].get("extra-files", []), (
            "The release tool rewrites the constant only in a file listed under extra-files"
        )

    def test_license_terms_and_copyright(self) -> None:
        """Verify LICENSE holds the EUPL-1.2 text and README/mkdocs state licence, boundary and copyright."""
        license_path = REPO_ROOT / "LICENSE"
        assert license_path.is_file(), "LICENSE file is missing"
        assert not license_path.is_symlink(), "LICENSE must be a regular file, not a link"
        content = license_path.read_text(encoding="utf-8")
        assert "EUROPEAN UNION PUBLIC LICENCE v. 1.2" in content, "LICENSE does not hold the EUPL-1.2 text"
        declared = (REPO_ROOT / "LICENSES" / "EUPL-1.2.txt").read_text(encoding="utf-8")
        assert content == declared, "LICENSE differs from LICENSES/EUPL-1.2.txt"

        readme_content = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        assert "Lusoris Authors" in readme_content, "Missing Lusoris copyright in README.md"
        for needed in ("## License", "EUPL-1.2", "Apache-2.0", APACHE_LAST_REVISION):
            assert needed in readme_content, f"README.md licence section does not name {needed}"

        mkdocs_lines = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8").splitlines()
        copyright_lines = [line for line in mkdocs_lines if line.startswith("copyright:")]
        assert len(copyright_lines) == 1, "mkdocs.yml needs exactly one copyright line"
        assert "The Lusoris Authors" in copyright_lines[0], "Missing Lusoris copyright in mkdocs.yml"
        assert "EUPL-1.2" in copyright_lines[0], "The mkdocs.yml copyright line does not name the licence"

    def test_no_source_header_names_the_former_licence(self) -> None:
        """A tracked source file must not carry the Apache-2.0 header the tree had before ADR-0023."""
        listed = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "-z", "*.py", "*.sh", "*.go", "*.hcl", "*.mjs"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        paths = [rel for rel in listed.stdout.split("\0") if rel]
        assert len(paths) > 50, f"git ls-files listed only {len(paths)} source files"
        stale = [
            rel
            for rel in paths
            if FORMER_LICENCE_HEADER in (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        ]
        assert stale == [], f"These files still carry the former licence header: {stale}"

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

    def test_workflow_pip_installs_use_a_hash_lock(self) -> None:
        """Verify every pip install in a workflow installs only from a hash lock.

        pip checks the hashes only under `--require-hashes`; a package named on the
        command line, or a requirement file outside the lock directory, is unpinned.
        """
        installs = []
        for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
            for number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), 1):
                match = PIP_INSTALL.search(line)
                if match:
                    installs.append((f"{workflow.name}:{number}", match.group(1).split()))
        assert installs, "No pip install line was found, so the pattern no longer matches"
        for where, arguments in installs:
            assert "--require-hashes" in arguments, f"{where}: pip install without --require-hashes"
            sources = [argument for argument in arguments if not argument.startswith("-")]
            assert sources, f"{where}: pip install names no requirement file"
            for source in sources:
                lock = REPO_ROOT / source
                assert lock.parent == REQUIREMENTS_DIR and lock.suffix == ".txt", (
                    f"{where}: {source} is not a lock under .github/requirements"
                )
                assert lock.is_file(), f"{where}: {source} does not exist"

    def test_hash_locks_state_a_compile_command_the_update_bot_can_run(self) -> None:
        """Verify each lock header names its input and writes option values with `=`.

        Renovate recompiles a lock by running the command in its header. It refuses
        `--python-version 3.12` and `--output-file <path>` written with a space, and
        then extracts no dependency from that lock.
        """
        locks = sorted(REQUIREMENTS_DIR.glob("*.txt"))
        inputs = sorted(REQUIREMENTS_DIR.glob("*.in"))
        assert locks, "No lock was found under .github/requirements"
        assert [lock.stem for lock in locks] == [source.stem for source in inputs], (
            "Every input needs its lock and every lock its input"
        )
        for lock in locks:
            relative = lock.relative_to(REPO_ROOT).as_posix()
            command = lock.read_text(encoding="utf-8").splitlines()[1].lstrip("# ").split()
            assert command[:3] == ["uv", "pip", "compile"], f"{relative}: header is not a compile command"
            assert "--generate-hashes" in command, f"{relative}: compiled without --generate-hashes"
            assert relative[: -len(".txt")] + ".in" in command, f"{relative}: header names another input"
            assert f"--output-file={relative}" in command, f"{relative}: --output-file must use '='"
            versions = [option for option in command if option.startswith("--python-version")]
            assert versions and all("=" in option for option in versions), f"{relative}: --python-version must use '='"

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
