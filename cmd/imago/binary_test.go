// Copyright 2026 Lusoris
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"sync"
	"testing"
	"time"

	sdkmcp "github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Tests that start the built imago program the way a user or an MCP client does,
// instead of calling newRootCmd in-process: the exit code, the stream each message
// lands on and the stdio framing of `imago mcp` are visible only from outside.

const (
	buildDeadline = 5 * time.Minute
	runDeadline   = time.Minute
)

var (
	binaryOnce sync.Once
	binaryDir  string
	binaryPath string
	binaryErr  error
)

func TestMain(m *testing.M) {
	code := m.Run()
	if binaryDir != "" {
		_ = os.RemoveAll(binaryDir)
	}
	os.Exit(code)
}

// imagoBinary builds the program once per test run and returns its path.
func imagoBinary(t *testing.T) string {
	t.Helper()
	binaryOnce.Do(func() {
		binaryDir, binaryErr = os.MkdirTemp("", "imago-bin-")
		if binaryErr != nil {
			return
		}
		name := "imago"
		if runtime.GOOS == "windows" {
			name += ".exe"
		}
		binaryPath = filepath.Join(binaryDir, name)
		ctx, cancel := context.WithTimeout(context.Background(), buildDeadline)
		defer cancel()
		out, err := exec.CommandContext(ctx, "go", "build", "-o", binaryPath, ".").CombinedOutput()
		if err != nil {
			binaryErr = fmt.Errorf("go build: %w\n%s", err, out)
		}
	})
	require.NoError(t, binaryErr)
	return binaryPath
}

// lockedBuffer collects a child's stderr; exec copies into it from its own goroutine
// while the test may read it for a failure message.
type lockedBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (b *lockedBuffer) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.Write(p)
}

func (b *lockedBuffer) String() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.String()
}

type runResult struct {
	stdout, stderr string
	code           int
}

// runImago runs the built program from the repository root with no input.
func runImago(t *testing.T, args ...string) runResult {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), runDeadline)
	defer cancel()
	cmd := exec.CommandContext(ctx, imagoBinary(t), args...)
	cmd.Dir = repoRoot(t)
	var stdout, stderr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	err := cmd.Run()
	res := runResult{stdout: stdout.String(), stderr: stderr.String()}
	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) {
		res.code = exitErr.ExitCode()
		return res
	}
	require.NoError(t, err, "imago did not run to completion")
	return res
}

func TestBinaryHelp(t *testing.T) {
	res := runImago(t, "--help")
	assert.Equal(t, 0, res.code)
	assert.Contains(t, res.stdout, "Imago — Unified CLI & AI MCP Server")
	assert.Empty(t, res.stderr)
}

func TestBinaryFlavorsListJSON(t *testing.T) {
	res := runImago(t, "flavors", "list", "--json")
	require.Equal(t, 0, res.code, res.stderr)
	var list []struct {
		ID string `json:"id"`
	}
	require.NoError(t, json.Unmarshal([]byte(res.stdout), &list), "stdout is not one JSON document")
	assert.Len(t, list, 44)
	assert.Equal(t, "base-generic", list[0].ID)
}

func TestBinaryUnknownCommandFails(t *testing.T) {
	res := runImago(t, "no-such-command")
	assert.Equal(t, 1, res.code)
	assert.Contains(t, res.stderr, `unknown command "no-such-command"`)
	assert.Empty(t, res.stdout)
}

func TestBinaryUnknownFlagFails(t *testing.T) {
	res := runImago(t, "flavors", "list", "--invalid-flag")
	assert.Equal(t, 1, res.code)
	assert.Contains(t, res.stderr, "unknown flag: --invalid-flag")
}

func TestBinaryMCPRefusesUnknownTransport(t *testing.T) {
	res := runImago(t, "mcp", "--transport", "carrier-pigeon")
	assert.NotEqual(t, 0, res.code)
	assert.Contains(t, res.stderr, `unknown transport "carrier-pigeon"`)
	assert.Empty(t, res.stdout, "a refused start must not write to the protocol stream")
}

// TestBinaryMCPOverStdio speaks JSON-RPC to `imago mcp` over its stdin and stdout, as
// an editor does. A log line or stray print on stdout breaks the framing and fails the
// handshake.
func TestBinaryMCPOverStdio(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), runDeadline)
	defer cancel()
	cmd := exec.CommandContext(ctx, imagoBinary(t), "mcp")
	cmd.Dir = repoRoot(t)
	stderr := new(lockedBuffer)
	cmd.Stderr = stderr

	client := sdkmcp.NewClient(&sdkmcp.Implementation{Name: "binary-test", Version: "1.0.0"}, nil)
	session, err := client.Connect(ctx, &sdkmcp.CommandTransport{Command: cmd, TerminateDuration: 5 * time.Second}, nil)
	require.NoError(t, err, "handshake failed; stderr:\n%s", stderr.String())

	init := session.InitializeResult()
	require.NotNil(t, init)
	assert.Equal(t, "imago", init.ServerInfo.Name)

	tools, err := session.ListTools(ctx, nil)
	require.NoError(t, err)
	names := make([]string, 0, len(tools.Tools))
	for _, tool := range tools.Tools {
		names = append(names, tool.Name)
	}
	sort.Strings(names)
	assert.Equal(t, []string{
		"apply_flavor", "confirm_action", "discard_staged_action", "generate_cloudinit",
		"get_flavor", "get_milestones", "get_standards", "inspect_compliance",
		"list_epics", "list_flavors", "list_staged_actions", "route_plan",
		"trigger_build", "validate_manifest",
	}, names)

	res, err := session.CallTool(ctx, &sdkmcp.CallToolParams{
		Name:      "get_flavor",
		Arguments: map[string]any{"flavor_id": "base-generic"},
	})
	require.NoError(t, err)
	assert.False(t, res.IsError)
	require.NotEmpty(t, res.Content)
	assert.Contains(t, res.Content[0].(*sdkmcp.TextContent).Text, "00-base-strip.sh")

	require.NoError(t, session.Close(), "server did not stop when the client closed stdin")
}
