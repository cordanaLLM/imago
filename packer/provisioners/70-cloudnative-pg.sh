#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 70-cloudnative-pg.sh — CloudNativePG and PostgreSQL database host kernel tuning
# Optimizes memory overcommit, dirty page flushing, file descriptors, and WAL write latency.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

configure_postgresql_sysctl() {
  echo "==> Configuring kernel sysctl parameters for PostgreSQL / CloudNativePG..."
  cat <<'EOF' | sudo tee /etc/sysctl.d/70-cloudnative-pg.conf >/dev/null
# PostgreSQL strict memory overcommit to avoid sudden OOM-killer termination
vm.overcommit_memory = 2
vm.overcommit_ratio = 80

# Keep dirty pages bounded for predictable checkpoint write latency
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10

# Increase open file limits and IPC messaging queues
fs.file-max = 2097152
kernel.sched_migration_cost_ns = 5000000
EOF

  if ! sudo sysctl --system; then
    echo "    sysctl --system returned non-zero; at least one configured key was not applied in the build environment." >&2
  fi
}

configure_postgresql_hugepages() {
  echo "==> Setting transparent hugepages policy for database shared buffers..."
  # Set madvise to allow PostgreSQL to allocate hugepages explicitly when configured
  if [ -d /sys/kernel/mm/transparent_hugepage ]; then
    if ! echo "madvise" | sudo tee /sys/kernel/mm/transparent_hugepage/enabled >/dev/null; then
      echo "    transparent_hugepage/enabled was not writable in the build environment." >&2
    fi
  fi

  # Ensure security limits allow large memory locks
  cat <<'EOF' | sudo tee /etc/security/limits.d/90-postgresql.conf >/dev/null
*    soft    nofile    1048576
*    hard    nofile    1048576
*    soft    memlock   unlimited
*    hard    memlock   unlimited
EOF
}

main() {
  configure_postgresql_sysctl
  configure_postgresql_hugepages
  echo "==> 70-cloudnative-pg: Complete."
}

main "$@"
