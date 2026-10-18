// Copyright 2026 Lusoris

// Package imago provides root schemas and coordinates for the Lusoris cloud image engine.
package imago

import _ "embed"

// VersionsSchema holds the raw JSON Schema validating versions.json.
//
//go:embed versions.schema.json
var VersionsSchema []byte
