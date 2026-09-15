# TrueNAS SCALE & CORE VM Integration Guide

All `lusoris-cloud-images` flavors are engineered for high-performance virtualized operation within TrueNAS SCALE (Debian KVM) and TrueNAS CORE (FreeBSD bhyve).

---

## 1. Importing Lusoris Images into TrueNAS SCALE

TrueNAS SCALE utilizes KVM for virtualization, providing native VirtIO disk, network, and PCI passthrough capabilities.

### Step 1: Download & Prepare Image on a ZFS Dataset
Log in to your TrueNAS host via SSH and decompress the release artifact into your VM zvol or dataset:

```bash
# Navigate to your VM storage dataset
cd /mnt/tank/vm-images/

# Download and stream-decompress the Lusoris flavor (e.g. docker-generic or k8s-node-generic)
curl -fsSL https://github.com/cordanaLLM/imago/releases/latest/download/lusoris-cloud-docker-generic.qcow2.zst | zstdcat > docker-generic.qcow2

# Create a sparse Zvol for maximum performance (e.g. 32GB)
zfs create -V 32G -s tank/vms/docker-node-zvol

# Stream write the raw/qcow2 image into the Zvol
qemu-img convert -p -O raw docker-generic.qcow2 /dev/zvol/tank/vms/docker-node-zvol
```

### Step 2: Configure VM in TrueNAS Web GUI
1. Navigate to **Virtualization -> Add VM**.
2. **Guest Operating System**: Select **Linux**.
3. **CPUs & Memory**:
   - Assign desired vCPUs and RAM.
   - Enable **Hyper-V EnLIGHTenments** (for Windows flavors) or leave disabled for Linux.
4. **Disks**:
   - **Disk Type**: `Zvol`.
   - **Zvol**: Select `tank/vms/docker-node-zvol`.
   - **Disk Mode**: `VirtIO` (or `VirtIO-SCSI`).
5. **Network Interface**:
   - **Adapter Type**: `VirtIO`.
   - **Bridge**: Select `br0` (or your primary management bridge).

---

## 2. Guest Agent & Health Monitoring

- **`qemu-guest-agent` Pre-Installed**: Lusoris images include the native QEMU guest agent, automatically active on first boot.
  - TrueNAS SCALE displays guest IP addresses and network interfaces directly in the Virtualization dashboard.
  - Snapshot integration: TrueNAS can perform filesystem-frozen consistent snapshots via the guest agent.
- **ACPI Clean Shutdown**: Clicking **Stop** in the TrueNAS GUI invokes `acpid`, executing a graceful shutdown of all containers and services.

---

## 3. High-Performance NAS Storage Mounts

### A. High-Throughput NFSv4.2 with Client-Side Caching (`fscache`)
To mount TrueNAS ZFS shares inside a Lusoris guest with maximum throughput and local RAM caching:

1. In `/etc/fstab` inside the Lusoris guest:
   ```text
   truenas.example.com:/mnt/tank/media  /mnt/nas/media  nfs4  rw,noatime,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,_netdev,fsc  0  0
   ```
2. Enable `cachefilesd` in the guest for persistent SSD client-side caching:
   ```bash
   sudo systemctl enable --now cachefilesd
   ```

### B. SMB 3.1.1 Multi-Channel
For SMB/CIFS shares, Lusoris kernels support SMB 3.1.1 with multi-channel enabled for bonding multiple virtual NICs:
```text
//truenas.example.com/share  /mnt/nas/share  cifs  credentials=/etc/smbcredentials,vers=3.1.1,multichannel,uid=1000,gid=1000,_netdev  0  0
```

---

## 4. Thin Provisioning & TRIM / Discard
Lusoris images enable `fstrim.timer` weekly by default. When using VirtIO-SCSI in TrueNAS:
- Ensure the disk device is created with **VirtIO-SCSI** and discard is enabled.
- Reclaimed space inside the VM is automatically returned to the underlying ZFS pool.

