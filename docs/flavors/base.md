# Base Flavors

The `base-*` tier provides a zero-bloat, hardened Linux foundation for general-purpose virtual machines, bare-metal servers, and cloud instances.

## Key Characteristics

- **Distro Base**: Ubuntu 26.04 LTS (Resolute).
- **Purged Components**: `snapd`, `lxd`, Ubuntu Pro client, telemetry daemons, motd news, unused locales, and man pages.
- **Time Synchronization**: Network Time Security (NTS) chrony client with multi-tier Anycast (Cloudflare) and national metrology institutes (PTB, Netnod, SIDN, 3eck).
- **Hypervisor Coexistence**: Both `qemu-guest-agent` and `open-vm-tools` are installed; each daemon remains dormant unless booted on its matching hypervisor.
- **Portability**: Cloud-init operates with unrestricted datasources for seamless compatibility with Proxmox, Unraid, VMware, AWS, GCP, and Bare-Metal.
- **Kernel Tuning**: Controlled via `KERNEL_PROFILE` (`generic`, `baremetal`, `k8s`, `ai-infer`). Injects optimal sysctls, cgroups v2 accounting, and GRUB cmdline arguments.

## Available Flavors

### `base-generic`

Lightweight headless compute image. Suitable for web servers, databases, and microVMs. Uses `KERNEL_PROFILE=generic`.

### `base-intel`

Includes Intel Media Driver (`iHD`), Level Zero runtime (`libze`), OpenCL compute, Battlemage Xe2 support, CDI specification, and diagnostics (`vainfo`, `clinfo`).

### `base-amd`

Includes Mesa Gallium `radeonsi` VA-API, RADV Vulkan drivers, AMDGPU DRM runtime, and CDI specification.

### `base-nvidia-*`

Segregated into four hardware generations and datacenter:

- `base-nvidia-legacy`: NVIDIA 535 LTS driver branch for Pascal and Volta (`sm_60`, `sm_70`).
- `base-nvidia-mainstream`: NVIDIA 565 driver branch for Turing and Ampere (`sm_75`, `sm_80`, `sm_86`).
- `base-nvidia-bleeding`: NVIDIA 615 driver branch for Blackwell (`sm_100`, `sm_120`, RTX 5090, B200).
- `base-nvidia-datacenter`: NVIDIA Open Kernel Modules, Fabric Manager, and NVIDIA Enroot for Hopper and Blackwell multi-GPU NVLink meshes. Uses `KERNEL_PROFILE=baremetal`.
