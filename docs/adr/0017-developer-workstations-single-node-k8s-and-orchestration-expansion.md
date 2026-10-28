# 17. Developer Workstation Environments, Single-Node Kubernetes, and Clustered Orchestration Expansion

Date: 2026-09-10

## Status

Accepted

## Context

`imago` provides hardened virtual machine and bare-metal OS images across 7 workload tiers (Base OS, Docker/Podman, Multi-Node Kubernetes, K3s Edge Fleet, CloudNative Storage, AI Inference, and Homelab Appliances).

An architectural review of developer and operator workflows identified four critical unaddressed use cases:

1. **Interactive Remote Development Environments**: While `appliance-ci-runner` provides headless DinD for CI execution, developers frequently require persistent, browser-accessible remote workstations (`code-server` / OpenVSCode Server) with pre-configured polyglot runtimes (`uv` for Python, Go, Rust `rustup`, Node.js/Bun) and pre-wired Docker/Podman sockets for DevContainers.
2. **Turnkey Single-Node Kubernetes**: Current Tier 3 `k8s-node-*` flavors are worker nodes expecting a cluster control-plane (`kubeadm join`). However, developers, CI pipelines, and standalone edge servers need an immediate, full-fledged upstream Kubernetes node ready on first boot with untainted control plane (`NoSchedule-`), local-path storage, and metrics-server.
3. **Alternative Cluster Orchestration Beyond Kubernetes**: Enterprise Kubernetes is frequently over-engineered for small teams, edge deployments, and homelab environments. Open-source orchestrators like **Docker Swarm** (built into Docker Engine with zero daemon overhead) and **HashiCorp Nomad** (~45MB RAM footprint, scheduling both OCI containers and raw binaries) provide simpler, resilient clustering alternatives.
4. **Self-Hosted Developer Backends**: Airgapped, private homelab, or sovereign team infrastructures require a self-contained developer forge combining lightweight Git hosting (Forgejo / Gitea), container-native CI/CD (Woodpecker CI), and a private OCI artifact registry (Zot / Harbor).

## Decision

We formalize the architectural roadmap for developer workstations, standalone Kubernetes, and alternative orchestrators:

### 1. Developer Workstation Appliances (`dev-workstation`)

- **Remote Web IDE**: Integrates `code-server` with configurable TLS, password/token authentication, and native OpenSSH with agent forwarding.
- **Polyglot Developer Toolchains**: Pre-installs modern compiler toolchains:
  - Python: `uv` (fast package manager and Python version manager).
  - Go: Pinned stable Go toolchain.
  - Rust: `rustup` with `cargo` and `clippy`.
  - JavaScript/TypeScript: Node.js LTS and Bun.
- **Container-in-VM Ergonomics**: Rootless Podman and Docker CE pre-configured with socket forwarding (`/var/run/docker.sock`) to support Microsoft DevContainers and VS Code Remote extensions.
- **Diagnostic CLI Suite**: Includes `cdebug`, `starship`, `tmux`, `zsh`, `neovim`, `btop`, `ripgrep`, `fd`, `bat`, and `eza`.

### 2. Turnkey Single-Node Kubernetes (`k8s-node-standalone`)

- **Base Runtime**: containerd 2.3.5, kubelet 1.37.0, and kubeadm.
- **Automated Standalone Bootstrap**: A cloud-init hook initializes the cluster on first boot:
  - Untaints the control plane: `kubectl taint nodes --all node-role.kubernetes.io/control-plane-`.
  - Installs CNCF `local-path-provisioner` for persistent storage classes.
  - Deploys pre-warmed `metrics-server` for resource monitoring.
  - Automatically loads pre-cached CNI daemonsets (Cilium or Flannel).

### 3. Lightweight Clustered Container Orchestrators

- **Docker Swarm Profile**:
  - Leverages existing `docker-*` flavors with pre-tuned kernel VXLAN settings, sysctl buffer scaling, and firewall rules for Swarm management (TCP 2377), node communication (TCP/UDP 7946), and overlay traffic (UDP 4789).
  - Supplies automated cloud-init join templates for instant manager/worker formation.
- **HashiCorp Nomad Track**:
  - Evaluates lightweight Nomad client/server nodes for non-Kubernetes microVM and binary scheduling.
- **Linux Containers (Incus) Track**:
  - Provides rootfs tarballs (`.rootfs.tar.zst`) for sub-second system container launching sharing the host kernel.
- **Podman Quadlet Integration**:
  - Expands unit generation tools for daemonless systemd-supervised `.container` services.

### 4. Self-Hosted Dev Backend (`appliance-dev-forge`)

- Packages a complete, lightweight developer platform into a turnkey appliance:
  - **Git Forge**: Forgejo (Go-based, $< 80\text{MB}$ RAM).
  - **CI Engine**: Woodpecker CI server and agent.
  - **OCI Registry**: Zot (pure Go OCI v2 container registry).

## Consequences

### Positive

- **Complete Developer Journey**: Extends `imago` from hypervisor infrastructure to day-to-day developer productivity.
- **Zero-Barrier Single-Node K8s**: Enables instant local Kubernetes clusters without cluster-api or multi-node setup complexity.
- **Operational Diversity**: Supports teams and homelabbers seeking lightweight alternatives (Docker Swarm, Nomad) to heavy Kubernetes clusters.
- **Hard Rule 10 Compliance**: All proposed profiles and templates strictly preserve the RFC 1918 zero-leak invariant.

### Negative / Neutral

- Adds new appliance flavors to the documentation and testing matrices.
