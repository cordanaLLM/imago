# Windows Developer Platform Specification (WSL2 & Hyper-V)

Windows developer workstations and Windows Server environments require seamless integration with Windows Subsystem for Linux (WSL2) and Hyper-V Generation 2 virtual machines. This specification defines deployment standards, systemd enablement, and Hyper-V integration daemons for Lusoris images.

---

## 1. Windows Subsystem for Linux (WSL2) Deployment

Lusoris images can be imported directly into WSL2 as custom distributions, providing a hardened, bloat-free foundation for container and Kubernetes development.

### 1.1 Tarball Export & Import Workflow

1. Convert or export the raw Lusoris root filesystem:

   ```powershell
   # In PowerShell (Windows Terminal)
   wsl --import lusoris-cloud C:\WSL\lusoris-cloud .\output-images\base-generic\rootfs.tar.gz --version 2
   ```

2. Verify distribution registration:

   ```powershell
   wsl -l -v
   # Output:
   #   NAME             STATE           VERSION
   # * lusoris-cloud    Running         2
   ```

### 1.2 Declarative Configuration (`/etc/wsl.conf`)

Lusoris provides a pre-validated `/etc/wsl.conf` supporting full systemd initialization and interop:

```ini
[boot]
systemd=true

[user]
default=ubuntu

[network]
generateHosts=true
generateResolvConf=true

[interop]
enabled=true
appendWindowsPath=false
```

With `systemd=true`, all standard Linux services (`chrony`, `docker`, `containerd`, `ssh`) start identically to bare-metal and cloud VM instances.

---

## 2. Hyper-V Generation 2 Virtual Machines

For complete isolation, PCI passthrough testing, or Windows Server virtualization, Lusoris produces Generation 2 UEFI-compliant images.

### 2.1 Virtual Machine Provisioning

```powershell
# Create Generation 2 VM in PowerShell
New-VM -Name "lusoris-srv01" `
       -Generation 2 `
       -MemoryStartupBytes 4GB `
       -SwitchName "Default Switch" `
       -NewVHDPath "C:\Hyper-V\lusoris-srv01.vhdx" `
       -NewVHDSizeBytes 40GB

# Disable Secure Boot template or select Microsoft UEFI Certificate Authority
Set-VMFirmware -VMName "lusoris-srv01" -SecureBootTemplate "MicrosoftUEFICertificateAuthority"
```

---

## 3. Hyper-V Integration Services (LIS)

Lusoris provisioner `05-hypervisor-agents.sh` installs the Linux Integration Services daemons (`hyperv-daemons`) to support native hypervisor management:

| Service | Daemon Executable | Operational Function |
| :--- | :--- | :--- |
| **VSS Snapshot** | `hv_vss_daemon` | Hyper-V host-triggered Volume Shadow Copy crash-consistent backups |
| **KVP Exchange** | `hv_kvp_daemon` | Host-guest key-value pair exchange (IP address, OS version, telemetry) |
| **File Copy** | `hv_fcopy_daemon` | Direct out-of-band file copying from host to guest via `Copy-VMFile` |

All daemons are enabled in systemd and run dormant unless the virtual machine is actively executing under Microsoft Hyper-V virtualization.
