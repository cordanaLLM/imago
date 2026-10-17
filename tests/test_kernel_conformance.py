# Copyright 2026 Lusoris
"""Verification that the vendored Aegis-OS schema and the conformance corpus agree (issue #48).

pkg/kernel/testdata/aegis/conformance.json records, row by row, whether the decoder of the
schema owner, cordanaLLM/Aegis-OS, accepts or refuses a kernel-requirement payload at the
commit ADR-0030 pins. pkg/kernel/conformance_test.go replays those verdicts against imago's
Go decoder. The tests below replay them against the JSON Schema the owner publishes next to
its decoder, vendored as kernel-requirement.schema.json, and hold the corpus to the rows that
tools/kernel/aegis_conformance.py builds, so a row cannot change while it keeps a stale
verdict.

A JSON Schema cannot express every rule of the owner's decoder. Each row where the schema
accepts what the owner refuses is listed in BEYOND_SCHEMA with the rule it cannot express;
a listed row the schema starts to refuse fails as a stale entry.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parent.parent
AEGIS = ROOT / "pkg" / "kernel" / "testdata" / "aegis"
CORPUS = AEGIS / "conformance.json"
SCHEMA = AEGIS / "kernel-requirement.schema.json"
TOOL = ROOT / "tools" / "kernel" / "aegis_conformance.py"
PINNED_COMMIT = "e915c654e6c1e497c976c02ae977067516575552"

BEYOND_SCHEMA = {
    "target-release-below-minimum": "the target release is ordered against the minimum release",
    "target-release-below-three-components": "the target release is ordered against the minimum release",
    "symbol-duplicate": "symbols are distinct across rows; uniqueItems compares whole rows",
    "duplicate-key-schema": "a duplicate member is refused by the decoder; a JSON reader keeps one of them",
    "payload-16385-bytes": "the payload bound counts bytes of text, not a property of the value",
}


def load_tool():
    spec = importlib.util.spec_from_file_location("aegis_conformance", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def corpus() -> dict:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def schema_validator(schema: dict) -> jsonschema.protocols.Validator:
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


def schema_verdict(validator, text: str) -> str:
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return "refused"
    return "accepted" if validator.is_valid(document) else "refused"


def disagreements(schema: dict) -> dict[str, str]:
    validator = schema_validator(schema)
    return {
        row["name"]: row["owner"] for row in corpus()["rows"] if schema_verdict(validator, row["text"]) != row["owner"]
    }


def test_corpus_names_the_pinned_owner_commit() -> None:
    assert corpus()["aegis-commit"] == PINNED_COMMIT


def test_corpus_matches_the_rows_the_tool_builds() -> None:
    assert load_tool().check() == 0


def test_a_changed_row_text_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    planted = corpus()
    planted["rows"][1]["text"] = planted["rows"][1]["text"].replace("x86-64", "arm64", 1)
    path = tmp_path / "conformance.json"
    path.write_text(json.dumps(planted), encoding="utf-8")
    tool = load_tool()
    monkeypatch.setattr(tool, "CORPUS", path)
    assert tool.check() == 1


def test_vendored_schema_agrees_with_the_owner_on_every_other_row() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    differ = disagreements(schema)
    unlisted = {name: owner for name, owner in differ.items() if name not in BEYOND_SCHEMA}
    assert not unlisted, f"schema and owner disagree on rows not listed in BEYOND_SCHEMA: {unlisted}"
    stale = sorted(set(BEYOND_SCHEMA) - set(differ))
    assert not stale, f"BEYOND_SCHEMA lists rows the schema now decides like the owner: {stale}"
    assert all(differ[name] == "refused" for name in BEYOND_SCHEMA)


def test_a_schema_that_admits_any_architecture_is_refused() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    planted = copy.deepcopy(schema)
    planted["$defs"]["Architecture"] = {"type": "string"}
    unlisted = set(disagreements(planted)) - set(BEYOND_SCHEMA)
    assert "architectures-riscv64" in unlisted


def test_owner_rows_cover_both_verdicts() -> None:
    owners = [row["owner"] for row in corpus()["rows"]]
    assert owners.count("accepted") >= 20
    assert owners.count("refused") >= 40
