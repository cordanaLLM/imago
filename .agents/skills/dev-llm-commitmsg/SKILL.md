---
name: dev-llm-commitmsg
description: Generate strict Conventional Commits messages conforming to the repository contract.
---

# Conventional Commit Message Drafting

All commits in `lusoris-cloud-images` must follow Conventional Commits specification.

## Format
```text
<type>(<scope>): <short summary in present tense>

[optional body explaining context, rationale, or trade-offs]

[optional footer(s), e.g. Closes #123]
```

## Types
- `feat`: New image flavor, builder target, or major feature.
- `fix`: Bug fix in provisioners, templates, CI, or tests.
- `chore`: Maintenance, dependency updates, or toolchain changes.
- `docs`: Documentation updates under `docs/` or `README.md`.
- `refactor`: Code change that neither fixes bug nor adds feature.
- `perf`: Performance improvement in build times or boot latency.
- `ci`: CI/CD workflow updates, GitHub Actions, or security scanner tweaks.

## Scopes
- `forge`: Packer engine, QEMU/Proxmox builders.
- `base`: Base OS stripping, systemd, or kernel tuning.
- `docker`: Docker CE runtime or container toolkits.
- `k8s`: Kubernetes node components (containerd, kubelet, CNI).
- `ai-infer`: AI inference appliances (vLLM, CDI, NUMA tuning).
- `gpu-intel`: Intel Arc / Xe drivers and runtimes.
- `gpu-amd`: AMD Mesa or ROCm 7.2 runtimes.
- `gpu-nvidia`: NVIDIA generational drivers (580, 595, 615).
- `deps`: Dependency bumps in `versions.json`.

## Rules
- Summary line must be $\le$ 72 characters.
- Must be written in English.
- Use imperative mood: "add flavor" not "added flavor".
