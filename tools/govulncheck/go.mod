// Copyright 2026 Lusoris
// Pins govulncheck for the security-scans workflow, apart from the imago module so
// that its dependencies do not raise the versions imago builds with. Renovate's gomod
// manager updates it. Run from the repository root:
//   go -C tools/govulncheck tool govulncheck -C "$PWD" ./...
module github.com/cordanaLLM/imago/tools/govulncheck

go 1.27.3

tool golang.org/x/vuln/cmd/govulncheck

require (
	golang.org/x/mod v0.42.0 // indirect
	golang.org/x/sync v0.24.0 // indirect
	golang.org/x/sys v0.49.0 // indirect
	golang.org/x/telemetry v0.0.0-20261010193011-f71dc92da45e // indirect
	golang.org/x/tools v0.52.0 // indirect
	golang.org/x/vuln v1.9.0 // indirect
)
