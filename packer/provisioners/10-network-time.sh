#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 10-network-time.sh — Resilient Global NTS time synchronization via chrony
# Combines global Anycast NTS, Stratum-1 national laboratories, and graceful pool fallback.
set -euo pipefail

install_chrony() {
  echo "==> Installing chrony..."
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends chrony
}

configure_global_sources() {
  echo "==> Configuring resilient multi-tier NTS and Stratum-1 sources..."
  if [ -d /etc/chrony/sources.d ]; then
    sudo find /etc/chrony/sources.d -maxdepth 1 -type f -name 'ubuntu*.sources' -delete
  fi

  if [ -f /etc/chrony/chrony.conf ]; then
    sudo sed -Ei 's|^[[:space:]]*sourcedir[[:space:]]+/run/chrony-dhcp[[:space:]]*$|# sourcedir /run/chrony-dhcp  # Disabled: enforce authoritative NTS sources only.|' /etc/chrony/chrony.conf
  fi

  cat <<'EOF' | sudo tee /etc/chrony/sources.d/global-nts.sources
# Tier 1: Global Anycast NTS (Cloudflare worldwide low-latency)
server time.cloudflare.com iburst nts

# Tier 2: European Stratum-1 NTS National Metrology Institutes
server ptbtime1.ptb.de iburst nts
server ptbtime2.ptb.de iburst nts
server nts.netnod.se iburst nts
server ntp.time.nl iburst nts
server ntp.3eck.net iburst nts

# Tier 3: Resilient fallback pool (active if egress firewalls block NTS TCP/4460)
pool 2.ubuntu.pool.ntp.org iburst maxsources 4
EOF

  cat <<'EOF' | sudo tee /etc/chrony/conf.d/global-policy.conf
# Global Time Synchronization & Stepping Policy
makestep 1.0 3
rtconutc
minsources 3
authselectmode mix
EOF
}

verify_and_enable_chrony() {
  echo "==> Verifying and starting chrony service..."
  sudo chronyd -p >/dev/null
  sudo systemctl enable chrony.service
  sudo systemctl restart chrony.service
}

main() {
  install_chrony
  configure_global_sources
  verify_and_enable_chrony
  echo "==> 10-network-time: Complete."
}

main "$@"
