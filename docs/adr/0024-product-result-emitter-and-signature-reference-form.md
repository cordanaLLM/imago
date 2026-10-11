# 24. Product-Result Emitter and the Signature Reference Form

Date: 2026-10-11

## Status

Accepted

## Context

[ADR-0020](0020-aegis-product-input-contract-acceptance.md) accepted the Aegis product-input manifest and pinned the shape of the result imago returns, `imago.p01.product-result.v1`. Its decision 5 ends with the statement that nothing produces a result, and it admitted any locator of at most 512 characters as `signature-ref`.

Three facts made that too little:

- **Aegis milestone M11 waits on the form.** Its harness verifies the digest and the signature of the returned image with a pinned cosign before any boot, and it adds the form of `signature-ref` to its pin schema as a second signature scheme. The [Aegis roadmap](https://github.com/cordanaLLM/Aegis-OS/blob/main/docs/roadmap/README.md) states that a scheme added before the form is pinned would guess its contract. Issue #46 tracks the emitter.
- **A locator without a form cannot be verified.** A consumer that reads `signature-ref` has to know what it fetches, which tool verifies it, and which signer it accepts.
- **The fleet already publishes one signature form.** The kernel forge `cordanaLLM/nucleus` releases a `SHA256SUMS` file with a keyless cosign bundle `SHA256SUMS.bundle`, and `.github/workflows/sync-kernel-manifest.yml` verifies it with `cosign verify-blob` against the provider's repository identity and the GitHub Actions issuer ([ADR-0021](0021-pinned-kernel-artifact-contract-with-nucleus.md)).

imago still has no executor that builds the mkosi image the manifest describes. This record decides the form and the emitter. Where the executor runs was decided separately on the same day (answer `imago-46-executor-home` in the references); the executor and its record follow in their own change.

## Decision

1. **The signature is a keyless cosign bundle over a `SHA256SUMS` file that lists the image.** `signature-ref` is the HTTPS URL of that bundle. The checksum file is published at the same URL without the `.bundle` suffix. This is the form nucleus publishes and imago verifies, so the fleet has one signature form for release artefacts.
2. **`Result.Validate` admits one syntax for `signature-ref`.** The rule is an allow-list checked byte by byte, without a regular expression and without a URL parser, so a consumer can mirror it exactly:

   - at most `MaxReferenceLen` (512) bytes, no control character, no backslash, as before;
   - the text starts with `https://` in lower case;
   - the host is the text up to the first `/`: 1..`MaxSignatureHostLen` (253) bytes of `[A-Za-z0-9.-]` that start and end alphanumeric, with no port and no user part;
   - the path is the rest: bytes of `[A-Za-z0-9._~/-]` only, no empty segment, no `.` or `..` segment, therefore no query, no fragment and no percent-encoding;
   - the last path segment is exactly `SHA256SUMS.bundle` (`SignatureBundleFile`).

   A violation is an `*aegis.Error` on the field `signature-ref` with the cause `ErrInvalidField`; the reason names the rule and never repeats the value.
3. **The signer a consumer accepts is this repository's GitHub Actions identity.** The verification is the one imago runs for the kernel release, with imago as the signer:

   ```bash
   cosign verify-blob --bundle SHA256SUMS.bundle \
     --certificate-identity-regexp '^https://github.com/cordanaLLM/imago/' \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     SHA256SUMS
   ```

   After it passes, the consumer checks that `SHA256SUMS` lists the hexadecimal part of `image-digest`. The host of `signature-ref` is not part of the trust decision: the certificate identity is.
4. **Signing happens only inside a GitHub Actions run of this repository.** There is no workstation key and no long-lived key. The emitter does not sign.
5. **The emitter is `aegis.Emit`, exposed as `imago aegis result emit`.** For an accepted request it computes the SHA-256 of the image file with a bounded read (`MaxImageBytes`, 64 GiB), refuses an empty image, requires that the given `SHA256SUMS` lists that digest, and builds the result with the request's correlation id. The checksum file is at most `MaxChecksumsBytes` (1 MiB) and `MaxChecksumLines` (1024) long, and every non-empty line has a form `sha256sum` writes: `<sha256>  <name>` or `<sha256> *<name>`. The name is not compared, because the digest identifies the image. The digest loop reads whole chunks, so a reader that returns short reads is digested whole and stays under the bound. A refusal is an `*aegis.Error` on the field `image`, `checksums` or `image-digest`. `WriteResult` validates before it writes, so an invalid result produces no output.
6. **`imago aegis result validate <path>` is the acceptance check for a consumer.** It decodes a result with the decoder the manifest uses (`strictDecode` in `pkg/aegis/aegis.go`: unknown fields, trailing content and inputs above 1 MiB are refused) and runs `Result.Validate`. The fuzz target `FuzzParseResult` holds that whatever the parser accepts has the form of decision 2, checked by an oracle that shares no code with the validator.
7. **`boot-evidence-ref` keeps the generic bounds of ADR-0020.** Its form depends on where the image boots and is decided with the executor.
8. **This narrows ADR-0020 decision 5 for `signature-ref` only.** ADR-0020 is not rewritten. A value that the earlier `Result.Validate` accepted and this one refuses is a breaking change of an exported function; no result existed, and the one pinned consumer waited for this form.

## Consequences

- **Positive**: Aegis M11 can pin its second signature scheme against a stated form, a stated verification command and a stated signer.
- **Positive**: a consumer proves that imago accepts a result with the pinned imago binary instead of a reimplemented check.
- **Positive**: a result cannot name an image that its signed checksum file does not list, because the emitter computes the digest from the file and compares.
- **Negative**: the emitter does not verify the signature. It never contacts the network and does not run cosign, so a result can name a bundle that does not verify. The consumer's verification in decision 3 decides, and the executor verifies its own bundle before it emits.
- **Negative**: no real result exists yet. The emitter is proven against test files only, and issue #46 stays open until an executor builds, signs and boots an image.
- **Negative**: a bundle behind a port, a percent-encoded path or another file name is refused. Admitting one needs a new record.
- **Neutral**: `aegis.SignatureBundleFile` repeats `kernel.BundleFile`, because `pkg/aegis` imports no other package of this repository. The test `TestSignatureBundleNameMatchesKernelRelease` in `cmd/imago` fails when the two differ.
- **Neutral**: the correlated error text still begins with `aegis product-input`, also for a refused result. The field name tells the two apart; changing the text would change ADR-0020 decision 3.

## References

- Operator decisions of 2026-10-11 in the fleet answer ledger (paraphrased):
  - `imago-46-signature-form`: the signature is a keyless cosign bundle over a checksum file that lists the image; the reference is the HTTPS URL of the bundle; the identity is bound to this repository and the GitHub issuer; signing happens only inside an Actions run; the emitter comes first and the executor is its own decision.
  - `aegis-os-m11-imago-46`: issue #46 is taken before other open units because it blocks Aegis milestone M11.
  - `imago-46-executor-home`: the executor is a workflow of this repository on GitHub-hosted runners that builds at a stated Aegis revision, boots the image once, signs keylessly over `SHA256SUMS` and publishes a pre-release; it is not part of this change.
- Issue #46, the emitter for an accepted product-input request.
- [ADR-0020](0020-aegis-product-input-contract-acceptance.md), decisions 3 and 5; [ADR-0021](0021-pinned-kernel-artifact-contract-with-nucleus.md).
- `.github/workflows/sync-kernel-manifest.yml`, step that runs `cosign verify-blob`.
- `pkg/aegis/result.go`, `pkg/aegis/result_test.go`, `pkg/aegis/fuzz_test.go`, `cmd/imago/main.go`, `cmd/imago/main_test.go`.
