# Cloud-Native Immutable & Storage Appliance Flavors

`cloudnative-*` flavors bring immutable container hosting, Kubernetes worker nodes, and enterprise storage protocols into a hardened, zero-drift operating system baseline.

Designed after modern declarative OS architectures (such as Flatcar and Talos Linux), these flavors eliminate configuration drift, enhance cluster storage reliability, and optimize database kernel metrics for high-throughput transactional workloads.

---

## The 4 Cloud-Native & Storage Flavors

| Flavor Name | Role | Hardware Tier | Kernel Profile | Key Features |
| :--- | :--- | :--- | :--- | :--- |
| **`cloudnative-generic`** | Immutable Host | VirtIO / CPU | `generic` | Read-only root hardening, ephemeral tmpfs, containerd 2.3.5 + CDI |
| **`cloudnative-k8s`** | Immutable K8s Node | VirtIO / CPU | `k8s` | Read-only root hardening, containerd 2.3.5, kubelet 1.37.0 |
| **`cloudnative-storage`** | CNCF Storage Node | VirtIO / Baremetal | `baremetal` | NVMe-oF (TCP), OpenZFS 2.3, `open-iscsi`, `multipathd`, NFS |
| **`cloudnative-pg`** | Database Host | VirtIO / Baremetal | `ai-infer` | CloudNativePG / PostgreSQL tuning, hugepages, strict overcommit |

---

## Architectural Principles

### 1. Immutability & Drift Prevention (`cloudnative-generic`, `cloudnative-k8s`)

- **Systemd Strict System Protection**: Configures systemd managers (`DefaultProtectSystem=strict`, `DefaultProtectHome=read-only`, `DefaultPrivateTmp=yes`) to lock down core system directories against runtime modification.
- **Volatile In-Memory Directories**: Mounts `/tmp` and `/var/tmp` on RAM-backed `tmpfs` (`rw,nosuid,nodev,noexec,relatime,size=2G`), ensuring transient build artifacts and temporary files vanish on reboot.
- **Sealed Package Updates**: Disables unattended background package updates (`APT::Periodic::Update-Package-Lists "0"`). Operating system upgrades follow an immutable image replacement cycle rather than in-place apt mutations.
- **Container Device Interface (CDI)**: Pre-configures `/etc/cdi` and `/var/run/cdi` for declarative, vendor-neutral hardware acceleration passthrough.

### 2. CNCF Storage Protocols & Fabrics (`cloudnative-storage`)

Designed for distributed Kubernetes storage operators (Rook-Ceph, Longhorn, OpenEBS, TrueNAS SCALE CSI), this appliance bakes in kernel modules and userspace tooling for high-speed block and network storage:

- **NVMe-oF (NVMe over Fabrics TCP)**: Kernel modules `nvme-core`, `nvme-fabrics`, and `nvme-tcp` autoload on boot, enabling high-performance NVMe block storage streaming over commodity 10GbE/25GbE networks.
- **OpenZFS 2.3**: Ships with native OpenZFS userspace utilities and kernel modules (`zfsutils-linux`) for high-speed ZFS LocalPV pools, compression, and snapshotting.
- **Multipath I/O & iSCSI**: Pre-configures `multipath-tools` with friendly device naming and enables `iscsid.service` for SAN fabrics.
- **NFS Client**: Pre-installs `nfs-common` for shared volume mounts and read-write-many (RWX) CSI provisioners.

### 3. Database & CloudNativePG Hardening (`cloudnative-pg`)

Databases require fundamentally different kernel memory dynamics than stateless web applications. Running PostgreSQL or CloudNativePG on standard Linux kernels risks abrupt OOM-killer evictions and I/O checkpoint spikes. `cloudnative-pg` applies strict kernel tuning:

- **Strict Memory Accounting**: Sets `vm.overcommit_memory = 2` and `vm.overcommit_ratio = 80`. This prevents Linux from overcommitting memory allocations beyond RAM + swap, ensuring the kernel refuses excessive malloc requests rather than killing the PostgreSQL master process.
- **Smooth Checkpoint I/O**: Reduces dirty background page threshold to `vm.dirty_background_ratio = 5` and hard threshold to `vm.dirty_ratio = 10`. This forces kernel background flushers to write dirty blocks to disk continuously, preventing sudden multi-gigabyte disk write freezes during WAL sync.
- **Transparent Hugepages (`madvise`)**: Disables aggressive system-wide hugepage defragmentation while enabling `madvise`, allowing PostgreSQL to explicitly lock 2MB hugepages for shared memory buffers without random memory stalls.
- **High File Descriptor & Lock Limits**: Bumps file descriptors (`fs.file-max = 2097152`, security limits `1048576`) and permits unlimited process memory locking (`memlock unlimited`).

---

## Cloud-Init Bootstrap Examples

### Immutable Kubernetes Worker (`cloudnative-k8s`)

Join a Kubernetes cluster with read-only root guarantees:

```yaml
#cloud-config
write_files:
  - path: /etc/systemd/system/kubelet.service.d/20-nocloud.conf
    permissions: "0644"
    content: |
      [Service]
      Environment="KUBELET_EXTRA_ARGS=--node-ip=192.0.2.10 --protect-kernel-defaults=true"

runcmd:
  - systemctl enable --now kubelet.service
```

### CNCF Storage Node: Connect NVMe-oF Target (`cloudnative-storage`)

Discover and attach an NVMe-oF volume over TCP on boot:

```yaml
#cloud-config
runcmd:
  - nvme discover -t tcp -a 192.0.2.20 -s 4420
  - nvme connect -t tcp -a 192.0.2.20 -s 4420 -n nqn.2026-09.io.lusoris:storage.nvme0
```

### CloudNativePG Host Mount & Pool Setup (`cloudnative-pg`)

Ensure dedicated NVMe drive is formatted and ready for CNPG persistent storage:

```yaml
#cloud-config
disk_setup:
  /dev/nvme0n1:
    table_type: "gpt"
    layout: true
    overwrite: false

fs_setup:
  - label: pgdata
    filesystem: ext4
    device: /dev/nvme0n1
    partition: auto

mounts:
  - [ "/dev/nvme0n1", "/var/lib/postgresql/data", "ext4", "defaults,noatime,nodiratime,commit=60", "0", "2" ]
```
