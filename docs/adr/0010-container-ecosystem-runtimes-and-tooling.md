# 10. Modern Container Runtimes, Lazy-Pulling Snapshotters, and Zero-Footprint Diagnostic Tooling

Date: 2026-09-10

## Status

Accepted

## Context

An architectural review of the broader container ecosystem—specifically cataloged in [`pditommaso/awesome-containers`](https://github.com/pditommaso/awesome-containers), [`iximiuz/awesome-container-tinkering`](https://github.com/iximiuz/awesome-container-tinkering), [`ramitsurana/awesome-kubernetes`](https://github.com/ramitsurana/awesome-kubernetes), and [`cloudnativebasel/awesome-cloud-native`](https://github.com/cloudnativebasel/awesome-cloud-native)—identified four critical leverage points to significantly improve container performance, operator ergonomics, and CI validation in `imago`:

1. **OCI Runtime Memory & Startup Overhead**: The standard OCI runtime (`runc`) is written in Go and carries measurable memory (~25MB resident set per process under heavy load) and startup latency. In dense edge environments (`k3s-agent-*`) or large-scale Kubernetes clusters (`k8s-node-*`), switching to an ultra-fast C-based OCI runtime (`crun`) reduces memory usage to ~4MB and speeds up container creation by 2–3x while providing native cgroups v2, Wasm/WASI, and checkpoint/restore capabilities.
2. **Cold-Boot Image Delays for Multi-Gigabyte Workloads**: Cloud-native AI workloads (`ai-infer-*`, Ollama, vLLM, PyTorch, CUDA) ship container images ranging from 5GB to 25GB. Standard containerd pulls 100% of the image before launching the process. Lazy-pulling technologies like `stargz-snapshotter` (eStargz, CNCF) enable instant pod startup ($< 2\text{s}$) by streaming file blocks on-demand over HTTP range requests.
3. **The Minimal Container Debugging Dilemma**: Hardened and distroless production containers lack shells, `curl`, `gdb`, `tcpdump`, or `strace`. Baking diagnostic tools into base images causes severe bloat and security exposure; however, operating without diagnostic tools leaves operators blind during production incidents. Ephemeral container debugger utilities such as `cdebug` (by iximiuz) bridge this gap by attaching an ephemeral debugging container directly to the target container's namespaces without modifying the image.
4. **HPC & AI Unprivileged Sandboxing**: In multi-tenant GPU computing and high-performance computing (HPC), standard Docker/containerd daemons introduce security and filesystem performance penalties. Tools like NVIDIA `enroot` turn container images into unprivileged user-space sandboxes with native driver integration and near-bare-metal I/O.
5. **CI Image Verification Gates**: Validating that built images satisfy security, package, and configuration contracts requires moving beyond static linters to declarative verification tools such as Google's `container-structure-test` and Aqua Security's `trivy`.

## Decision

We adopt a phased modernization program integrating high-leverage container ecosystem technologies into `imago`:

### 1. Dual OCI Runtime Engine (`runc` + `crun`) in Kubernetes & Container Hosts

- In `50-k8s-runtime.sh`, `crun` is installed alongside standard `runc`.
- containerd (`/etc/containerd/config.toml`) is configured with dual runtime classes:
  - Default runtime remains standard `runc` for maximum ecosystem compatibility.
  - An accelerated runtime class `crun` is registered (`runtime_type = "io.containerd.runc.v2"`, `options = { BinaryName = "crun", SystemdCgroup = true }`). Pods can immediately opt-in via Kubernetes manifest: `runtimeClassName: crun`.
- In `41-podman-runtime.sh`, `crun` remains the primary default OCI runtime for rootless and daemonless container execution.

### 2. Zero-Footprint Diagnostic Tooling (`cdebug`)

- `cdebug` is baked into all container host images (`docker-*`, `podman-*`, `k8s-node-*`, `k3s-*`) under `/usr/local/bin/cdebug`.
- Operators can debug any running container or Kubernetes pod without image mutation:

  ```bash
  sudo cdebug exec -it <container-id-or-name>
  sudo cdebug exec -it --image nicolaka/netshoot <container-id-or-name>
  ```

### 3. Declarative Single Source of Truth (`versions.json`) Integration

- All runtime and tool versions are pinned declaratively in `versions.json` and validated by `versions.schema.json`:
  - `runtimes.crun`: `"1.20"`
  - `runtimes.stargz_snapshotter`: `"0.15.1"`
  - `tools.cdebug`: `"0.5.1"`
  - `tools.enroot`: `"3.4.1"`

### 4. Roadmap Integrations (Phase 2)

- **`stargz-snapshotter` Plugin**: In upcoming releases, `stargz-snapshotter` will be integrated into `50-k8s-runtime.sh` and `60-ai-infer-runtime.sh` to enable on-demand block streaming for eStargz-formatted AI images.
- **NVIDIA `enroot`**: Bundled into `base-nvidia-datacenter` and `ai-infer-nvidia-*` for rootless Slurm/HPC container isolation.
- **`container-structure-test`**: Integrated into Packer QEMU verification to validate image filesystem contracts before release artifact publishing.

## Consequences

### Positive

- **Drastic Resource Savings**: Nodes utilizing `crun` experience a ~85% reduction in runtime memory overhead per container.
- **Zero-Bloat Troubleshooting**: Production images maintain zero unnecessary packages while operators retain instant debugging capabilities via `cdebug`.
- **Sub-Second Pod Scheduling**: Lays the foundation for instant cold-starts of heavy AI/ML containers via lazy image streaming.
- **Power of 10 Compliance**: All installation logic adheres strictly to bounded network execution (`curl --max-time 30`), functions $\le 60$ lines, and checked return codes.

### Negative / Neutral

- Rootfs size of container host images increases by ~22MB due to the static `cdebug` binary.
- Operators must specify `runtimeClassName: crun` on Pod specs to leverage the non-default C-based runtime.
