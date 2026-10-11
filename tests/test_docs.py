"""Automated verification suite for documentation and architectural records.

Validates MkDocs navigation tree completeness, ADR Nygard format adherence,
ADR index synchrony, absence of placeholder emails, and CHANGELOG structure.
Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked assertions.
"""

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
MKDOCS_CONFIG = REPO_ROOT / "mkdocs.yml"
ADR_DIR = DOCS_DIR / "adr"
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"


class MkDocsLoader(yaml.SafeLoader):
    """Custom YAML loader ignoring python-specific mkdocs tags."""

    pass


MkDocsLoader.add_multi_constructor("tag:yaml.org,2002:python/", lambda loader, suffix, node: None)


def extract_nav_paths(node):
    """Collect all target documentation file paths from mkdocs nav, in document order."""
    paths = []
    pending = [node]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            pending.extend(reversed(list(current.values())))
        elif isinstance(current, list):
            pending.extend(reversed(current))
        elif isinstance(current, str) and current.endswith(".md"):
            paths.append(current)
    return paths


class TestDocsIntegrity:
    def test_mkdocs_nav_files_exist(self) -> None:
        """Verify every markdown file declared in mkdocs.yml nav exists on disk."""
        assert MKDOCS_CONFIG.exists(), "mkdocs.yml is missing"
        config = yaml.load(MKDOCS_CONFIG.read_text(encoding="utf-8"), Loader=MkDocsLoader)
        nav = config.get("nav", [])
        nav_files = extract_nav_paths(nav)

        assert len(nav_files) >= 15, f"Expected >= 15 nav items, found {len(nav_files)}"
        for rel_file in nav_files:
            file_path = DOCS_DIR / rel_file
            assert file_path.exists(), f"File in mkdocs.yml nav does not exist: {file_path}"
            assert file_path.stat().st_size > 0, f"File in mkdocs.yml nav is empty: {file_path}"

    def test_adr_nygard_format(self) -> None:
        """Verify all ADR files adhere to Nygard structure (Status, Context, Decision, Consequences)."""
        adr_files = sorted(ADR_DIR.glob("0*.md"))
        assert len(adr_files) >= 5, f"Expected at least 5 ADRs, found {len(adr_files)}"

        required_sections = ["## Status", "## Context", "## Decision", "## Consequences"]
        for adr in adr_files:
            content = adr.read_text(encoding="utf-8")
            for sec in required_sections:
                assert sec in content, f"ADR {adr.name} is missing mandatory section '{sec}'"

    def test_adr_index_synchrony(self) -> None:
        """Verify all ADR files are cataloged in docs/adr/README.md."""
        readme = ADR_DIR / "README.md"
        assert readme.exists(), "docs/adr/README.md index is missing"
        index_content = readme.read_text(encoding="utf-8")

        for adr in ADR_DIR.glob("0*.md"):
            assert adr.name in index_content, f"ADR {adr.name} is missing from the table in docs/adr/README.md"

    def test_no_placeholder_emails(self) -> None:
        """Verify documentation contains no fake or placeholder contact email addresses."""
        placeholder_pattern = re.compile(
            r"\b[A-Za-z0-9._%+-]+@(example\.com|example\.org|yourdomain\.com|test\.com|domain\.com)\b",
            re.IGNORECASE,
        )
        for md_file in REPO_ROOT.rglob("*.md"):
            parts = md_file.relative_to(REPO_ROOT).parts
            if ".workingdir" in parts or ".pytest_cache" in parts:
                continue
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            match = placeholder_pattern.search(content)
            assert not match, (
                f"Prohibited placeholder email '{match.group(0)}' found in {md_file.relative_to(REPO_ROOT)}. "
                f"Use GitHub native surfaces exclusively."
            )

    def test_changelog_structure(self) -> None:
        """Verify CHANGELOG.md exists and adheres to Keep a Changelog format."""
        assert CHANGELOG_PATH.exists(), "CHANGELOG.md is missing"
        content = CHANGELOG_PATH.read_text(encoding="utf-8")
        assert "## [Unreleased]" in content, "Missing '## [Unreleased]' section in CHANGELOG.md"
        assert any(sec in content for sec in ["### Added", "### Changed", "### Fixed"]), (
            "CHANGELOG.md missing standard category sections"
        )

    def test_mermaid_diagrams_syntax_and_style(self) -> None:
        """Verify all Mermaid code blocks in documentation have valid diagram types and balanced syntax."""
        mermaid_pattern = re.compile(r"```mermaid\s*\n(.*?)\n```", re.DOTALL)
        valid_prefixes = (
            "flowchart",
            "graph",
            "sequenceDiagram",
            "stateDiagram",
            "stateDiagram-v2",
            "classDiagram",
            "erDiagram",
            "mindmap",
            "timeline",
            "xychart-beta",
        )

        md_files = [
            f
            for f in REPO_ROOT.rglob("*.md")
            if ".workingdir" not in f.relative_to(REPO_ROOT).parts
            and ".pytest_cache" not in f.relative_to(REPO_ROOT).parts
        ]
        total_diagrams = 0

        for md_file in md_files:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            for match in mermaid_pattern.finditer(content):
                total_diagrams += 1
                block = match.group(1).strip()
                lines = [
                    line.strip() for line in block.splitlines() if line.strip() and not line.strip().startswith("%%")
                ]
                assert len(lines) > 0, f"Empty mermaid block in {md_file.relative_to(REPO_ROOT)}"

                first_line = lines[0]
                assert any(first_line.startswith(prefix) for prefix in valid_prefixes), (
                    f"Invalid diagram type '{first_line}' in {md_file.relative_to(REPO_ROOT)}"
                )

                assert block.count("{") == block.count("}"), (
                    f"Unbalanced curly braces in {md_file.relative_to(REPO_ROOT)}"
                )
                assert block.count("[") == block.count("]"), (
                    f"Unbalanced square brackets in {md_file.relative_to(REPO_ROOT)}"
                )

        assert total_diagrams >= 5, f"Expected at least 5 mermaid diagrams in repository, found {total_diagrams}"
