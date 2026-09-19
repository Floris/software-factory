# ADR 0001: Use a separate software-factory repository

- Status: Accepted
- Date: 2026-09-19

## Context

The existing `agents-md` repository is the canonical tracked copy of the shared
workspace routing instructions. The software factory needs architecture,
policies, configuration, Beads state, executable orchestration code, services,
and its own release lifecycle.

## Decision

Create `software-factory` as a separate control repository. Keep `agents-md`
small and update it only to route factory-related work to this repository.

## Consequences

- Codex receives concise workspace routing without loading factory internals for
  unrelated tasks.
- Factory policy and implementation evolve together in one auditable repo.
- Product and deployment sources of truth remain unchanged.
- The VPS can clone and update the factory independently of shared workspace
  instruction backups.
