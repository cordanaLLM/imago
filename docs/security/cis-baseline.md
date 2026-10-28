# CIS Benchmark Hardening Baseline

`imago` enforces Center for Internet Security (CIS) Benchmark Level 1 hardening standards directly at image build time.

## Kernel Sysctl Hardening (`/etc/sysctl.d/99-imago.conf`)

- **Memory Protection**: `fs.suid_dumpable = 0`, `kernel.randomize_va_space = 2` (ASLR), `kernel.kptr_restrict = 2`, `kernel.dmesg_restrict = 1`.
- **Filesystem Link Protection**: `fs.protected_hardlinks = 1`, `fs.protected_symlinks = 1`.
- **Network Spoofing & Redirection**:
  - Strict Reverse Path Filtering: `net.ipv4.conf.all.rp_filter = 1`.
  - ICMP Redirect Disabling: `accept_redirects = 0`, `send_redirects = 0`.
  - ICMP Broadcast Ignore: `net.ipv4.icmp_echo_ignore_broadcasts = 1`.

## Protocol Blacklisting (`/etc/modprobe.d/blacklist-uncommon.conf`)

Unused legacy and dangerous network and storage protocols are blacklisted to reduce kernel attack surface:

- Network protocols: `dccp`, `sctp`, `rds`, `tipc`.
- Legacy filesystems: `cramfs`, `freevxfs`, `jffs2`, `hfs`, `hfsplus`.

## Zero-Default Authentication

- The temporary SSH build password (`ubuntu:ubuntu`) is locked via `passwd -l ubuntu` during `99-cleanup.sh`.
- Host SSH keys are wiped from the image template and automatically regenerated on first boot by cloud-init.
