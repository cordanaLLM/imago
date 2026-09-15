// Copyright 2026 Lusoris
// Package mcp wires a Model Context Protocol (MCP) server exposing lusoris-cloud-images
// tool capabilities to AI agents and IDEs.
package mcp

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/golusoris/golusoris/core/clock"
)

// StagedStatus represents the lifecycle state of a staged mutation action.
type StagedStatus string

const (
	StatusPending   StagedStatus = "pending"
	StatusConfirmed StagedStatus = "confirmed"
	StatusDiscarded StagedStatus = "discarded"
)

// StagedAction captures a destructive or environment-mutating tool call
// that requires explicit operator or agent confirmation before execution.
type StagedAction struct {
	ID        string         `json:"id"`
	Tool      string         `json:"tool"`
	Target    string         `json:"target"`
	Payload   map[string]any `json:"payload"`
	Preview   string         `json:"preview"`
	Status    StagedStatus   `json:"status"`
	CreatedAt time.Time      `json:"created_at"`
}

// DefaultStagingTTL represents the maximum lifetime of an unconfirmed or completed staged action before eviction.
const DefaultStagingTTL = 15 * time.Minute

// MaxStagedCapacity defines the maximum number of actions stored before forced eviction of oldest items.
const MaxStagedCapacity = 1000

// Stager provides concurrency-safe tracking of pending operations.
type Stager struct {
	mu      sync.RWMutex
	actions map[string]*StagedAction
	clock   clock.Clock
}

// NewStager constructs an initialized action stager. The clock is injected
// (golusoris core/clock) so TTL pruning is deterministic under test.
func NewStager(c clock.Clock) *Stager {
	return &Stager{
		actions: make(map[string]*StagedAction),
		clock:   c,
	}
}

// Stage registers a new action and returns its staged descriptor.
func (s *Stager) Stage(tool, target string, payload map[string]any, preview string) *StagedAction {
	s.mu.Lock()
	defer s.mu.Unlock()

	if len(s.actions) >= MaxStagedCapacity {
		s.pruneLocked(DefaultStagingTTL)
	}

	id := generateActionID(s.clock)
	act := &StagedAction{
		ID:        id,
		Tool:      tool,
		Target:    target,
		Payload:   payload,
		Preview:   preview,
		Status:    StatusPending,
		CreatedAt: s.clock.Now().UTC(),
	}
	s.actions[id] = act
	return act
}

// Prune removes staged actions whose age exceeds maxAge.
// If maxAge <= 0, DefaultStagingTTL is used. Returns the count of pruned actions.
func (s *Stager) Prune(maxAge time.Duration) int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.pruneLocked(maxAge)
}

func (s *Stager) pruneLocked(maxAge time.Duration) int {
	if maxAge <= 0 {
		maxAge = DefaultStagingTTL
	}
	cutoff := s.clock.Now().UTC().Add(-maxAge)
	pruned := 0
	for id, act := range s.actions {
		if act.CreatedAt.Before(cutoff) {
			delete(s.actions, id)
			pruned++
		}
	}
	return pruned
}

// Get retrieves a staged action by ID.
func (s *Stager) Get(id string) (*StagedAction, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	act, ok := s.actions[id]
	if !ok {
		return nil, fmt.Errorf("staged action %q not found", id)
	}
	return act, nil
}

// List returns a snapshot copy of all staged actions.
func (s *Stager) List() []*StagedAction {
	s.mu.RLock()
	defer s.mu.RUnlock()

	out := make([]*StagedAction, 0, len(s.actions))
	for _, a := range s.actions {
		out = append(out, a)
	}
	return out
}

// Confirm marks a pending action as confirmed.
func (s *Stager) Confirm(id string) (*StagedAction, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	act, ok := s.actions[id]
	if !ok {
		return nil, fmt.Errorf("staged action %q not found", id)
	}
	if act.Status != StatusPending {
		return nil, fmt.Errorf("staged action %q cannot be confirmed (current status: %s)", id, act.Status)
	}
	act.Status = StatusConfirmed
	return act, nil
}

// Discard removes or marks a pending action as discarded.
func (s *Stager) Discard(id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	act, ok := s.actions[id]
	if !ok {
		return errors.New("staged action not found")
	}
	act.Status = StatusDiscarded
	delete(s.actions, id)
	return nil
}

func generateActionID(c clock.Clock) string {
	b := make([]byte, 4)
	if _, err := rand.Read(b); err != nil {
		return fmt.Sprintf("act-%d", c.Now().UnixNano()%1000000)
	}
	return fmt.Sprintf("act-%s", hex.EncodeToString(b))
}
