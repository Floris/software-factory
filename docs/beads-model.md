# Beads model

## Placement

- This repository tracks work needed to build and operate the factory.
- Each product repository tracks its own product work.
- `website-k8s` tracks deployment and infrastructure work.

Do not maintain a central duplicate of all product tasks. The factory discovers
configured repositories and queries their canonical Beads databases.

## Ownership

The Oracle is the only actor allowed to claim, update, block, or close Beads.
Implementation and review workers receive the selected task as input but do not
write `.beads`.

## Required task information

- Outcome and acceptance criteria.
- Dependencies.
- Repository and allowed write scope.
- Risk classification.
- Validation commands or named validation profile.
- Delivery target.
- Human-approval requirements.
- Related product or deployment Bead IDs.

Execution evidence added later includes branch, pull request, commit, image
identifier, deployment commit, environment, validation summary, and verification
result.

## Cross-repository work

A product task that requires deployment creates a separate deployment task in
`website-k8s`. Each task stores the other's ID plus immutable commit and image
identifiers. The product task remains open until the requested delivery level
is satisfied.

## Synchronization

Each canonical Beads database uses its own Dolt remote. A runner pulls before
selecting work and pushes after an Oracle-owned state change. Failure to
synchronize blocks new claims rather than allowing divergent work state.

## Initial factory epic

When Beads is initialized on the VPS, create one epic covering:

1. secure VPS bootstrap;
2. repository discovery and configuration validation;
3. read-only ready-work aggregation;
4. atomic claim and worktree creation;
5. Codex structured execution;
6. validation and review;
7. branch and pull-request creation;
8. GitOps handoff and DEV verification;
9. systemd scheduling and recovery.
