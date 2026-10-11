# ADR 0005: Bare-Metal Compressed Block Streaming Installation

## Status

Accepted

## Context

Deploying operating systems to bare-metal servers often requires heavy PXE installers, NFS shares, or saving large uncompressed 20GB+ disk images into RAM before flashing to NVMe.

## Decision

We deliver compressed raw disk images (`.raw.zst`) and provide `/usr/local/bin/lusoris-install-to-disk`:

1. The tool streams the image over HTTPS directly through `zstdcat` into `dd of=/dev/nvmeX bs=4M`.
2. Memory consumption is limited to the zstd stream buffer (< 50MB).
3. First boot triggers `growpart` to expand the root partition to 100% of the physical drive.

## Consequences

- Fast bare-metal provisioning directly from rescue RAM disks without intermediate disk writes or large RAM requirements.
