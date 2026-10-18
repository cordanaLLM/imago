// Copyright 2026 Lusoris
// Package cloudinit generates hardened cloud-init user-data and meta-data
// across virtualization platforms and developer workstations.
package cloudinit

import (
	"bytes"
	"fmt"
	"regexp"
	"strings"

	"github.com/cordanaLLM/imago/pkg/flavors"
	"go.yaml.in/yaml/v3"
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

// userDataHeader precedes the encoded document; cloud-init requires the first line.
const userDataHeader = "#cloud-config\n# Lusoris Hardened Cloud-Init User-Data\n"

// userDataDoc is the user-data document; field order is the emitted key order.
type userDataDoc struct {
	Hostname       string           `yaml:"hostname"`
	FQDN           string           `yaml:"fqdn"`
	ManageEtcHosts bool             `yaml:"manage_etc_hosts"`
	Users          []userDataUser   `yaml:"users"`
	SSHPwauth      bool             `yaml:"ssh_pwauth"`
	DisableRoot    bool             `yaml:"disable_root"`
	Timezone       string           `yaml:"timezone"`
	Growpart       userDataGrowpart `yaml:"growpart"`
	Mounts         [][]string       `yaml:"mounts,omitempty"`
	WriteFiles     []userDataFile   `yaml:"write_files,omitempty"`
	Packages       []string         `yaml:"packages,omitempty"`
	FinalMessage   string           `yaml:"final_message"`
}

type userDataUser struct {
	Name              string   `yaml:"name"`
	Gecos             string   `yaml:"gecos"`
	Sudo              string   `yaml:"sudo"`
	Groups            []string `yaml:"groups,flow"`
	Shell             string   `yaml:"shell"`
	LockPasswd        bool     `yaml:"lock_passwd"`
	SSHAuthorizedKeys []string `yaml:"ssh_authorized_keys,omitempty"`
}

type userDataGrowpart struct {
	Mode                   string   `yaml:"mode"`
	Devices                []string `yaml:"devices,flow"`
	IgnoreGrowrootDisabled bool     `yaml:"ignore_growroot_disabled"`
}

type userDataFile struct {
	Path    string `yaml:"path"`
	Content string `yaml:"content"`
}

// metaDataDoc is the NoCloud meta-data document.
type metaDataDoc struct {
	InstanceID    string `yaml:"instance-id"`
	LocalHostname string `yaml:"local-hostname"`
}

func buildUser(cfg Config) userDataUser {
	u := userDataUser{
		Name:       cfg.User,
		Gecos:      "Lusoris Operator",
		Sudo:       "ALL=(ALL) NOPASSWD:ALL",
		Groups:     []string{"adm", "audio", "cdrom", "dialout", "floppy", "video", "plugdev", "dip", "netdev", "render", "sudo"},
		Shell:      "/bin/bash",
		LockPasswd: true,
	}
	for _, key := range cfg.SSHAuthorizedKeys {
		if trimmed := strings.TrimSpace(key); trimmed != "" {
			u.SSHAuthorizedKeys = append(u.SSHAuthorizedKeys, trimmed)
		}
	}
	return u
}

func platformUserData(platform string) ([][]string, []userDataFile) {
	switch platform {
	case "unraid":
		return [][]string{{"share", "/mnt/share", "virtiofs", "rw,sync", "0", "0"}}, nil
	case "truenas":
		return [][]string{{"nfs_share", "/mnt/truenas", "nfs", "rw,hard,intr,noatime", "0", "0"}},
			[]userDataFile{{
				Path:    "/etc/udev/rules.d/99-truenas-virtio.rules",
				Content: "ACTION==\"add|change\", SUBSYSTEM==\"block\", KERNEL==\"sd[a-z]|vd[a-z]\", ATTR{queue/discard_max_bytes}!=\"0\", ATTR{queue/discard_granularity}!=\"0\"\n",
			}}
	case "macos", "utm":
		return [][]string{{"workspace", "/mnt/workspace", "virtiofs", "rw,sync", "0", "0"}}, nil
	case "windows", "hyperv":
		return nil, []userDataFile{{
			Path:    "/etc/modules-load.d/hyperv.conf",
			Content: "hv_vmbus\nhv_storvsc\nhv_netvsc\nhv_utils\n",
		}}
	default:
		return nil, nil
	}
}

func buildUserDataDoc(cfg Config) userDataDoc {
	doc := userDataDoc{
		Hostname:       cfg.Hostname,
		FQDN:           cfg.Hostname + ".local",
		ManageEtcHosts: true,
		Users:          []userDataUser{buildUser(cfg)},
		SSHPwauth:      false,
		DisableRoot:    true,
		Timezone:       cfg.Timezone,
		Growpart: userDataGrowpart{
			Mode:                   "auto",
			Devices:                []string{"/"},
			IgnoreGrowrootDisabled: false,
		},
		FinalMessage: "The Lusoris system is up, after $UPTIME seconds.",
	}
	if len(cfg.ExtraPackages) > 0 {
		doc.Packages = cfg.ExtraPackages
	}
	doc.Mounts, doc.WriteFiles = platformUserData(cfg.Platform)
	return doc
}

func renderUserData(cfg Config) (string, error) {
	cfg = normalize(cfg)
	doc := buildUserDataDoc(cfg)

	var buf bytes.Buffer
	buf.WriteString(userDataHeader)

	enc := yaml.NewEncoder(&buf)
	enc.SetIndent(2)
	if err := enc.Encode(doc); err != nil {
		return "", fmt.Errorf("cloudinit: encode user-data: %w", err)
	}
	if err := enc.Close(); err != nil {
		return "", fmt.Errorf("cloudinit: encode user-data: %w", err)
	}
	return buf.String(), nil
}

// GenerateUserData renders hardened cloud-init YAML user-data.
func GenerateUserData(cfg Config) (string, error) {
	if err := Validate(cfg); err != nil {
		return "", err
	}
	return renderUserData(cfg)
}

func renderMetaData(cfg Config) (string, error) {
	cfg = normalize(cfg)
	doc := metaDataDoc{
		InstanceID:    cfg.Hostname + "-01",
		LocalHostname: cfg.Hostname,
	}

	var buf bytes.Buffer
	enc := yaml.NewEncoder(&buf)
	enc.SetIndent(2)
	if err := enc.Encode(doc); err != nil {
		return "", fmt.Errorf("cloudinit: encode meta-data: %w", err)
	}
	if err := enc.Close(); err != nil {
		return "", fmt.Errorf("cloudinit: encode meta-data: %w", err)
	}
	return buf.String(), nil
}

// GenerateMetaData renders cloud-init meta-data.
func GenerateMetaData(cfg Config) (string, error) {
	cfg = normalize(cfg)
	if err := validateIdentity(cfg); err != nil {
		return "", err
	}
	return renderMetaData(cfg)
}
