# ADR 0002: Use one factory Beads task store

- Status: Accepted; operational cutover pending
- Date: 2026-09-21

## Context

Separate Beads databases in the factory, product, and GitOps repositories make
claims and cross-repository work harder to reconcile. The factory and Expense
Tracker embedded Dolt manifests are currently unreadable because they are owned
by `nobody:nogroup`. Moving tasks alone does not prevent that ownership fault.

## Decision

Use the `software-factory` Beads database as the only authoritative task store
for factory, product, and deployment work. Each issue has a `repository_id` in
its metadata. The Oracle resolves that ID against the root-provisioned repository
allowlist before using a path, validation profile, or credential. Existing
`sf-*`, `et-*`, and `wk-*` IDs remain stable; prefixes are historical identity,
not routing authority. New issues use the central database's `sf-*` prefix.

One trusted non-root host runner owns the central database and its Dolt remote.
It runs outside the Codex workspace sandbox and exposes fixed task operations,
not arbitrary Beads commands. It checks canonical path, database identity,
ownership, directory mode, manifest mode, and readability before and after each
write. Codex and delegated workers receive read-only task snapshots. Unexpected
ownership stops writes and publication; repair is an explicit operator action.

The migration is a gated operation: freeze old writes, prove source freshness,
archive each full Dolt history, import issues preserving IDs and relationships,
validate the candidate, then switch host routing under an exclusive lock. Old
databases and remotes remain read-only for audit. The central store is not live
until the cutover and runner fault tests in [the migration runbook](../central-beads-migration.md)
pass.

## Consequences

- Product repositories remain authoritative for application code and tests;
  `website-k8s` remains authoritative for Kubernetes desired state.
- The Oracle queries one task store and validates `repository_id` for each task.
- A single task store reduces routing and synchronization complexity but creates
  one availability boundary; ownership checks, backups, and fail-closed recovery
  are required.
- The earlier per-repository Beads placement in the architecture and workflow
  documentation is superseded only after the operational cutover. Until then,
  no new claims are made from either layout.
