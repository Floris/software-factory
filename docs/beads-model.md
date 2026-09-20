# Beads model

## Placement

- This repository tracks work needed to build and operate the factory.
- Each product repository tracks its own product work.
- `website-k8s` tracks deployment and infrastructure work.

Do not maintain a central duplicate of all product tasks. The factory discovers
only repositories explicitly registered by the operator and queries each
repository's canonical Beads database. A multi-component product still has one
product Beads database; components and packages are routing metadata, not
separate task stores.

## Public projection

Public visibility is an optional derived projection, not a second Beads
database. Registration and policy default it off. The Oracle may export only a
repository explicitly enabled with a public alias and display name. It creates
fields from the public allowlist rather than copying raw `bd` output.

A canonical task is excluded unless the root-provisioned, operator-owned
public-copy manifest maps its exact normalized repository identity and
canonical Bead ID to content-bound public ID, title, and summary values. There
is no repository-wide or task-metadata approval path. Canonical titles and
purported public fields in Beads are not assumed safe. Bodies and descriptions,
acceptance criteria, comments and notes, owners and assignees, email addresses,
internal labels and metadata, external references, paths and remotes, commands,
logs, evidence, credentials, and arbitrary URLs never enter the projection.
Relationships are projected only when both tasks are public.

The public status is an observation, not execution evidence. In particular,
`in_progress` does not prove that a worker is live. The last successful sync
time and staleness state must be displayed with it. The public snapshot cannot
be used to claim, update, block, or close work.

The manifest's monotonic authorization revision and content digest bind every
candidate. Under the exclusive lock, revocation advances the revision and
conditionally replaces the preprovisioned object with a newly authorized or
valid empty snapshot before confirming cache invalidation. Even when canonical
Beads is unavailable, a stale task survives only while its exact approval
remains current.

## Ownership

The Oracle is the only actor allowed to claim, update, block, or close Beads.
Implementation and review workers receive the selected task as input but do not
write `.beads`.

Each canonical `.beads` directory and its embedded Dolt files are owned by the
dedicated factory account. The top-level directory uses mode `0700`. An
unexpected owner or an unreadable Dolt manifest is a fail-closed host recovery
condition: the runner stops before changing task state, preserves the database,
and asks an operator to repair only the affected path. The factory process never
uses `sudo`, weakens the directory mode, deletes the manifest, or reconstructs
the database from an older copy while the current database may still be
recoverable.

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

A product task that requires deployment creates a separate deployment task in
`website-k8s`. Each task stores the other's ID plus immutable commit and image
identifiers. The product task remains open until the requested delivery level
is satisfied.

## Synchronization

Each canonical Beads database uses its own Dolt remote. A runner pulls before
selecting work and pushes after an Oracle-owned state change. Failure to
synchronize blocks new claims rather than allowing divergent work state.

Repository IDs, canonical paths, normalized Git repository identities/remotes,
and Beads remote identities must each be unique across entries in
root-provisioned host configuration. Each repository declares exactly one
default branch, but a branch name is not a global identity: multiple
repositories may validly use `main` or another identical branch name. Reusing
one Beads remote for multiple product repositories, falling back to a central
database, or accepting a remote discovered from untrusted repository content
is forbidden. New repository onboarding proves the same ownership, mode,
readability, and pull/check/push invariants before that repository contributes
ready work.

The Oracle resolves the Dolt remote from root-provisioned
`/etc/software-factory/repositories.yaml`. Do not commit the canonical remote
to a product repository's tracked `.beads/config.yaml`. The trusted runner
configures the local database at onboarding, and only the exact repository's
`beads_sync` credential binding receives permission to publish that remote
state. A Git source binding or another repository's Beads binding is never a
fallback.

Bootstrap an empty remote explicitly from trusted repository configuration:

1. initialize the local database as the factory account;
2. add the repository's Dolt remote when none is configured;
3. push the existing local history once to create the remote branch; and
4. run the normal pull, conflict check, blocked-state repair, and push cycle.

Do not begin bootstrap with a pull from an empty remote. Do not force-push a
Dolt remote during normal operation. Do not copy another repository's database
to bootstrap a new product. Every canonical Beads operation has these trusted
preflight and postflight checks:

1. resolve the canonical path and expected account from host configuration;
2. reject symlinks, an owner other than the factory account, a top-level mode
   other than `0700`, or a manifest that is not a regular `0600` file;
3. verify that a read-only status query opens the expected database;
4. perform the bounded Oracle operation as the factory account; and
5. repeat the ownership, mode, and readability checks before accepting or
   publishing the result.

Any mismatch halts claims and remote writes. Store recovery copies under the
factory runtime root, outside Git, before repairing database ownership or
history. The original `nobody:nogroup` ownership event was not attributable
from retained logs, so unattended scheduling remains disabled until the runner
enforces these checks and a repeatable fault test verifies the fail-closed
path.

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
