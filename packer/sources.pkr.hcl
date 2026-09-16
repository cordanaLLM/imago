# QEMU / KVM Standalone Builder
# Builds a portable QCOW2 image locally or in CI without external hypervisor dependencies.
source "qemu" "image" {
  accelerator            = var.accelerator
  headless               = true
  cpus                   = var.cpus
  memory                 = var.memory
  disk_size              = var.disk_size
  disk_image             = true
  disk_interface         = "virtio"
  format                 = "qcow2"
  net_device             = "virtio-net"
  iso_url                = var.iso_url != "" ? var.iso_url : local.manifest.distro.iso_url
  iso_checksum           = var.iso_checksum != "" ? var.iso_checksum : local.manifest.distro.iso_checksum
  output_directory       = "${var.output_dir}/${var.flavor}"
  vm_name                = "${var.image_name}-${var.flavor}.qcow2"
  cd_files               = ["${path.root}/http/meta-data", "${path.root}/http/user-data"]
  cd_label               = "cidata"
  ssh_username           = var.ssh_username
  ssh_password           = var.ssh_password
  ssh_timeout            = "15m"
  ssh_handshake_attempts = 100
  shutdown_command       = "echo '${var.ssh_password}' | sudo -S shutdown -P now"
}

# Proxmox VE Template Clone Builder
# Deploys directly into a Proxmox cluster site from an existing cloud-init base.
source "proxmox-clone" "template" {
  proxmox_url              = var.proxmox_url
  username                 = var.proxmox_token_id
  token                    = var.proxmox_token_secret
  node                     = var.proxmox_node
  insecure_skip_tls_verify = var.proxmox_skip_tls_verify

  clone_vm_id  = var.vm_id
  task_timeout = "10m"

  vm_name = "${var.image_name}-${var.flavor}-packer"
  vm_id   = var.vm_id + 100

  cores    = var.cpus
  sockets  = 1
  cpu_type = "host"
  memory   = var.memory
  os       = "l26"
  bios     = "ovmf"

  efi_config {
    efi_storage_pool  = var.storage_pool
    efi_type          = "4m"
    pre_enrolled_keys = false
  }

  scsi_controller = "virtio-scsi-pci"
  network_adapters {
    bridge = "vmbr0"
    model  = "virtio"
  }

  cloud_init              = true
  cloud_init_storage_pool = var.storage_pool

  ssh_username = var.ssh_username
  ssh_timeout  = "15m"

  template_name        = "${var.image_name}-${var.flavor}"
  template_description = "Lusoris ${var.flavor} cloud image - built by Packer on ${timestamp()}"
}
