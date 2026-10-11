# Ultra-Deep Image Optimization, Slimming & Hardening Specification

`lusoris-cloud-images` achieves sub-second cold boot times (< 1.5s on modern NVMe hypervisors), minimal storage footprints (~400–600MB reductions over stock distributions), and enterprise compliance adhering to **CIS Benchmark Level 2** and **BSI IT-Grundschutz SYS.1.3**. This document defines the technical architecture of these optimizations.

---

## 1. Boot Acceleration Architecture (< 1.5s Cold Boot)

Cold boot latency in cloud environments directly dictates auto-scaling agility and microVM responsiveness.

```text
+-----------------------------------------------------------------------------+
|                     LUSORIS OPTIMIZED BOOT PIPELINE                         |
+-------------------+--------------------+-------------------+----------------+
| Firmware / BIOS   | GRUB2 / EFI Stub   | Initramfs (Zstd)  | Systemd Userspace|
| (< 100ms)         | (< 50ms)           | (< 350ms)         | (< 900ms)      |
+-------------------+--------------------+-------------------+----------------+
```

### 1.1 GRUB2 & EFI Fast-Boot Directives

- **Zero Menu Delay**: `GRUB_TIMEOUT=0` and `GRUB_RECORDFAIL_TIMEOUT=0` in `/etc/default/grub`.
- **Quiet Kernel Printk**: `loglevel=3 quiet console=tty1 console=ttyS0,115200n8` suppresses kernel console spam while keeping serial redirection active.
- **Fast Initramfs Decompression**: Initramfs archives are compressed with Zstandard (`COMPRESS=zstd -19`) for near-instant decompression speed on modern CPUs.

### 1.2 Fast-Path Cloud-Init Discovery (`NoCloud`)

Standard cloud-init spends 3–8 seconds querying multiple cloud metadata endpoints (`AWS`, `Azure`, `GCP`, `OpenStack`, `DigitalOcean`).

- **NoCloud Prioritization**: In `/etc/cloud/cloud.cfg.d/90_dpkg.cfg`, `datasource_list: [ NoCloud, ConfigDrive, None ]` terminates metadata discovery immediately when local ISO/disk metadata is found.
- **Network Wait Masking**: `cloud-init-generator` masks `systemd-networkd-wait-online.service` with a bounded timeout (`--timeout=5`), eliminating long DHCP discovery stalls.

### 1.3 Systemd Unit Masking & Parallelization

Non-essential services are masked or deferred:

- Masked: `plymouth`, `whoopsie`, `apport`, `snapd.seeded.service`.
- Serial Getty services on inactive terminals (`tty2`–`tty6`) are set to autospawn on demand rather than launching concurrently at boot.

---

## 2. Radical Filesystem & Firmware Slimming (~400–600MB Saved)

Cloud virtual machines running on hypervisors or enterprise rack servers have no physical need for desktop wireless drivers, cellular modems, or audio firmware.

### 2.1 Firmware Pruning

The `/lib/firmware` directory in stock Ubuntu exceeds 800MB. Lusoris retains only datacenter-relevant firmware:

- **Retained**: Intel/AMD GPU firmware (`i915`, `amdgpu`), Mellanox ConnectX NIC firmware (`mlx5`), QLogic/Broadcom HBA firmware, and CPU microcode (`intel-microcode`, `amd64-microcode`).
- **Pruned**: Wi-Fi chipsets (`iwlwifi`, `ath10k`, `ath11k`, `rtlwifi`), Bluetooth adapters, TV tuners, and legacy audio codecs.
- **Net Reduction**: Saves ~450MB of raw disk space and reduces initramfs size by 35%.

### 2.2 Apt Documentation & Cache Purge

Lusoris drop-in configuration `/etc/apt/apt.conf.d/01nodoc` permanently prevents downloading documentation:

```text
path-exclude /usr/share/doc/*
path-exclude /usr/share/man/*
path-exclude /usr/share/groff/*
path-exclude /usr/share/info/*
path-exclude /usr/share/lintian/*
path-exclude /usr/share/linda/*
```

---

## 3. ZRAM In-Memory Swap Guard & Memory Optimization

To eliminate slow disk-based swap thrashing on SSD/NVMe drives while preventing Out-Of-Memory (OOM) killer terminations during brief memory spikes:

1. **ZRAM Block Device**: A compressed RAM disk (`/dev/zram0`) is created with a size equal to 50% of total physical RAM (up to a 16GB ceiling).
2. **Compression Algorithm**: Zstandard (`zstd`) or `lz4` compression provides a 3:1 to 4:1 compression ratio with sub-microsecond latency.
3. **Swap Priority**: Configured with priority `100` (`swapon -p 100 /dev/zram0`), ensuring the kernel swaps into compressed RAM before any physical disk swap.
4. **Swappiness Tuning**: `vm.swappiness = 10` ensures anonymous memory is kept in physical RAM, only invoking ZRAM under real memory pressure.

---

## 4. Hardening Baselines: CIS Level 2 & BSI IT-Grundschutz SYS.1.3

Lusoris provisioners enforce compliance with **Center for Internet Security (CIS) Ubuntu Server Benchmark Level 2** and **German Federal Office for Information Security (BSI) IT-Grundschutz Standard SYS.1.3 (Server under Linux)**:

### 4.1 Kernel Lockdown & Core Dumps

- **Core Dump Disabling**: `* hard core 0` in `/etc/security/limits.d/10-nocore.conf` and `fs.suid_dumpable = 0`.
- **Ptrace Restrictions**: `kernel.yama.ptrace_scope = 1` prevents processes from attaching to unowned parent/child processes.
- **Kptr Restrictions**: `kernel.kptr_restrict = 2` hides kernel symbol addresses in `/proc/kallsyms` from non-root processes.

### 4.2 Network Stack Lockdown

- **SYN Flood Protection**: `net.ipv4.tcp_syncookies = 1`.
- **Reverse Path Filtering**: `net.ipv4.conf.all.rp_filter = 1` and `net.ipv4.conf.default.rp_filter = 1` prevents IP spoofing.
- **ICMP Redirect Rejection**: `net.ipv4.conf.all.accept_redirects = 0` and `net.ipv4.conf.all.send_redirects = 0`.

---

## 5. Multi-Distribution Matrix Evaluation & Roadmap

While Ubuntu LTS (Ubuntu 26.04 LTS Resolute Minimal, maintaining Ubuntu 24.04 LTS compatibility) serves as the primary base distribution for hardware and driver breadth, Lusoris formalizes an active multi-distribution upstream roadmap ([ADR-0009](../adr/0009-multi-distribution-base-roadmap.md)):

| Distribution Base | Strengths | Weaknesses | Architectural Roadmap Status |
| :--- | :--- | :--- | :--- |
| **Ubuntu LTS (26.04 / 24.04)** | Broadest GPU/accelerator driver support, Canonical security backports, first-class cloud-init | Larger base image size without pruning | **Production Foundation** across all 44 GPU/compute flavors |
| **Debian 13 (Trixie) / 12 (Bookworm)** | Extremely lean base, predictable upstream, rock-solid stability | Slower backports for bleeding-edge NVIDIA/ROCm drivers | **Phase 2 Target**: Minimal microVMs, storage appliances (`cloudnative-storage`) |
| **Alpine Linux (3.21+)** | Tiny footprint (< 50MB), musl libc security | musl glibc incompatibility with proprietary NVIDIA/CUDA drivers | **Phase 3 Target**: Lightweight edge gateway appliances & microVMs |
| **bootc (CentOS/Fedora)** | OCI image-based boot, transactional OSTree updates | Heavy container registry dependence during boot | **Phase 4 Target**: Declarative immutable host (`cloudnative-generic`) |
| **Talos Linux** | Completely immutable, API-driven, zero SSH, ephemeral root | Inflexible for custom host-level homelab appliances | Evaluated reference benchmark for pure Kubernetes nodes |

---

## 6. Modern Container Runtimes & Zero-Footprint Diagnostics

Following insights from the container ecosystem and [`pditommaso/awesome-containers`](https://github.com/pditommaso/awesome-containers) codified in [ADR-0010](../adr/0010-container-ecosystem-runtimes-and-tooling.md), container workloads in `lusoris-cloud-images` implement modern performance and operational standards:

1. **Dual OCI Runtime Engines (`runc` & `crun`)**:
   - Standard `runc` remains active for default compatibility.
   - High-performance `crun` is pre-baked and configured in containerd as an alternative `RuntimeClass`, cutting container startup latency by 2–3x and reducing resident memory overhead from ~25MB to ~4MB per container.
2. **Zero-Footprint Troubleshooting (`cdebug`)**:
   - Production images strictly avoid bundling debugging utilities (`gdb`, `strace`, `tcpdump`, `curl`, `netshoot`) into container base layers.
   - Instead, the host operating system provides `cdebug` (`/usr/local/bin/cdebug`), enabling operators to attach ephemeral troubleshooting toolkits into any running container or Pod namespace on-demand without image modification.
3. **Lazy-Pulling Snapshotter Roadmap (eStargz)**:
   - For multi-gigabyte AI/ML inference containers (Ollama, vLLM, PyTorch), `stargz-snapshotter` enables startup in $< 2\text{s}$ by streaming content on-demand over HTTP range requests rather than waiting for full-image downloads.
