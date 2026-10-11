# Global Anycast NTS Time Architecture

Network Time Security (NTS) provides cryptographic authentication for the Network Time Protocol (NTP) using TLS 1.3 (RFC 8915). It prevents man-in-the-middle time manipulation attacks.

## Multi-Tiered Topology

`lusoris-cloud-images` implements a fault-tolerant multi-tier NTS topology configured in `/etc/chrony/sources.d/global-nts.sources`:

1. **Tier 1: Global Anycast NTS**
   - `server time.cloudflare.com iburst nts`
   - Provides worldwide single-digit millisecond latency via Anycast routing.
2. **Tier 2: European Stratum-1 National Metrology Institutes**
   - `ptbtime1.ptb.de` & `ptbtime2.ptb.de` (Physikalisch-Technische Bundesanstalt, Germany)
   - `nts.netnod.se` (Netnod, Sweden)
   - `ntp.time.nl` (SIDN Labs, Netherlands)
   - `ntp.3eck.net` (Switzerland)
3. **Tier 3: Graceful Fallback Pool**
   - `pool 2.ubuntu.pool.ntp.org iburst maxsources 4`
   - Ensures time synchronization continues without failure if an enterprise network firewall blocks TCP port 4460 (NTS-KE).

```mermaid
flowchart TD
    %% Semantic class definitions with vibrant, high-contrast jewel palettes
    classDef client fill:#0284c7,stroke:#0369a1,stroke-width:2px,color:#ffffff
    classDef ke fill:#7c3aed,stroke:#6d28d9,stroke-width:2px,color:#ffffff
    classDef anycast fill:#059669,stroke:#047857,stroke-width:2px,color:#ffffff
    classDef atomic fill:#d97706,stroke:#b45309,stroke-width:2px,color:#ffffff
    classDef fallback fill:#334155,stroke:#1e293b,stroke-width:2px,color:#ffffff

    subgraph Client["Lusoris Guest OS (chrony daemon)"]
        Chrony["chrony (authselectmode mix)"]:::client
        Step["makestep 1.0 3 · minsources 3"]:::client
    end

    subgraph SecurityExchange["NTS Key Establishment (TLS 1.3 · TCP 4460)"]
        KE["NTS-KE Exchange<br/><small>AEAD Key & Cookie Negotiation</small>"]:::ke
    end

    subgraph TimeSources["Multi-Tiered Stratum-1 Time Infrastructure"]
        subgraph Tier1["Tier 1: Global Anycast NTS"]
            CF["time.cloudflare.com<br/><small>Anycast Edge Routing</small>"]:::anycast
        end

        subgraph Tier2["Tier 2: European Metrology Institutes (Atomic Clocks)"]
            PTB["PTB Germany<br/><small>ptbtime1.ptb.de · ptbtime2.ptb.de</small>"]:::atomic
            Netnod["Netnod Sweden<br/><small>nts.netnod.se</small>"]:::atomic
            SIDN["SIDN Netherlands<br/><small>ntp.time.nl</small>"]:::atomic
            Dreck["3eck Switzerland<br/><small>ntp.3eck.net</small>"]:::atomic
        end

        subgraph Tier3["Tier 3: Graceful NTP Fallback"]
            Pool["2.ubuntu.pool.ntp.org<br/><small>UDP 123 Fallback if TCP 4460 Blocked</small>"]:::fallback
        end
    end

    Chrony -->|TCP 4460 TLS 1.3| KE
    KE -->|Encrypted Cookies| Chrony
    Chrony -->|Authenticated UDP 123| CF & PTB & Netnod & SIDN & Dreck
    Chrony -.->|Unauthenticated UDP 123 Fallback| Pool

    style Client fill:none,stroke:#0284c7,stroke-width:2px,stroke-dasharray: 4 4
    style SecurityExchange fill:none,stroke:#7c3aed,stroke-width:2px,stroke-dasharray: 4 4
    style TimeSources fill:none,stroke:#64748b,stroke-width:2px
    style Tier1 fill:none,stroke:#059669,stroke-width:2px,stroke-dasharray: 4 4
    style Tier2 fill:none,stroke:#d97706,stroke-width:2px,stroke-dasharray: 4 4
    style Tier3 fill:none,stroke:#334155,stroke-width:2px,stroke-dasharray: 4 4
```

---

## Chrony Policy (`/etc/chrony/conf.d/global-policy.conf`)

- `authselectmode mix`: Prefers cryptographically authenticated NTS sources, gracefully falling back to standard NTP if NTS is unreachable.
- `makestep 1.0 3`: Steps the system clock if offset is greater than 1 second in the first 3 clock updates.
- `minsources 3`: Mandates at least 3 active sources for consensus before steering time.
