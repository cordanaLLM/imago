# ADR 0001: Centralized Declarative Version Manifest (`versions.json`)

## Status

Accepted

## Context

Originally, component versions (Kubernetes binaries, container image tags, driver branches) were hardcoded in multiple provisioner scripts and Packer variable files. Version bumps required searching and updating dozens of files, risking version drift and breaking automated updates.

## Decision

We consolidate all versions into a single root [`versions.json`](https://github.com/cordanaLLM/imago/blob/main/versions.json) file:

1. Packer decodes the file natively using `jsondecode(file("${path.root}/../versions.json"))`.
2. Packer injects versions dynamically into shell provisioners via `environment_vars`.
3. Provisioners never hardcode version strings or tags.
4. Renovate monitors `versions.json` to open automated pull requests updating only that file.
5. Pytest asserts zero hardcoded version strings exist in provisioners.

## Consequences

- Single location to inspect or bump any upstream dependency.
- Automated tools (Renovate) update dependencies with minimal diff footprint.
