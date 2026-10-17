// Copyright 2026 Lusoris
// Package builder validates image build plans for local Packer and self-hosted
// or cloud CI backends. Execution requires an explicitly registered executor;
// a dry run reports a plan without execution.
package builder

import (
	"context"
	"errors"
	"fmt"
	"slices"
	"time"

	"github.com/cordanaLLM/imago/pkg/flavors"
)

// Backend identifies the execution target.
type Backend string

const (
	BackendLocal      Backend = "local"
	BackendGitea      Backend = "gitea"
	BackendProxmox    Backend = "proxmox"
	BackendGitLab     Backend = "gitlab"
	BackendWoodpecker Backend = "woodpecker"
	BackendHarbor     Backend = "harbor"
	BackendMinIO      Backend = "minio"
	BackendJenkins    Backend = "jenkins"
	BackendGitHub     Backend = "github"
)

// Status values a Result carries once the request passed validation.
const (
	// StatusPlanned marks a validated dry run; nothing was executed.
	StatusPlanned = "planned"
	// StatusUnavailable marks a request whose backend has no executor.
	StatusUnavailable = "unavailable"
	// StatusSucceeded marks a completed build with artifact evidence.
	StatusSucceeded = "succeeded"
)

// Request defines the build parameters.
type Request struct {
	Backend    Backend       `json:"backend"`
	Flavor     string        `json:"flavor"`
	Endpoint   string        `json:"endpoint,omitempty"`
	AuthToken  string        `json:"-"`
	Repository string        `json:"repository,omitempty"`
	Ref        string        `json:"ref,omitempty"`
	DryRun     bool          `json:"dry_run"`
	Timeout    time.Duration `json:"timeout"`
}

// Result describes a plan, refusal, or execution backed by artifact evidence.
type Result struct {
	Backend        Backend `json:"backend"`
	Flavor         string  `json:"flavor"`
	Success        bool    `json:"success"`
	Status         string  `json:"status"`
	DryRun         bool    `json:"dry_run"`
	Message        string  `json:"message"`
	RunLog         string  `json:"run_log,omitempty"`
	Artifact       string  `json:"artifact,omitempty"`
	ArtifactSHA256 string  `json:"artifact_sha256,omitempty"`
}

// ErrBackendUnavailable identifies a known backend without an executor.
var ErrBackendUnavailable = errors.New("build backend not implemented")

// BackendUnavailableError names the backend a build request needed.
type BackendUnavailableError struct {
	Backend Backend
}

func (e *BackendUnavailableError) Error() string {
	return fmt.Sprintf("builder: backend %q: %v", e.Backend, ErrBackendUnavailable)
}

// Unwrap supports errors.Is with ErrBackendUnavailable.
func (e *BackendUnavailableError) Unwrap() error {
	return ErrBackendUnavailable
}

// backends lists every backend Validate accepts.
var backends = []Backend{
	BackendLocal, BackendGitea, BackendProxmox, BackendGitLab, BackendWoodpecker,
	BackendHarbor, BackendMinIO, BackendJenkins, BackendGitHub,
}

// Validate refuses an unknown flavor or backend. Dispatch calls it before a dry
// run too, and the MCP server calls it before staging a build for confirmation.
func Validate(backend Backend, flavor string) error {
	if _, err := flavors.Get(flavor); err != nil {
		return fmt.Errorf("builder: invalid flavor: %w", err)
	}
	if !slices.Contains(backends, backend) {
		return fmt.Errorf("builder: unsupported backend %q", backend)
	}
	return nil
}

// Executor performs a validated build request.
type Executor interface {
	Execute(context.Context, Request) (Result, error)
}

// Dispatch preserves the refusal-only default; no executor is registered.
func Dispatch(ctx context.Context, req Request) (Result, error) {
	return DispatchWith(ctx, req, nil)
}

// DispatchWith validates before planning or invoking an explicitly registered executor.
func DispatchWith(ctx context.Context, req Request, executors map[Backend]Executor) (Result, error) {
	res := Result{Backend: req.Backend, Flavor: req.Flavor, DryRun: req.DryRun}
	if err := ctx.Err(); err != nil {
		return res, fmt.Errorf("builder: request context: %w", err)
	}
	if err := Validate(req.Backend, req.Flavor); err != nil {
		return res, err
	}
	if req.DryRun {
		res.Status = StatusPlanned
		res.Message = fmt.Sprintf("dry-run: validated plan for flavor %q on backend %q; no build was executed", req.Flavor, req.Backend)
		return res, nil
	}
	if executor := executors[req.Backend]; executor != nil {
		return executor.Execute(ctx, req)
	}
	err := &BackendUnavailableError{Backend: req.Backend}
	res.Status = StatusUnavailable
	res.Message = err.Error()
	return res, err
}
