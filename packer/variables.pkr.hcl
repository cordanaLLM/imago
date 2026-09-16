variable "image_name" {
  type        = string
  default     = "lusoris-cloud"
  description = "Base output name for the generated image"
}

variable "flavor" {
  type        = string
  default     = "base-generic"
  description = "Target image flavor across the 4D matrix"
}

variable "preheat_profile" {
  type        = string
  default     = "lean"
  description = "Kubernetes image preheat profile: lean (pause only), cilium, calico, flannel"
}

variable "kernel_profile" {
  type        = string
  default     = "generic"
  description = "Hand-optimized kernel tuning profile: generic, baremetal, k8s, ai-infer"
}

variable "distro_version" {
  type        = string
  default     = "26.04"
  description = "Base distribution version (Ubuntu 26.04 LTS Resolute)"
}

variable "iso_url" {
  type        = string
  default     = ""
  description = "Optional override for upstream cloud image (defaults to versions.json distro.iso_url)"
}

variable "iso_checksum" {
  type        = string
  default     = ""
  description = "Optional override for upstream checksum (defaults to versions.json distro.iso_checksum)"
}

variable "disk_size" {
  type        = string
  default     = "20G"
  description = "Target virtual disk size"
}

variable "memory" {
  type        = number
  default     = 4096
  description = "RAM allocated during the build in MB"
}

variable "cpus" {
  type        = number
  default     = 4
  description = "vCPU count allocated during the build"
}

variable "output_dir" {
  type        = string
  default     = "output-images"
  description = "Directory where the final images are placed"
}

variable "ssh_username" {
  type        = string
  default     = "ubuntu"
  description = "SSH username used by cloud-init for build access"
}

variable "ssh_password" {
  type        = string
  default     = "ubuntu"
  sensitive   = true
  description = "Temporary SSH password for cloud-init build"
}

# Proxmox-specific variables (used when deploying to Proxmox VE)
variable "proxmox_url" {
  type        = string
  default     = "https://127.0.0.1:8006/api2/json"
  description = "Proxmox API URL (e.g. https://pve.example.com:8006/api2/json)"
}

variable "proxmox_token_id" {
  type        = string
  default     = "terraform@pve!terraform"
  description = "Proxmox API token ID"
}

variable "proxmox_token_secret" {
  type        = string
  default     = "placeholder-secret"
  sensitive   = true
  description = "Proxmox API token secret"
}

variable "proxmox_node" {
  type        = string
  default     = "pve"
  description = "Target Proxmox node"
}

variable "proxmox_skip_tls_verify" {
  type        = bool
  default     = true
  description = "Skip Proxmox TLS verification"
}

variable "storage_pool" {
  type        = string
  default     = "local-lvm"
  description = "Proxmox storage pool for templates"
}

variable "vm_id" {
  type        = number
  default     = 9000
  description = "Base VM ID for Proxmox template"
}

variable "accelerator" {
  type    = string
  default = "kvm"
  # kvm is right wherever /dev/kvm exists, which is every machine this fleet builds on
  # for real. A GitHub-hosted runner has no nested virtualisation, so QEMU there refuses
  # to start at all and reports only "Qemu failed to start"; CI passes "tcg" to emulate
  # instead. Keeping the default at kvm means a local build is never silently slow.
  description = "QEMU accelerator: kvm where /dev/kvm exists, tcg to emulate"

  validation {
    condition     = contains(["kvm", "tcg", "hvf", "whpx", "none"], var.accelerator)
    error_message = "The accelerator must be one of kvm, tcg, hvf, whpx or none."
  }
}
