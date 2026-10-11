# ADR 0002: Multi-Tiered Global Anycast & Stratum-1 NTS Topology

## Status

Accepted

## Context

Initial images hardcoded German PTB NTS servers with `authselectmode require`. For users in North America, Asia, or on enterprise firewalls blocking port 4460 (NTS-KE), this introduced high latency or outright failure to sync time.

## Decision

We implement a 3-tier time synchronization architecture in `10-network-time.sh`:

- Tier 1: Anycast NTS (`time.cloudflare.com`) for worldwide low latency.
- Tier 2: European Stratum-1 NTS (PTB, Netnod, SIDN, 3eck).
- Tier 3: NTP fallback pool (`2.ubuntu.pool.ntp.org`) with `authselectmode mix`.

## Consequences

- Single-digit millisecond latency globally with cryptographically verified time.
- Graceful degradation in airgapped or firewalled environments without failing boot.
