#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 79-appliance-game.sh — Dedicated game server appliance (SteamCMD, Pterodactyl Wings, Palworld, CS2)
# 32-bit i386 multiarch glibc runtime, SteamCMD, low-latency UDP socket tuning, and 1M file limits.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

enable_i386_multiarch_runtime() {
  local arch
  arch="$(dpkg --print-architecture)"
  if [ "${arch}" != "amd64" ]; then
    echo "    Notice: Host architecture is '${arch}'; i386 multiarch is x86_64 specific. Skipping."
    return 0
  fi

  echo "==> Enabling i386 multiarch architecture and runtime libraries..."
  sudo dpkg --add-architecture i386
  sudo apt-get update

  # Accept Steam license non-interactively
  echo steam steam/question select "I AGREE" | sudo debconf-set-selections
  echo steam steam/license note '' | sudo debconf-set-selections

  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    lib32gcc-s1 \
    lib32stdc++6 \
    libc6:i386 \
    libsdl2-2.0-0:i386 \
    libcurl4:i386 \
    steamcmd

  # Symlink steamcmd to canonical system PATH
  if [ -f /usr/games/steamcmd ] && [ ! -f /usr/local/bin/steamcmd ]; then
    sudo ln -s /usr/games/steamcmd /usr/local/bin/steamcmd
  fi
}

tune_gaming_udp_buffers_and_limits() {
  echo "==> Tuning kernel network stack for low-latency, high-burst UDP gaming..."
  cat <<'SYSCTL' | sudo tee /etc/sysctl.d/99-game-server.conf >/dev/null
# Maximize UDP socket buffers to eliminate packet loss during player spikes
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.core.rmem_default = 1048576
net.core.wmem_default = 1048576
net.ipv4.udp_rmem_min = 16384
net.ipv4.udp_wmem_min = 16384

# Unreal Engine 5 & source engine max memory map limits
vm.max_map_count = 1048576
SYSCTL

  # Configure maximum open file descriptors for game server panels
  cat <<'LIMITS' | sudo tee /etc/security/limits.d/99-game-server.conf >/dev/null
* soft nofile 1048576
* hard nofile 1048576
root soft nofile 1048576
root hard nofile 1048576
LIMITS
}

main() {
  enable_i386_multiarch_runtime
  tune_gaming_udp_buffers_and_limits
  echo "==> 79-appliance-game: Complete."
}

main "$@"
