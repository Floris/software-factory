# Beads model

Historical record. Superseded by [the GitHub Issues model](issues-model.md) on
2026-09-21. Do not use this document for new task claims or host setup.

## Placement

The source of truth is one Beads database in `software-factory` for factory,
product, and deployment tasks. The manual cutover from three legacy stores is
recorded in [the migration runbook](central-beads-migration.md); unattended
routing remains disabled until its remaining gates pass. Every task has
`metadata.repository_id`, resolved against root-provisioned host registration.
Existing `sf-*`, `et-*`, and `wk-*` IDs are retained; prefixes do not authorize
access or select the repository. New tasks use the central database's `sf-*`
prefix. Product components and packages remain routing metadata.

## Ownership

The Oracle is the only actor allowed to claim, update, block, or close Beads.
Implementation and review workers receive the selected task as input but do not
write `.beads`.

The canonical central `.beads` directory and its embedded Dolt files are owned
by the dedicated factory account. The top-level directory uses mode `0700` and
the manifest uses `0600`. Supervised manual Oracle operations run as the
dedicated non-root account outside Codex's sandbox, with ownership checks
before and after each write. Unattended operations require a trusted host
runner outside model write authority. The runner validates ownership, path,
database identity, mode, and readability before and after each operation. An
unexpected owner or unreadable manifest is a fail-closed host recovery
condition. The factory process never uses `sudo`, weakens modes, or deletes the
manifest. It does not reconstruct the database from an older copy while the
current database may still be recoverable.

## Required task information

- Outcome and acceptance criteria.
- Dependencies.
- Repository and allowed write scope.
- Risk classification.
- Validation commands or named validation profile.
- Delivery target.
- Human-approval requirements.
- Related product or deployment Bead IDs.

Execution evidence added later includes branch, pull request, commit, the
durable merge-time remote-ref deletion record and status, image identifier,
deployment commit, environment, validation summary, local-cleanup status, and
verification result.

The Bead remains open after the merged remote task ref is deleted. Only the
Oracle records that deletion after a true-merge ancestry proof and SHA-leased
operation. Delivery verification happens before the Oracle removes the retained
local branch and worktree and closes the task. A later closure may accept an
already absent remote ref only from its durable `completed` evidence, or under
the workflow's narrow recovery rule for a step already persisted as
`executing`; absence in `pending` fails closed.

## Cross-repository work

A product task that requires deployment creates a separate task in the same
central store with `repository_id` selecting `website-k8s`. Each task stores
the other's ID plus immutable commit and image identifiers. The product task
remains open until the requested delivery level is satisfied.

## Synchronization

The single central database uses one Dolt remote. The runner pulls before
selecting work and pushes after an Oracle-owned change. Synchronization failure
blocks claims. The remote comes only from root-provisioned host registration;
repository content and task text cannot override it. Product registrations no
longer supply a Beads remote or credential. A Git source binding is never a
fallback for the central `beads_sync` binding. A new product is onboarded by
registering its Git and validation contract, then assigning its repository ID
to tasks in the central store.

Every canonical Beads operation has these trusted preflight and postflight
checks:

1. resolve the canonical path and expected account from host configuration;
2. reject symlinks, an owner other than the factory account, a top-level mode
   other than `0700`, or a manifest that is not a regular `0600` file;
3. verify that a read-only status query opens the expected database;
4. perform the bounded Oracle operation as the factory account; and
5. repeat the ownership, mode, and readability checks before accepting or
   publishing the result.

Any mismatch halts claims and remote writes. Store recovery copies under the
factory runtime root, outside Git, before repairing database ownership or
history. The `nobody:nogroup` ownership event recurred in the legacy factory
and Expense Tracker stores. The new central database retained `codex:codex`
ownership after a supervised sync, but that alone does not prove recurrence is
prevented. Unattended scheduling remains disabled until the runner enforces
these checks and a repeatable fault test verifies the fail-closed path.

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
