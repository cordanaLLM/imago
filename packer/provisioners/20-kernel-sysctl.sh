#!/usr/bin/env bash
# Copyright 2026 Lusoris
# 20-kernel-sysctl.sh — High-performance network sysctl, CIS baseline, and per-flavor kernel tuning
# Configures BBR, OverlayFS metacopy, cgroup v2 PSI, and per-flavor kernel cmdline parameters.
# Complies with NASA/JPL Power of 10: short functions (<= 60 lines), checked returns.
set -euo pipefail

KERNEL_PROFILE="${KERNEL_PROFILE:-generic}"

configure_sysctl_and_bbr() {
  echo "==> Setting high-performance network, bridging, and BBR parameters..."
  cat <<'EOF' | sudo tee /etc/sysctl.d/99-lusoris.conf
# Network forwarding & container bridging
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1

# BBR Congestion Control & High-Throughput Buffers
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 16384
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_rfc1337 = 1
net.netfilter.nf_conntrack_max = 1048576

# Filesystem watch limits & virtual memory
fs.file-max = 2097152
fs.inotify.max_user_instances = 8192
fs.inotify.max_user_watches = 524288
vm.swappiness = 0
vm.overcommit_memory = 1
vm.max_map_count = 1048576
vm.vfs_cache_pressure = 50
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5

# CIS Benchmark Level 1 Hardening & BPF JIT
fs.suid_dumpable = 0
fs.protected_hardlinks = 1
fs.protected_symlinks = 1
fs.protected_fifos = 2
fs.protected_regular = 2
kernel.randomize_va_space = 2
kernel.kptr_restrict = 2
kernel.dmesg_restrict = 1
kernel.yama.ptrace_scope = 1
net.core.bpf_jit_harden = 2
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.icmp_echo_ignore_broadcasts = 1
EOF

  load_container_modules
}

load_container_modules() {
  printf 'overlay\nbr_netfilter\ntcp_bbr\n' | sudo tee /etc/modules-load.d/container-runtime.conf
  echo 'options overlay metacopy=on redirect_dir=on' | sudo tee /etc/modprobe.d/overlay.conf
  local module
  for module in overlay br_netfilter tcp_bbr; do
    if ! sudo modprobe "${module}"; then
      echo "    Module ${module} did not load in the build environment; it stays listed in modules-load.d." >&2
    fi
  done
}

configure_kernel_cmdline() {
  local cmdline_base="console=tty1 console=ttyS0,115200n8 quiet audit=1 audit_backlog_limit=8192 fsck.repair=yes net.ifnames=0 biosdevname=0 cgroup_no_v1=all systemd.unified_cgroup_hierarchy=1 psi=1"
  local extra_params=""

  case "${KERNEL_PROFILE}" in
    ai-infer)
      echo "==> Applying AI Inference low-latency kernel tuning (preempt=full, THP always)..."
      extra_params="preempt=full transparent_hugepage=always processor.max_cstate=1 intel_idle.max_cstate=1"
      ;;
    baremetal)
      echo "==> Applying bare-metal performance tuning (iommu=pt, split_lock_detect=off)..."
      extra_params="iommu=pt split_lock_detect=off"
      ;;
    k8s)
      echo "==> Applying Kubernetes node kernel profile..."
      extra_params="vm.swappiness=0"
      ;;
    *)
      echo "==> Using generic cloud kernel profile..."
      ;;
  esac

  if [ -f /etc/default/grub ]; then
    sudo sed -i "s|^GRUB_CMDLINE_LINUX_DEFAULT=.*|GRUB_CMDLINE_LINUX_DEFAULT=\"${cmdline_base} ${extra_params}\"|" /etc/default/grub
    sudo update-grub
  fi
}

blacklist_and_upgrades() {
  echo "==> Blacklisting unused protocols and securing unattended updates..."
  cat <<'EOF' | sudo tee /etc/modprobe.d/blacklist-uncommon.conf
install dccp /bin/true
install sctp /bin/true
install rds /bin/true
install tipc /bin/true
install cramfs /bin/true
install freevxfs /bin/true
install jffs2 /bin/true
install hfs /bin/true
install hfsplus /bin/true
EOF

  sudo sed -i '/\sswap\s/d' /etc/fstab
  sudo swapoff -a
  sudo systemctl mask swap.target

  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends unattended-upgrades
  cat <<'EOF' | sudo tee /etc/apt/apt.conf.d/20auto-upgrades
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

  cat <<'EOF' | sudo tee /etc/apt/apt.conf.d/52unattended-upgrades-blacklist
Unattended-Upgrade::Package-Blacklist {
  "linux-image-*";
  "linux-headers-*";
  "containerd*";
  "kubelet";
  "kubeadm";
  "kubectl";
};
EOF
}

main() {
  configure_sysctl_and_bbr
  configure_kernel_cmdline
  blacklist_and_upgrades
  echo "==> 20-kernel-sysctl: Complete."
}

main "$@"
