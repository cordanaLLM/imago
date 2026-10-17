# 30. The Kernel Requirement Decoder Follows the Schema Owner

Date: 2026-10-17

## Status

Accepted. Supersedes decision 4 of [ADR-0021](0021-pinned-kernel-artifact-contract-with-nucleus.md).

## Context

`cordanaLLM/Aegis-OS` owns the schema `aegis.p01-nucleus.kernel-requirement.v1`. Its decoder is `KernelRequirement::decode` in the crate `aegis-fabrica-defs`, and it publishes a JSON Schema of the payload as `build/kernel-requirement.schema.json`. imago writes its own requirement in that shape (`kernel/requirement.json`) and `nucleus` reads both.

ADR-0021 decision 4 gave imago its own set of bounds, written before the owner had fixed its rules. Issue [#48](https://github.com/cordanaLLM/imago/issues/48) records the result: the two decoders disagreed on 30 of the 80 rows that `tools/kernel/aegis_conformance.py` builds from the owner's payload.

- imago refused what the owner accepts: the states `present` and `absent`, the optional `artifact` object, a `:` in the correlation id, a release such as `7` or `7.3-rc2`, a `required-by` of up to 128 characters, a repeated architecture, and four architectures.
- imago accepted what the owner refuses: a target release older than the minimum or empty, `riscv64` or any other architecture outside `x86-64` and `arm64`, a lowercase or digit-first `required-by` and the bare prefix `REQ-`, 65 features, a 65-byte symbol, a member named twice or in another case, and a payload above 16384 bytes.

A requirement imago validated could therefore be refused by `nucleus`, and the reverse.

Aegis-OS decision D103 (2026-09-29) made `required-by` schema-generic: any identifier of an upper-case letter followed by upper-case letters, digits and `-`. imago's flavor-tier ids such as `FLAVOR-K8S-NODE` are valid under it.

## Decision

1. **The owner's decoder at Aegis-OS commit `e915c654e6c1e497c976c02ae977067516575552` is the reference.** `pkg/kernel` accepts and refuses exactly what it does. The bounds, character sets and allow-lists in `pkg/kernel/requirement.go` are the owner's: payload of at most 16384 bytes; correlation id of 1..128 characters of `[A-Za-z0-9._:-]`; 1..4 architectures from `x86-64` and `arm64`, repeats allowed; releases of 1..64 characters of `[0-9A-Za-z._+-]` starting with a digit; `target-release` and `module-abi` absent, `null`, or a release, never empty; a target release not older than the minimum, compared on the leading dotted numeric components like the owner; 1..64 features with distinct symbols of at most 64 bytes; the states `built-in`, `module`, `present` and `absent`; `required-by` of 1..128 characters as D103 defines it, but not `REQ-` alone; and an optional top-level `artifact` with a 64-character lowercase hex `digest` and an optional `signature` of up to 256 lowercase hex characters of even length.
2. **Strict decoding refuses what the owner's JSON layer refuses.** `decodeStrict` decodes with `encoding/json/v2`, which matches member names case-sensitively and refuses a duplicate member; it also refuses unknown members, a second document and an oversized payload. The kernel artifact manifest of ADR-0021 decision 1 shares this decoder and is decoded the same way.
3. **imago keeps its flavor-tier ids.** `kernel/requirement.json` keeps `required-by` ids of the form `FLAVOR-<TIER>`. `TestRepositoryRequirementDecodes` holds them to that prefix.
4. **The owner's files are vendored at the pinned commit.** `pkg/kernel/testdata/aegis/` holds the owner's payload, its reference payload and its JSON Schema, copied byte for byte from `build/` at the pinned commit, under the owner's EUPL-1.2 notice (`REUSE.toml`).
5. **Agreement is held by a recorded corpus.** `tools/kernel/aegis_conformance.py` builds 80 rows from the vendored payload: one-field edits, each bound and the value just past it, and raw texts the JSON layer must refuse. Run with `--decoder`, it records the owner's verdict on every row in `pkg/kernel/testdata/aegis/conformance.json`, together with the commit. `pkg/kernel/conformance_test.go` replays every verdict against the Go decoder. `tests/test_kernel_conformance.py` replays them against the vendored schema, lists the five rows a JSON Schema cannot decide with the rule each needs, and fails when the corpus differs from the rows the tool builds.
6. **A new owner commit is adopted by regenerating the corpus.** Moving the pin means copying the three files from the new commit, building the owner's decoder there, running the tool with `--decoder` and `--aegis-commit`, and changing the decoder until both replays pass.

## Consequences

- **Positive**: a requirement imago validates is one the owner's decoder accepts, row for row. `imago kernel requirement validate kernel/requirement.json` and the owner's decoder both accept the repository's requirement.
- **Positive**: a change on either side shows as a failing row with the row's name, not as a refusal at `nucleus`.
- **Negative**: the owner's bounds are tighter than imago's were (64 features instead of 512, 4 architectures instead of 8). A requirement that outgrows them needs a change at the owner first.
- **Negative**: the artifact manifest is now decoded case-sensitively and refuses a duplicate member. No producer writes either, but a hand-edited manifest that relied on case-insensitive matching is refused.
- **Neutral**: regenerating the verdicts needs a Rust build of the owner's crate. The replays run offline from the committed corpus.

## References

- [ADR-0021](0021-pinned-kernel-artifact-contract-with-nucleus.md): the kernel artifact contract with `cordanaLLM/nucleus`.
- [ADR-0028](0028-one-reason-bound-for-every-contract-parser.md): the bound on every error text, which the new checks keep.
- Aegis-OS `docs/build/product-input.md` at the pinned commit: decision D103 on `required-by`.
- Fleet answer ledger, ids `imago-48-requirement-schema` and `imago-48-pin-refresh`, 2026-10-17: conform at Aegis-OS `e915c65`, keep the flavor-tier ids, vendor the fixtures and the schema at that commit (paraphrased).
