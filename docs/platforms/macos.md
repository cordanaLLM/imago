# macOS Developer Platform Specification (Apple Silicon M1–M4)

Running cloud infrastructure images locally on macOS developer machines requires tailored virtualization configurations, ARM64/x86_64 binary translation, and host-guest filesystem synchronization. This document defines the engineering standards for running Lusoris images on Apple Silicon (M1, M2, M3, and M4).

---

## 1. Supported macOS Virtualization Engines

Lusoris images support both native ARM64 execution and Rosetta 2 translation across major macOS hypervisor engines:

| Engine | Virtualization Backend | Primary Use Case | Shared Filesystem | Graphical Display |
| :--- | :--- | :--- | :--- | :--- |
| **UTM** | Apple Virtualization.framework / QEMU | Desktop VMs, GUI consoles | VirtIO-FS / 9p | SPICE / Metal |
| **OrbStack** | Hypervisor.framework (Lightweight) | Fast headless containers / Linux machines | Native 9p/VirtIO | Headless / SSH |
| **Lima** | Apple Virtualization.framework | Cloud-init automated developer VMs | VirtIO-FS | Headless / SSH |
| **Colima** | Lima / QEMU wrapper | Docker / Kubernetes CLI backend | VirtIO-FS | Headless / SSH |

---

## 2. Rosetta 2 Linux Binary Translation

While Apple Silicon runs ARM64 kernels natively, developer workflows frequently require executing legacy x86_64 binaries or container images. macOS Virtualization.framework provides native Rosetta 2 binary translation inside Linux guest environments.

### 2.1 Configuration & Mount

Apple Virtualization.framework exposes the Rosetta translation binary via a special VirtIO-FS share. To mount and enable Rosetta 2:

```bash
# Mount Rosetta share from macOS host
sudo mkdir -p /run/rosetta
sudo mount -t virtiofs rosetta /run/rosetta

# Register Rosetta binary with Linux binfmt_misc
echo ':rosetta:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00:\xff\xff\xff\xff\xff\xfe\xfe\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/run/rosetta/rosetta:OC' | sudo tee /proc/sys/fs/binfmt_misc/register
```

### 2.2 Invariant Verification

Once registered, x86_64 Linux ELF binaries execute transparently on Apple Silicon with hardware-accelerated translation, achieving approximately 70–85% of native execution speed for compute-intensive tasks.

---

## 3. Host-Guest Directory Sharing (VirtIO-FS)

VirtIO-FS provides low-latency, memory-mapped shared directory access between macOS APFS host filesystems and Lusoris guest kernels.

### 3.1 UTM and Lima VirtIO-FS Mounting

```bash
# Mount shared folder named "workspace" with POSIX permission mapping
sudo mkdir -p /mnt/workspace
sudo mount -t virtiofs workspace /mnt/workspace -o rw,sync
```

### 3.2 Automated FSTAB Integration

Add the shared mount to `/etc/fstab` for persistent availability:

```text
workspace /mnt/workspace virtiofs rw,nofail 0 0
```

---

## 4. Display, Clipboard & Resolution Synchronization (SPICE)

For desktop virtualization environments (UTM):

1. **Dynamic Resolution**: `spice-vdagent` communicates with the QEMU/UTM SPICE channel, automatically resizing the Linux guest resolution when the macOS application window is resized.
2. **Bidirectional Clipboard**: Seamlessly synchronizes text and clipboard buffers between macOS pasteboards and Linux X11/Wayland selections.
3. **Condition Virtualization**: `spice-vdagent.service` is pre-installed in Lusoris base images and automatically sleeps when no SPICE character device (`/dev/virtio-ports/com.redhat.spice.0`) is present, consuming zero CPU cycles in headless server deployments.

---

## 5. Laptop Battery & Thermal Preservation Tuning

Running virtual machines on MacBook Pro / Air hardware on battery power requires conservative CPU idle scheduling:

- **Tickless Idle**: Lusoris kernels run with `CONFIG_NO_HZ_IDLE=y` enabled, ensuring idle virtual CPU harts do not trigger timer interrupts that prevent Apple Silicon efficiency cores (E-cores) from entering deep power-saving states (`C-states`).
- **Disk I/O Flush Cadence**: `vm.dirty_writeback_centisecs = 1500` extends the background page flush window to 15 seconds, preventing frequent SSD write wakeups.
