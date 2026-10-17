# 31. Fail-Closed Build Dispatch

Date: 2026-10-17

## Status

Accepted. Narrows the execution step of [ADR-0015](0015-progressive-agent-skills-and-staged-mcp-operations.md): staging and confirmation stay, a confirmed build now reports that no executor exists.

## Context

Issue [#55](https://github.com/cordanaLLM/imago/issues/55): `builder.Dispatch` returned a successful result for all nine backends (`local`, `gitea`, `proxmox`, `gitlab`, `woodpecker`, `harbor`, `minio`, `jenkins`, `github`) without invoking Packer or a remote API. It built a job id from the clock and formatted an artifact URL. `imago build` printed that result, and the MCP tools `trigger_build` and `confirm_action` returned it, so a confirmed request read as proof that a build had run. A dry run also reported `success: true` with a trigger timestamp.

## Decision

1. **Every request is validated first.** `builder.Validate` refuses an unknown flavor or backend in both modes; a cancelled context ends the request before validation.
2. **A request without dry run fails until an executor exists.** `Dispatch` returns `*builder.BackendUnavailableError`, which names the backend and matches `builder.ErrBackendUnavailable` under `errors.Is`. The result has `status: "unavailable"` and `success: false`. No I/O is performed.
3. **A dry run reports a plan, not a success.** The result has `status: "planned"`, `dry_run: true` and `success: false`, and its message says that no build was executed.
4. **`success` means a backend acknowledged an execution.** Fields that only an execution can fill are removed: `Result.TriggeredAt`, `Result.PipelineID` and `Result.ArtifactURL`. `Request.Clock` and `mcp.Deps.Clock` go with them, since nothing reads a clock any more.
5. **Adapters pass the refusal on.** `imago build` exits 1 with the error and prints no build line. `trigger_build` with `confirmed=true` and `confirm_action` on a staged build both return a tool error naming the missing executor; the staged action is consumed, so a second confirmation is refused as before.
6. **A future executor must carry evidence.** An executor added for a backend reports success only from what its backend returned (a job id, a run URL, an artifact digest), and adds those fields with it. Validation and confirmation never stand in for that evidence.

## Consequences

- Automation that called `Dispatch`, `imago build` or `trigger_build` without dry run now gets an error where it used to get a fabricated success; a dry-run consumer must read `status` instead of `success`.
- Every backend is a planted false-success case: `pkg/builder/builder_test.go`, `pkg/mcp/build_test.go` (confirmed and staged paths) and `cmd/imago/main_test.go` each fail if any backend reports success or carries a timestamp, job id or artifact URL.
- Images are still built by the `make build-<flavor>` targets and the release workflow; this decision changes neither, nor any credential, endpoint or deployment setting.
