# 8. Specialized Homelab Appliance Flavors

Date: 2026-09-10

## Status

Accepted

## Context

Community feedback across r/homelab and empirical data from the Steam Hardware Survey highlight that self-hosted enthusiasts and home engineers face persistent setup hurdles when deploying standard cloud images for dedicated homelab workloads. Common pain points include:

1. **Coral TPU & NVR Setup**: Passing Google Coral TPUs (M.2 Key E/M, USB) into Frigate or Scrypted requires compiling out-of-tree kernel modules, configuring custom udev rules, and creating CDI device definitions.
2. **Port 53 Binding Collisions**: Deploying AdGuard Home or Pi-hole fails by default on Ubuntu because `systemd-resolved` binds to `127.0.0.53:53`, requiring manual stub resolver disablement.
3. **Hardware Video Transcoding**: Jellyfin and Plex servers on low-power Intel mini-PCs (N100) or AMD APUs require dual-vendor VA-API drivers and high-readahead streaming tuning to prevent buffering stalls.
4. **Multi-Arch CI Runners**: Self-hosted GitHub Actions and GitLab runners require `qemu-user-static` binfmt registration to build ARM64 images for edge clusters.
5. **Dedicated Game Servers**: Running SteamCMD or Pterodactyl Wings for dedicated servers (Palworld, CS2, Valheim) requires 32-bit `i386` multiarch glibc and tuned UDP socket buffers.

## Decision

We introduce **Tier 7: Specialized Homelab Appliances** comprising 5 purpose-built, hardened flavors:

- `appliance-vision-nvr`: Frigate NVR & Scrypted host with Google Coral TPU udev rules, Intel QuickSync VA-API (`iHD`), Docker CE, and CDI device specification (`coral.google.com/edgetpu`).
- `appliance-gateway-dns`: Ultralight gateway (< 150MB RAM) with `systemd-resolved` stub disabled (`DNSStubListener=no`), line-rate IPv4/IPv6 packet forwarding, and autoloaded WireGuard.
- `appliance-media-server`: High-throughput transcoding server with dual-vendor VA-API (Intel QuickSync + AMD Mesa), NFS/CIFS storage clients, and 4096KB streaming readahead.
- `appliance-ci-runner`: Multi-arch CI/CD runner host with QEMU `binfmt_misc` emulation, Docker Buildx, build tools, and 4GB in-memory `/tmp` tmpfs mount.
- `appliance-game-server`: Dedicated game server host with 32-bit `i386` multiarch glibc, SteamCMD, 16MB UDP socket buffer tuning, and 1,048,576 file descriptor limits.

All flavors maintain strict NASA/JPL Power of 10 compliance in provisioners, single source of truth versioning, and zero-leak privacy invariants.

## Consequences

### Positive

- Delivers turnkey, production-grade solutions for the 5 most common homelab container workloads.
- Eliminates repetitive manual kernel configuration, udev tweaking, and network buffer troubleshooting for operators.
- Expands the total image catalog to 44 active flavors while preserving zero bloat and fast boot times.

### Negative / Trade-offs

- Expands the automated build matrix and test surface by 5 additional builds.
- Adds 5 shell provisioners (`75-appliance-vision.sh` through `79-appliance-game.sh`) to the repository.
