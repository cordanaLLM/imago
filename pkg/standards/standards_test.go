// Copyright 2026 Lusoris
package standards_test

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/cordanaLLM/imago/pkg/standards"
)

func TestAllStandardsCount(t *testing.T) {
	stds := standards.All()
	assert.Len(t, stds, 44, "must provide standards for all 44 flavors")
}

func TestGetStandard(t *testing.T) {
	baseStd, err := standards.Get("base-generic")
	require.NoError(t, err)
	assert.Equal(t, "base-generic", baseStd.FlavorID)
	assert.Contains(t, baseStd.RequiredPackages, "chrony")
	assert.Contains(t, baseStd.KernelParameters, "net.ipv4.tcp_congestion_control")

	k8sStd, err := standards.Get("k8s-node-cilium")
	require.NoError(t, err)
	assert.Contains(t, k8sStd.RequiredPackages, "kubelet")
	assert.Equal(t, "1", k8sStd.KernelParameters["net.bridge.bridge-nf-call-iptables"])

	k3sStd, err := standards.Get("k3s-agent-generic")
	require.NoError(t, err)
	assert.Equal(t, 300, k3sStd.MaxIdleMemoryMB)

	dockerNvidiaStd, err := standards.Get("docker-nvidia")
	require.NoError(t, err)
	assert.True(t, dockerNvidiaStd.CDISpecRequired)
}
