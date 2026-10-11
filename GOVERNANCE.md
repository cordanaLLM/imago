# Project Governance

## Overview

`lusoris-cloud-images` is an open-source project driven by community contributors and maintainers. This document outlines how decisions are made, how maintainership is earned, and how architectural directions are established.

## Decision Making & Architecture Decision Records (ADRs)

- Routine enhancements and bug fixes are decided via standard GitHub Pull Request review and approval by at least one Maintainer.
- Substantial architectural shifts, changes to invariants, or new flavor dimensions must be proposed as an **Architecture Decision Record (ADR)** in `docs/adr/`.
- Once an ADR is approved and merged, its status changes to `Accepted` and its text becomes immutable. Future directional changes require a superseding ADR.

## Maintainer Roles & Responsibilities

- **Maintainers**: Responsible for reviewing PRs, maintaining CI/CD quality gates, triage of issues, security releases, and release tagging.
- **Contributors**: Anyone who submits code, documentation, bug reports, or helps answer questions in community discussions.

## Becoming a Maintainer

Active contributors who consistently demonstrate:

1. Deep adherence to project quality gates (NASA/JPL Power of 10, clean ShellCheck, declarative source of truth).
2. Constructive, collaborative code reviews.
3. Sustained contributions over several release cycles.

may be nominated by an existing Maintainer.

## Epics, Milestones & PR Hard Gates

- Recurring and cross-cutting architectural work is tracked through declarative epics in [`.github/epics.json`](.github/epics.json) and monthly release milestones in [`.github/milestones.json`](.github/milestones.json).
- Every Pull Request must satisfy automated governance hard gates (`.github/workflows/pr-project-gate.yml`) requiring assignment to an active open milestone, explicit reference to a tracked issue/epic, and appropriate workload/area labels.
