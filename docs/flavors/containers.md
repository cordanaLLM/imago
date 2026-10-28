# Container Appliance Flavors

`imago` provides pre-configured, production-grade container host appliances supporting both **Docker CE 29.8** and **Rootless Podman 5.x**.

---

## Docker Appliances (`docker-*`)

Pre-baked with official Docker CE 29.8, `containerd.io` 2.3.5, and Docker Compose v2 plugin.

### Daemon Tuning (`/etc/docker/daemon.json`)

```json
{
  "exec-opts": ["native.cgroupdriver=systemd"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  },
  "live-restore": true,
  "userland-proxy": false,
  "features": {
    "cdi": true
  }
}
```

### Flavors

- **`docker-generic`**: Standard CPU container host for Docker Compose stacks.
- **`docker-intel`**: Pre-configured Intel QuickSync, Level Zero access, and CDI specification (`/etc/cdi/intel.yaml`) for Jellyfin, Plex, and Intel OpenVINO containers.
- **`docker-amd`**: Pre-configured AMD ROCm 7.2 compute runtime, `/dev/kfd` access, and CDI specification (`/etc/cdi/amd.yaml`) for PyTorch and ROCm containers.
- **`docker-nvidia`**: Pre-configured NVIDIA 595 driver, NVIDIA Container Toolkit, and CDI specification (`/etc/cdi/nvidia.yaml`) for Turing/Ampere GPUs.
- **`docker-nvidia-modern`**: Pre-configured NVIDIA 615 driver, NVIDIA Container Toolkit, and CDI specification for Ada Lovelace / Hopper GPUs (RTX 4080/4090, L40S, H100).
- **`docker-nvidia-bleeding`**: Pre-configured NVIDIA 615 driver, NVIDIA Container Toolkit, and CDI specification for Blackwell GPUs (RTX 5090, B200).

---

## Podman Appliances (`podman-generic`)

Daemonless and rootless container host designed for security-conscious environments and systemd integration via **Quadlet**.

### Features

- Rootless subordinate UID/GID mappings pre-configured (`/etc/subuid` and `/etc/subgid`).
- Quadlet generator directories initialized at `/etc/containers/systemd/` and `~/.config/containers/systemd/`.
- Netavark modern CNI network stack and crun OCI runtime.
- Includes `podman`, `buildah`, `skopeo`, and `crun`.
