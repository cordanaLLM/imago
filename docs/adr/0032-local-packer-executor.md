# 32. Local Packer Executor

Date: 2026-10-17

## Status

Accepted. Amends [ADR-0031](0031-fail-closed-build-dispatch.md) decision 2 for `BackendLocal` when an executor is explicitly registered by the CLI. The default dispatcher and MCP retain their refusal.

## Context

Issue [#136](https://github.com/cordanaLLM/imago/issues/136), unit B: Imago (Latin for “image”, pronounced ih-MAH-go) needs a local build path that returns execution evidence. The repository already defines QEMU Packer builds and output paths in `packer/sources.pkr.hcl`, with `output_dir`, `flavor` and `image_name` declared in `packer/variables.pkr.hcl`. A plan or confirmation cannot establish that those builds ran. Unit A supplies the toolchain pins in `versions.json`; the executor must refuse missing pins rather than invent defaults.

The MCP server runs in agent sessions on a shared workstation. Confirmation authorizes an attempt through that interface, but should not start an hour-long KVM workload there. The CLI provides an explicit operator entry point.

## Decision

1. **Registration controls execution.** Add `builder.Executor` and `DispatchWith`; `Dispatch` delegates without executors and preserves `BackendUnavailableError`. The CLI registers `LocalExecutor` only for local requests without dry run. Validation precedes registration and dispatch; dry runs remain plans without success or evidence (`pkg/builder/builder.go`, `cmd/imago/main.go`).
2. **Verify installed tools before building.** `LoadPins` reads the build pins from a selected manifest, rejects missing or malformed required values, and uses an iterative JSON token walk to reject duplicate keys at any depth. Packer's first version line must equal the pinned version; the platform-specific QEMU plugin binary must match its pinned SHA256. Tools are never downloaded by the executor (`pkg/builder/pins.go`, `pkg/builder/local.go`).
3. **Bound execution and retain failures.** `Request.Timeout` defaults to two hours; an earlier caller deadline remains effective. The default runner uses `exec.CommandContext`, cancellation and a bounded `WaitDelay`. Packer builds the selected QEMU flavor with explicit output directory, flavor and image name. Each run writes a UTC-named log without overwriting an existing log. Named sentinel errors preserve process and context causes, including both `ErrBuildTimeout` and `context.DeadlineExceeded` on timeout (`pkg/builder/local.go`).
4. **Success requires artifact evidence.** Only a completed Packer command followed by streaming SHA256 verification of the expected regular QCOW2 file, last written after the build started, yields `status: "succeeded"` and `success: true`. Append `run_log`, `artifact` and `artifact_sha256` to `Result` with `omitempty`; failures retain available log evidence but never success (`pkg/builder/local_test.go`).
5. **MCP keeps refusing execution.** `trigger_build` and `confirm_action` continue to call the default dispatcher for every backend, including local. The local refusal directs the caller to `imago build --backend local`. This keeps long KVM builds out of agent-triggered shared-host work; staging and dry-run behavior remain intact (`pkg/mcp/server.go`, `pkg/mcp/build_test.go`).

## Consequences

- CLI local builds require the installed Packer and plugin pins, matching binaries and the existing QEMU/KVM prerequisites. Other backends keep their typed refusal. `make build-<flavor>` and the release workflow remain separate entry points.
- Fake-runner tests cover success, version/checksum mismatches, missing plugin/artifact, nonzero exit, deadline expiry, a stale artifact left by an earlier run and non-local refusal without invoking Packer or KVM (`pkg/builder/local_test.go`). Manifest fixtures cover missing and duplicate keys (`pkg/builder/pins_test.go`); injected-executor tests cover CLI output and routing (`cmd/imago/build_test.go`).
- The CLI exposes `--packer-dir`, `--output-dir` and `--versions`, with logs beneath the chosen output directory. These paths resolve before Packer changes its working directory; artifact naming is fixed through explicit Packer variables (`docs/tools/cli-mcp.md`, section 2.4).
