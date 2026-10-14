# 28. One Reason Bound for Every Contract Parser

Date: 2026-10-14

## Status

Accepted. Amends [ADR-0020](0020-aegis-product-input-contract-acceptance.md) point 3 and [ADR-0021](0021-pinned-kernel-artifact-contract-with-nucleus.md) decision 1.

## Context

`pkg/aegis` bounds the reason of a rejection since pull request #71: a reason built from decoder or I/O error text is cut to the exported `aegis.MaxReasonLen` (256 bytes) and ends with a space and `(truncated)`. ADR-0020 does not record that bound, and the review of #71 asked for a decision record before the constant becomes part of the public surface.

The two parsers of `pkg/kernel` had no bound. `ParseRequirement` and `ParseArtifactManifest` returned the text of `encoding/json` unchanged, so a document with a 5000-byte unknown field name produced an error of more than 5000 bytes. `LoadRequirement` and `LoadArtifactManifest` repeated the caller's path. The correlation prefix of ADR-0021 (`<stream>@<version>` for the manifest, the correlation id for the requirement) echoed the raw value even when that value had failed its own check, so a 4000-byte stream reached the log line in full.

## Decision

1. **One bound.** `pkg/reason` holds the bound for every contract parser: `reason.MaxLen` = 256 bytes and `reason.Bound`, which keeps a text of at most `MaxLen` bytes unchanged and otherwise cuts it to `MaxLen` bytes ending with `reason.TruncatedMark`, which is a space followed by `(truncated)`. The cut never splits a UTF-8 character. A new parser calls `reason.Bound` instead of carrying its own copy (HISS-19).
2. **`aegis.MaxReasonLen` stays exported and equals `reason.MaxLen`.** It is the bound ADR-0020 point 3 applies to `Error.Reason`; the cause in `Error.Err` is unchanged.
3. **Every error an exported function of `pkg/kernel` returns is bounded.** The text is cut by `reason.Bound`; the full cause stays in the chain, so `errors.Is` and `errors.As` reach `ErrEmptyRequirement`, `ErrTooLarge`, `fs.ErrNotExist` and the verification sentinels as before.
4. **A correlation value that failed its check is not echoed.** In the prefix of a `pkg/kernel` error, an empty correlation id, stream or version reads `(missing)` and one that fails its own check reads `(invalid)`, the placeholders ADR-0020 already uses for `pkg/aegis`. A manifest with neither stream nor version keeps the field-only form.
5. **Tests hold the bound.** `pkg/reason/reason_test.go` checks the boundary at `MaxLen` and `MaxLen + 1` and a cut inside a multi-byte character. `pkg/kernel/reason_test.go` checks long unknown fields, long paths, invalid correlation values and the kept sentinels. `FuzzParseRequirement` and `FuzzParseArtifactManifest` fail on any error text longer than `reason.MaxLen`.

## Consequences

- **Positive**: no rejection text of either contract grows with the input, and no value that failed validation reaches a log line.
- **Positive**: one implementation of the cut; the aegis and kernel bounds cannot drift apart.
- **Negative**: an error longer than 256 bytes loses its tail in the text. The cause in the chain keeps the full detail for a caller that needs it.
- **Neutral**: callers that matched on the raw correlation prefix of an invalid value see the placeholder instead; no caller in this repository does.

## References

- [ADR-0020](0020-aegis-product-input-contract-acceptance.md): the aegis error shape and its placeholders; the bound is added by point 2.
- [ADR-0021](0021-pinned-kernel-artifact-contract-with-nucleus.md): the kernel contract whose correlated errors are bounded by points 3 and 4.
- `pkg/reason/reason.go`, `pkg/kernel/decode.go`: the bound and its use in the kernel package.
