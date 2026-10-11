#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 76-appliance-gateway.sh — High-Availability Gateway, AdGuard Home, Pi-hole, and WireGuard
# Frees port 53 (DNSStubListener=no), enables IP forwarding, and pre-loads WireGuard modules.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

free_port_53_dns_stub() {
  echo "==> Configuring systemd-resolved to disable port 53 stub listener..."
  sudo mkdir -p /etc/systemd/resolved.conf.d

  cat <<'RESOLV' | sudo tee /etc/systemd/resolved.conf.d/00-disable-stub.conf >/dev/null
[Resolve]
DNSStubListener=no
DNS=1.1.1.1 9.9.9.9
FallbackDNS=1.0.0.1 149.112.112.112
RESOLV

  # Ensure static resolv.conf points to public DNS until container starts
  sudo rm -f /etc/resolv.conf
  sudo ln -s /run/systemd/resolve/resolv.conf /etc/resolv.conf
}

configure_wireguard_and_forwarding() {
  echo "==> Installing WireGuard tools and configuring network packet forwarding..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    wireguard-tools \
    iptables \
    nftables \
    conntrack

  # Autoload WireGuard kernel module on boot
  echo "wireguard" | sudo tee /etc/modules-load.d/wireguard.conf >/dev/null

  # Enable router & gateway IP forwarding in sysctl
  cat <<'SYSCTL' | sudo tee /etc/sysctl.d/99-gateway.conf >/dev/null
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
SYSCTL
}

main() {
  free_port_53_dns_stub
  configure_wireguard_and_forwarding
  echo "==> 76-appliance-gateway: Complete."
}

main "$@"
