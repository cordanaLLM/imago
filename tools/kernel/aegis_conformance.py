#!/usr/bin/env python3
# Copyright 2026 Lusoris
# SPDX-License-Identifier: EUPL-1.2
"""Build the kernel-requirement conformance corpus and record the owner's verdicts (issue #48).

cordanaLLM/Aegis-OS owns the schema aegis.p01-nucleus.kernel-requirement.v1, and imago's
decoder of that schema must accept and refuse exactly what the owner's decoder does
(ADR-0030). This tool derives one row per rule from the vendored owner payload
pkg/kernel/testdata/aegis/kernel-requirement.json: each row is a one-field edit, a bound
and the value just past it, or a raw text the JSON layer must refuse.

  --decoder BIN  runs the owner's decoder on every row and writes the corpus with its
                 verdicts to pkg/kernel/testdata/aegis/conformance.json. BIN is the
                 decode_req example of the Aegis-OS crate aegis-fabrica-defs, built at
                 the commit named by --aegis-commit; it prints "<path>: accepted" or
                 "<path>: refused: <reason>" for each path.
  --check        exits 1 when the committed corpus differs from the rows built here in a
                 name or a text, so a changed row cannot keep a stale owner verdict.

pkg/kernel/conformance_test.go replays the committed verdicts against imago's decoder, and
tests/test_kernel_conformance.py replays them against the vendored JSON Schema.
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
VENDOR = ROOT / "pkg" / "kernel" / "testdata" / "aegis"
BASE = VENDOR / "kernel-requirement.json"
CORPUS = VENDOR / "conformance.json"
MAX_PAYLOAD_BYTES = 16384
DECODER_TIMEOUT_SECONDS = 60
DIGEST = "ab" * 32

Mutation = Callable[[dict], None]


def setter(path: tuple[str, ...], value: object) -> Mutation:
    """Return a mutation that sets the nested key at path to value."""

    def apply(doc: dict) -> None:
        target = doc
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return apply


def remover(path: tuple[str, ...]) -> Mutation:
    """Return a mutation that deletes the nested key at path."""

    def apply(doc: dict) -> None:
        target = doc
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]

    return apply


def feature_setter(field: str, value: object) -> Mutation:
    """Return a mutation that sets one field of the first feature row."""
    return lambda doc: doc["features"][0].__setitem__(field, value)


def abi(minimum: object, target: object = None) -> Mutation:
    """Return a mutation that replaces the ABI block; a None target is left out."""
    block = {"minimum-release": minimum}
    if target is not None:
        block["target-release"] = target
    return setter(("abi",), block)


def features(count: int) -> Mutation:
    """Return a mutation that replaces the features with count distinct rows."""
    rows = [
        {"symbol": f"CONFIG_F_{i}", "state": "built-in", "probe": "kernel-config", "required-by": "REQ-X"}
        for i in range(count)
    ]
    return setter(("features",), rows)


def duplicate_symbol(doc: dict) -> None:
    doc["features"].append(copy.deepcopy(doc["features"][0]))


MUTATIONS: list[tuple[str, Mutation | None]] = [
    ("owner-payload-as-vendored", None),
    ("state-present", feature_setter("state", "present")),
    ("state-absent", feature_setter("state", "absent")),
    ("state-unknown", feature_setter("state", "y")),
    ("probe-unknown", feature_setter("probe", "dmesg")),
    ("artifact-digest", setter(("artifact",), {"digest": DIGEST})),
    ("artifact-digest-and-signature", setter(("artifact",), {"digest": DIGEST, "signature": "0a1b"})),
    ("artifact-null", setter(("artifact",), None)),
    ("artifact-signature-odd-length", setter(("artifact",), {"digest": DIGEST, "signature": "0a1"})),
    ("artifact-signature-257-chars", setter(("artifact",), {"digest": DIGEST, "signature": "a" * 257})),
    ("artifact-signature-256-chars", setter(("artifact",), {"digest": DIGEST, "signature": "a" * 256})),
    ("artifact-digest-uppercase", setter(("artifact",), {"digest": DIGEST.upper()})),
    ("artifact-digest-63-chars", setter(("artifact",), {"digest": DIGEST[:63]})),
    ("artifact-without-digest", setter(("artifact",), {"signature": "0a1b"})),
    ("artifact-unknown-field", setter(("artifact",), {"digest": DIGEST, "size": 1})),
    ("correlation-id-colon", setter(("correlation-id",), "imago:kernel:0001")),
    ("correlation-id-space", setter(("correlation-id",), "imago kernel")),
    ("correlation-id-non-ascii", setter(("correlation-id",), "imago-kérnel")),
    ("correlation-id-empty", setter(("correlation-id",), "")),
    ("correlation-id-null", setter(("correlation-id",), None)),
    ("correlation-id-128-bytes", setter(("correlation-id",), "c" * 128)),
    ("correlation-id-129-bytes", setter(("correlation-id",), "c" * 129)),
    ("schema-v2", setter(("schema",), "aegis.p01-nucleus.kernel-requirement.v2")),
    ("schema-missing", remover(("schema",))),
    ("minimum-release-rc", abi("7.3-rc2", "7.3")),
    ("minimum-release-single-component", abi("7")),
    ("minimum-release-letter-first", abi("v7.3")),
    ("minimum-release-empty", abi("")),
    ("minimum-release-64-bytes", abi("6.12-" + "a" * 59)),
    ("minimum-release-65-bytes", abi("6.12-" + "a" * 60)),
    ("minimum-release-missing", setter(("abi",), {"target-release": "7.3"})),
    ("target-release-null", abi("6.12", None)),
    ("target-release-empty", abi("6.12", "")),
    ("target-release-below-minimum", abi("7.2", "6.18")),
    ("target-release-equal-minimum", abi("7.2", "7.2")),
    ("target-release-missing-component-is-zero", abi("7.2.0", "7.2")),
    ("target-release-below-three-components", abi("7.3", "7.2.4")),
    ("target-release-suffix-not-ordered", abi("7.2.4-2", "7.2.4-1")),
    ("module-abi-null", setter(("abi", "module-abi"), None)),
    ("module-abi-cachyos", setter(("abi", "module-abi"), "7.2.4-1-cachyos")),
    ("module-abi-letter-first", setter(("abi", "module-abi"), "cachyos")),
    ("abi-unknown-field", setter(("abi", "kabi"), "1")),
    ("abi-null", setter(("abi",), None)),
    ("required-by-flavor", feature_setter("required-by", "FLAVOR-BASE")),
    ("required-by-128-bytes", feature_setter("required-by", "R" * 128)),
    ("required-by-129-bytes", feature_setter("required-by", "R" * 129)),
    ("required-by-bare-prefix", feature_setter("required-by", "REQ-")),
    ("required-by-lowercase", feature_setter("required-by", "req-x")),
    ("required-by-digit-first", feature_setter("required-by", "1ABC")),
    ("required-by-underscore", feature_setter("required-by", "FLAVOR_BASE")),
    ("required-by-dot", feature_setter("required-by", "FLAVOR.BASE")),
    ("architectures-duplicate", setter(("architectures",), ["x86-64", "x86-64"])),
    ("architectures-arm64", setter(("architectures",), ["arm64"])),
    ("architectures-four", setter(("architectures",), ["x86-64", "arm64", "x86-64", "arm64"])),
    ("architectures-five", setter(("architectures",), ["x86-64", "arm64", "x86-64", "arm64", "x86-64"])),
    ("architectures-empty", setter(("architectures",), [])),
    ("architectures-riscv64", setter(("architectures",), ["riscv64"])),
    ("architectures-underscore", setter(("architectures",), ["x86_64"])),
    ("architectures-uppercase", setter(("architectures",), ["X86-64"])),
    ("features-64", features(64)),
    ("features-65", features(65)),
    ("features-empty", setter(("features",), [])),
    ("features-null", setter(("features",), None)),
    ("features-null-row", setter(("features",), [None])),
    ("feature-unknown-field", feature_setter("note", "x")),
    ("symbol-64-bytes", feature_setter("symbol", "CONFIG_" + "A" * 57)),
    ("symbol-65-bytes", feature_setter("symbol", "CONFIG_" + "A" * 58)),
    ("symbol-prefix-only", feature_setter("symbol", "CONFIG_")),
    ("symbol-lowercase", feature_setter("symbol", "CONFIG_kvm")),
    ("symbol-without-prefix", feature_setter("symbol", "KVM")),
    ("symbol-duplicate", duplicate_symbol),
    ("unknown-top-level-field", setter(("extra",), 1)),
]


def render(doc: object) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def raw_rows(base_text: str) -> list[tuple[str, str]]:
    """Return the rows only a raw text can express: JSON-layer refusals and the byte bound."""
    compact = json.dumps(json.loads(base_text), separators=(",", ":"))
    body = compact[1:]
    schema = json.dumps(json.loads(base_text)["schema"])
    padded = compact + " " * (MAX_PAYLOAD_BYTES - len(compact.encode()))
    return [
        ("duplicate-key-schema", '{"schema":' + schema + "," + body),
        ("key-case-differs", compact.replace('"schema":', '"Schema":', 1)),
        ("trailing-document", compact + " {}"),
        ("trailing-whitespace", compact + "\n\n"),
        ("top-level-array", "[" + compact + "]"),
        ("top-level-null", "null"),
        ("payload-16384-bytes", padded),
        ("payload-16385-bytes", padded + " "),
    ]


def build_rows() -> list[dict[str, str]]:
    base_text = BASE.read_text(encoding="utf-8")
    base = json.loads(base_text)
    rows = []
    for name, mutate in MUTATIONS:
        doc = copy.deepcopy(base)
        if mutate is not None:
            mutate(doc)
        rows.append({"name": name, "text": render(doc)})
    rows.extend({"name": name, "text": text} for name, text in raw_rows(base_text))
    return rows


def verdicts(decoder: Path, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Run the owner's decoder on every row and attach its verdict and reason."""
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for index, row in enumerate(rows):
            path = Path(tmp) / f"{index:03d}.json"
            path.write_text(row["text"], encoding="utf-8")
            paths.append(str(path))
        result = subprocess.run(
            [str(decoder), *paths], capture_output=True, text=True, check=True, timeout=DECODER_TIMEOUT_SECONDS
        )
    lines = result.stdout.splitlines()
    if len(lines) != len(rows):
        raise SystemExit(f"decoder printed {len(lines)} lines for {len(rows)} rows")
    out = []
    for row, path, line in zip(rows, paths, lines, strict=True):
        verdict = line.removeprefix(path + ": ")
        if verdict == "accepted":
            out.append({"name": row["name"], "owner": "accepted", "reason": "", "text": row["text"]})
        elif verdict.startswith("refused: "):
            reason = verdict.removeprefix("refused: ")
            out.append({"name": row["name"], "owner": "refused", "reason": reason, "text": row["text"]})
        else:
            raise SystemExit(f"unreadable decoder line: {line}")
    return out


def check() -> int:
    committed = json.loads(CORPUS.read_text(encoding="utf-8"))["rows"]
    want = [(row["name"], row["text"]) for row in build_rows()]
    have = [(row["name"], row["text"]) for row in committed]
    if want == have:
        print(f"conformance corpus matches: {len(want)} rows")
        return 0
    drifted = sorted(
        {name for name, _ in want} ^ {name for name, _ in have}
        | {w[0] for w, h in zip(want, have, strict=False) if w != h}
    )
    print(f"conformance corpus differs from the rows built here: {drifted}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--decoder", type=Path, help="owner decoder binary (decode_req example)")
    group.add_argument("--check", action="store_true", help="compare the committed corpus with the rows")
    parser.add_argument("--aegis-commit", help="full Aegis-OS commit the decoder was built at")
    args = parser.parse_args()
    if args.check:
        return check()
    if not args.aegis_commit:
        parser.error("--decoder needs --aegis-commit")
    corpus = {
        "schema": "imago.kernel-requirement-conformance.v1",
        "aegis-commit": args.aegis_commit,
        "decoder": "aegis_fabrica_defs::kernel::KernelRequirement::decode",
        "rows": verdicts(args.decoder, build_rows()),
    }
    CORPUS.write_text(json.dumps(corpus, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(corpus['rows'])} rows to {CORPUS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
