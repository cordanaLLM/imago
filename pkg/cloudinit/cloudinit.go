// Copyright 2026 Lusoris
// Package cloudinit generates hardened cloud-init user-data and meta-data
// across virtualization platforms and developer workstations.
package cloudinit

import (
	"encoding/json"
	"fmt"
	"regexp"
	"strings"

	"github.com/cordanaLLM/imago/pkg/flavors"
)

// Config specifies the runtime identity and platform targets for cloud-init generation.
type Config struct {
	Hostname          string   `json:"hostname"`
	User              string   `json:"user"`
	SSHAuthorizedKeys []string `json:"ssh_authorized_keys"`
	Platform          string   `json:"platform"`
	Flavor            string   `json:"flavor"`
	Timezone          string   `json:"timezone"`
	ExtraPackages     []string `json:"extra_packages,omitempty"`
}

// DefaultConfig returns opinionated production defaults.
func DefaultConfig(flavor string) Config {
	return Config{
		Hostname: "lusoris-node",
		User:     "ubuntu",
		Platform: "proxmox",
		Flavor:   flavor,
		Timezone: "UTC",
	}
}

// Platforms are the platform targets the generator knows; proxmox needs no extra user-data.
var platforms = map[string]bool{
	"proxmox": true, "unraid": true, "truenas": true, "macos": true, "utm": true, "windows": true, "hyperv": true,
}

// Every value written into the YAML passes one of these allow-lists. The user name pattern
// is the subset every useradd and adduser accepts; the package pattern is Debian Policy 5.6.1.
var (
	hostnamePattern = regexp.MustCompile(`^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$`)
	userPattern     = regexp.MustCompile(`^[a-z][a-z0-9_-]{0,31}$`)
	timezonePattern = regexp.MustCompile(`^[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+)*$`)
	packagePattern  = regexp.MustCompile(`^[a-z0-9][a-z0-9+.-]+$`)
	sshKeyPattern   = regexp.MustCompile(`^(ssh-(ed25519|rsa)|ecdsa-sha2-nistp(256|384|521)|sk-(ssh-ed25519|ecdsa-sha2-nistp256)@openssh\.com) [A-Za-z0-9+/]+={0,3}( [\x20-\x7e]*)?$`)
)

// normalize fills the defaults GenerateUserData has always applied.
func normalize(cfg Config) Config {
	if cfg.User == "" {
		cfg.User = "ubuntu"
	}
	if cfg.Hostname == "" {
		cfg.Hostname = "lusoris-node"
	}
	if cfg.Timezone == "" {
		cfg.Timezone = "UTC"
	}
	if cfg.Platform == "" {
		cfg.Platform = "proxmox"
	}
	cfg.Platform = strings.ToLower(cfg.Platform)
	return cfg
}

// Validate refuses a configuration whose values would not render as the YAML they claim to be.
func Validate(cfg Config) error {
	cfg = normalize(cfg)
	if _, err := flavors.Get(cfg.Flavor); err != nil {
		return fmt.Errorf("cloudinit: %w", err)
	}
	if !platforms[cfg.Platform] {
		return fmt.Errorf("cloudinit: platform %q is not one of proxmox, unraid, truenas, macos, utm, windows, hyperv", cfg.Platform)
	}
	if err := validateIdentity(cfg); err != nil {
		return err
	}
	return validateLists(cfg)
}

func validateIdentity(cfg Config) error {
	if !hostnamePattern.MatchString(cfg.Hostname) {
		return fmt.Errorf("cloudinit: hostname %q is not a single RFC 1123 label of 1 to 63 letters, digits and inner hyphens", cfg.Hostname)
	}
	if !userPattern.MatchString(cfg.User) || cfg.User == "root" {
		return fmt.Errorf("cloudinit: user %q must match %s and must not be root", cfg.User, userPattern)
	}
	if !timezonePattern.MatchString(cfg.Timezone) {
		return fmt.Errorf("cloudinit: timezone %q is not an IANA zone name", cfg.Timezone)
	}
	return nil
}

func validateLists(cfg Config) error {
	for i, key := range cfg.SSHAuthorizedKeys {
		if trimmed := strings.TrimSpace(key); trimmed != "" && !sshKeyPattern.MatchString(trimmed) {
			return fmt.Errorf("cloudinit: ssh key %d is not a single-line OpenSSH public key", i)
		}
	}
	for _, pkg := range cfg.ExtraPackages {
		if !packagePattern.MatchString(pkg) {
			return fmt.Errorf("cloudinit: package %q is not a Debian package name", pkg)
		}
	}
	return nil
}

// quote renders s as a YAML double-quoted scalar; JSON strings are valid YAML.
func quote(s string) string {
	data, err := json.Marshal(s)
	if err != nil {
		// json.Marshal of a string cannot fail; the fallback still yields a scalar.
		return `""`
	}
	return string(data)
}

// GenerateUserData renders hardened cloud-init YAML user-data.
func GenerateUserData(cfg Config) (string, error) {
	if err := Validate(cfg); err != nil {
		return "", err
	}
	cfg = normalize(cfg)

	var sb strings.Builder
	sb.WriteString("#cloud-config\n")
	sb.WriteString("# Lusoris Hardened Cloud-Init User-Data\n\n")

	fmt.Fprintf(&sb, "hostname: %s\n", quote(cfg.Hostname))
	fmt.Fprintf(&sb, "fqdn: %s\n", quote(cfg.Hostname+".local"))
	sb.WriteString("manage_etc_hosts: true\n\n")

	appendUser(&sb, cfg)

	sb.WriteString("ssh_pwauth: false\n")
	sb.WriteString("disable_root: true\n\n")

	fmt.Fprintf(&sb, "timezone: %s\n\n", quote(cfg.Timezone))

	sb.WriteString("growpart:\n")
	sb.WriteString("  mode: auto\n")
	sb.WriteString("  devices: ['/']\n")
	sb.WriteString("  ignore_growroot_disabled: false\n\n")

	appendPlatformUserData(&sb, cfg.Platform)

	if len(cfg.ExtraPackages) > 0 {
		sb.WriteString("packages:\n")
		for _, pkg := range cfg.ExtraPackages {
			fmt.Fprintf(&sb, "  - %s\n", quote(pkg))
		}
		sb.WriteString("\n")
	}

	sb.WriteString("final_message: \"The Lusoris system is up, after $UPTIME seconds.\"\n")
	return sb.String(), nil
}

func appendUser(sb *strings.Builder, cfg Config) {
	sb.WriteString("users:\n")
	fmt.Fprintf(sb, "  - name: %s\n", quote(cfg.User))
	sb.WriteString("    gecos: Lusoris Operator\n")
	sb.WriteString("    sudo: ALL=(ALL) NOPASSWD:ALL\n")
	sb.WriteString("    groups: [adm, audio, cdrom, dialout, floppy, video, plugdev, dip, netdev, render, sudo]\n")
	sb.WriteString("    shell: /bin/bash\n")
	sb.WriteString("    lock_passwd: true\n")

	if len(cfg.SSHAuthorizedKeys) > 0 {
		sb.WriteString("    ssh_authorized_keys:\n")
		for _, key := range cfg.SSHAuthorizedKeys {
			if strings.TrimSpace(key) != "" {
				fmt.Fprintf(sb, "      - %s\n", quote(strings.TrimSpace(key)))
			}
		}
	}
	sb.WriteString("\n")
}

func appendPlatformUserData(sb *strings.Builder, platform string) {
	switch platform {
	case "unraid":
		sb.WriteString("mounts:\n")
		sb.WriteString("  - [ share, /mnt/share, virtiofs, \"rw,sync\", \"0\", \"0\" ]\n\n")
	case "truenas":
		sb.WriteString("mounts:\n")
		sb.WriteString("  - [ nfs_share, /mnt/truenas, nfs, \"rw,hard,intr,noatime\", \"0\", \"0\" ]\n\n")
		sb.WriteString("write_files:\n")
		sb.WriteString("  - path: /etc/udev/rules.d/99-truenas-virtio.rules\n")
		sb.WriteString("    content: |\n")
		sb.WriteString("      ACTION==\"add|change\", SUBSYSTEM==\"block\", KERNEL==\"sd[a-z]|vd[a-z]\", ATTR{queue/discard_max_bytes}!=\"0\", ATTR{queue/discard_granularity}!=\"0\"\n\n")
	case "macos", "utm":
		sb.WriteString("mounts:\n")
		sb.WriteString("  - [ workspace, /mnt/workspace, virtiofs, \"rw,sync\", \"0\", \"0\" ]\n\n")
	case "windows", "hyperv":
		sb.WriteString("write_files:\n")
		sb.WriteString("  - path: /etc/modules-load.d/hyperv.conf\n")
		sb.WriteString("    content: |\n")
		sb.WriteString("      hv_vmbus\n      hv_storvsc\n      hv_netvsc\n      hv_utils\n\n")
	}
}

// GenerateMetaData renders cloud-init meta-data.
func GenerateMetaData(cfg Config) (string, error) {
	cfg = normalize(cfg)
	if err := validateIdentity(cfg); err != nil {
		return "", err
	}
	var sb strings.Builder
	fmt.Fprintf(&sb, "instance-id: %s\n", quote(cfg.Hostname+"-01"))
	fmt.Fprintf(&sb, "local-hostname: %s\n", quote(cfg.Hostname))
	return sb.String(), nil
}
