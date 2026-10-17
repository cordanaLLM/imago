# Sourced from versions.json (build.packer.version, build.packer_plugins.*); enforced by tests/test_packer_pins.py.
packer {
  required_version = "= 1.16.1"
  required_plugins {
    qemu = {
      version = "= 1.1.7"
      source  = "github.com/hashicorp/qemu"
    }
    proxmox = {
      version = "= 1.2.4"
      source  = "github.com/hashicorp/proxmox"
    }
  }
}
