# Bare-Metal & iPXE Deployment Guide

`imago` provides bare-metal optimized images with physical hardware tuning, microcode errata mitigations, and storage expansion.

## 1. Direct Block Flashing (`imago-install-to-disk`)

You can flash a compressed `.raw.zst` directly to physical NVMe or SATA storage from any live rescue environment (e.g. Ubuntu live CD, SystemRescue, Hetzner Rescue).

Each release of your fork carries the raw disk image of every flavor that `.github/workflows/release-matrix.yml` builds (`base-generic`, `docker-generic`, `k8s-node-generic`) as `imago-cloud-<flavor>.raw.zst`, next to the `.qcow2.zst`. Both are listed in the release's `SHA256SUMS`, which the workflow signs with cosign. The helper needs the raw image: handed a `.qcow2.zst`, it finds no partition table and stops. The target disk must be at least the image's disk size (20 GiB, `disk_size` in `packer/variables.pkr.hcl`); the first boot grows the root partition to fill it.

Set `OWNER` to the account or organisation that holds your fork and `TAG` to the release you want, then check the image against the signed checksums before you write it:

```bash
OWNER=your-account
TAG=v0.1.0
for asset in imago-cloud-base-generic.raw.zst SHA256SUMS SHA256SUMS.bundle; do
  curl -fsSLO "https://github.com/${OWNER}/imago/releases/download/${TAG}/${asset}"
done
cosign verify-blob --bundle SHA256SUMS.bundle \
  --certificate-identity "https://github.com/${OWNER}/imago/.github/workflows/release-build.yml@refs/tags/${TAG}" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com SHA256SUMS
sha256sum --check --ignore-missing SHA256SUMS
```

Write the checked file with the built-in helper utility:

```bash
imago-install-to-disk imago-cloud-base-generic.raw.zst /dev/nvme0n1
```

Or stream it straight from the release without storing it, which skips the checksum check:

```bash
curl -fsSL "https://github.com/${OWNER}/imago/releases/download/${TAG}/imago-cloud-base-generic.raw.zst" | \
  zstdcat | sudo dd of=/dev/nvme0n1 bs=4M status=progress conv=fsync
```

The helper refuses a target that is not a block device. After the write it reads the first sector of the target and fails unless it ends with the boot signature `0x55 0xAA` that an MBR disk and the protective MBR of a GPT disk both carry, so a `.qcow2.zst` or any other non-raw image is reported instead of announced as ready to boot. `tests/test_install_to_disk.py` flashes images onto a loop device to check this.

```mermaid
flowchart LR
    %% Semantic class definitions with vibrant, high-contrast jewel palettes
    classDef rescue fill:#d97706,stroke:#b45309,stroke-width:2px,color:#ffffff
    classDef remote fill:#0284c7,stroke:#0369a1,stroke-width:2px,color:#ffffff
    classDef disk fill:#7c3aed,stroke:#6d28d9,stroke-width:2px,color:#ffffff
    classDef boot fill:#059669,stroke:#047857,stroke-width:2px,color:#ffffff

    subgraph RescueEnv["Live Rescue Environment (RAM / Netboot)"]
        Curl["curl -fsSL (HTTP Stream)"]:::rescue
        Zstd["zstdcat (Decompress Stream)"]:::rescue
        DD["dd of=/dev/nvme0n1 bs=4M conv=fsync"]:::rescue
        Curl -->|Unix Pipe| Zstd -->|Raw Blocks| DD
    end

    subgraph RemoteStorage["Release Server / Object Storage"]
        RemoteImg[("imago-*.raw.zst<br/><small>Compressed Image Stream</small>")]:::remote
    end

    subgraph TargetDrive["Target Physical NVMe / SATA Disk"]
        GPT["GPT Partition Table<br/><small>Root Partition (20GB)</small>"]:::disk
    end

    subgraph FirstBoot["First Boot Sequence"]
        Growpart["growpart & resize2fs<br/><small>Expands to fill 100% of Drive</small>"]:::boot
        FullRoot[("Expanded Root Filesystem<br/><small>Full Capacity Online</small>")]:::boot
        Growpart --> FullRoot
    end

    RemoteImg -->|Network Stream| Curl
    DD -->|Direct Write| GPT
    GPT -.-> FirstBoot

    style RescueEnv fill:none,stroke:#d97706,stroke-width:2px,stroke-dasharray: 4 4
    style RemoteStorage fill:none,stroke:#0284c7,stroke-width:2px,stroke-dasharray: 4 4
    style TargetDrive fill:none,stroke:#7c3aed,stroke-width:2px,stroke-dasharray: 4 4
    style FirstBoot fill:none,stroke:#059669,stroke-width:2px,stroke-dasharray: 4 4
```

---

## 2. Automatic Root Disk Expansion

When flashing a 20GB `.raw.zst` image onto a 1TB, 2TB, or larger physical drive, `cloud-guest-utils` and `growpart` automatically resize the root GPT partition and filesystem to fill 100% of the drive on first boot.

## 3. CPU Microarchitecture & Hardware Profiles

- **Intel Bare-Metal**: Configured with `intel-microcode`, `intel_iommu=on iommu=pt`, and `intel_pstate=active`.
- **AMD Bare-Metal**: Configured with `amd64-microcode`, `amd_iommu=on iommu=pt`, and `amd_pstate=active`.
- **Physical NIC Drivers**: Pre-loads network firmware (`linux-firmware`) for Intel (`ice`, `i40e`, `ixgbe`), Broadcom (`bnxt_en`), and Mellanox ConnectX (`mlx5_core`).
- **NVMe Storage Scheduling**: Udev rules enforce `none` scheduler for NVMe drives to bypass CPU scheduler latency.

## 4. iPXE Netboot

Each release flavor ships four netboot assets ([ADR-0034](../adr/0034-ipxe-netboot.md)):

| Asset | Content |
| :--- | :--- |
| `<flavor>-netboot.vmlinuz` | the image's own kernel |
| `<flavor>-netboot.initrd` | a dracut initrd with `livenet`, `dmsquash-live` and the `imago-netroot` check |
| `<flavor>-root.squashfs` | the image's root file system, zstd-compressed |
| `<flavor>.ipxe` | the boot script; it names the other three by relative URIs and carries the squashfs sha256 |

iPXE checks no digest or signature, so check the four assets against the signed checksums before you serve them. With `OWNER`, `TAG` and `FLAVOR` set as in section 1:

```bash
FLAVOR=base-generic
for asset in "${FLAVOR}-netboot.vmlinuz" "${FLAVOR}-netboot.initrd" "${FLAVOR}-root.squashfs" "${FLAVOR}.ipxe" SHA256SUMS SHA256SUMS.bundle; do
  curl -fsSLO "https://github.com/${OWNER}/imago/releases/download/${TAG}/${asset}"
done
cosign verify-blob --bundle SHA256SUMS.bundle \
  --certificate-identity "https://github.com/${OWNER}/imago/.github/workflows/release-build.yml@refs/tags/${TAG}" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com SHA256SUMS
sha256sum --check --ignore-missing SHA256SUMS
```

A squashfs of 2 GiB or more is too large for one release asset (in the 2026-10-18 build, `ai-infer-nvidia`, `ai-infer-amd` and `k3s-agent-amd`). The release then carries `${FLAVOR}-root.squashfs.part00`, `.part01`, and so on instead, the first `curl` above fails, and `SHA256SUMS` lists each part. Download the parts, check them, and join them with `tools/ci/release_assets.py join` from a checkout of the release tag, which also checks the joined squashfs ([supply chain](../security/supply-chain.md#1-cryptographic-signing-via-cosign)):

```bash
python3 -I tools/ci/release_assets.py join --sums SHA256SUMS \
  --out "${FLAVOR}-root.squashfs" "${FLAVOR}-root.squashfs".part*
```

Serve the four files from one directory of a web server, with `boot.example.com` standing for that server, and chain the script from your iPXE configuration:

```ipxe
#!ipxe
dhcp
chain https://boot.example.com/imago/base-generic.ipxe
```

The script loads the kernel and initrd from its own directory (`${cwduri}`) and boots with `root=live:<directory>/<flavor>-root.squashfs`. Before the root is mounted, the initrd compares the fetched squashfs with the `imago.root-sha256=` value in the script. A missing, malformed or different value stops the boot with `imago-netroot: root sha256 missing`, `malformed` or `mismatch` on the console; no option skips the check.

- **RAM**: the host holds the squashfs and its writable overlay in RAM. Plan for the squashfs size (about 605 MiB for `base-generic`; the release job summary lists every flavor) plus the overlay and the workload; the CI netboot test gives the guest 4 GiB.
- **State**: every change lives in the overlay and is lost at reboot.
- **Disks**: the script passes `fstab=no`, so the booted host ignores the image's `/etc/fstab` entries for the `BOOT` and `UEFI` disk partitions it does not have. Mount local disks with systemd mount units or cloud-init `mounts:` instead.
- **cloud-init**: the script passes no data source. Add `ds=nocloud;s=https://boot.example.com/seed/` to the `kernel` line of a copy of the script to give the host a NoCloud seed; the copy no longer matches `SHA256SUMS`, but it keeps the `imago.root-sha256=` value, so the squashfs is still checked at boot.
