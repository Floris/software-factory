# Architecture

## Context

The development worker and the K3s cluster run on the same VPS. This is safe
only when physical co-location does not collapse the control boundaries.
GitHub remains the external authority and audit log, CI produces immutable
artifacts, and ArgoCD reconciles deployment state back onto K3s.

## Component model

```text
Human
  -> Beads priorities and acceptance criteria
  -> Software Factory Oracle on VPS
       -> isolated worktree
       -> Codex CLI worker
       -> trusted validation commands
       -> Git branch / pull request
  -> GitHub CI
       -> immutable GHCR image
  -> linked website-k8s deployment work
       -> GitOps pull request
       -> ArgoCD
       -> K3s DEV
  -> read-only deployment verification
  -> safe task branch and worktree cleanup
  -> Beads completion
```

## Source-of-truth boundaries

| Concern | Source of truth |
| --- | --- |
| Product requirements and work state | Product repository Beads |
| Application behavior | Product repository Git history |
| Container artifact | GHCR immutable digest or full commit tag |
| Deployment work state | `website-k8s` Beads |
| Kubernetes desired state | `website-k8s` Git history |
| Runtime reconciliation | ArgoCD |
| Factory behavior and policy | This repository |
| Workspace routing | Workspace-root `AGENTS.md` and `agents-md` |

## VPS filesystem layout

```text
/srv/software-factory/
├── repos/
│   ├── software-factory/   control repository, clean `main`
│   ├── <product-id>/       canonical product checkout, clean default branch
│   └── website-k8s/        canonical GitOps checkout, clean `main`
├── worktrees/
│   ├── software-factory/<bead-id>/
│   ├── <product-id>/<bead-id>/
│   └── website-k8s/<bead-id>/
└── runtime/
    ├── locks/
    └── runs/<run-id>/

/etc/software-factory/
├── repositories.yaml
└── policies.yaml
```

Directory rules:

- `repos/<repository>` is the registered canonical checkout used for fetch,
  synchronization, Beads discovery, and worktree administration. Its default
  branch stays clean. Only deterministic Oracle operations may write its Git
  metadata or `.beads`; implementation and review workers receive no canonical
  checkout write access.
- `worktrees/<repository>/<bead-id>` is the only writable source workspace for
  an implementation task. One worktree belongs to one Bead and one branch.
- `runtime` contains resumable execution metadata and locks, never durable work
  or secrets, and is not a Git repository.
- `/etc/software-factory` contains root-provisioned, host-local configuration.
  It is readable by the factory user but is never committed.
- Codex receives one worktree as its working directory and writable root. It
  does not receive `/srv/software-factory/repos` as a general write target.

## Repository and component model

The root-provisioned `/etc/software-factory/repositories.yaml` is the runtime
allowlist. Each entry identifies exactly one canonical Git repository, default
branch, policy, Beads remote, and trusted validation command arrays. A product
entry may additionally declare named components, the OCI package repositories
each component publishes, and the registered GitOps applications that consume
those components.

Each entry also carries non-secret `credential_refs` keyed by operation. The
trusted credential provider resolves the reference; credential material never
appears in repository configuration. Git read/write and Beads synchronization
resolve against the selected source repository, package read against that
repository's declared package set, and GitOps read/write against the target
GitOps repository. A product credential is never a fallback for its deployment
repository or another product.

Package publication is outside the VPS credential provider. Repository CI uses
the GitHub Actions `GITHUB_TOKEN` with `packages: write` scoped to the publish
job and `contents: read` otherwise. The factory validates the workflow boundary,
successful run, full-SHA artifact identity, and OCI provenance; CI neither
reads host registration nor receives a registry-push credential from the VPS.

Repository IDs, canonical paths, normalized Git repository identities/remotes,
and Beads remote identities are each unique across registrations. Every entry
has exactly one scalar `default_branch`; the branch value is local to that
repository, so several repositories may all use `main`.

This mapping is routing metadata, not a copy of desired state. It records stable
identities and the required `sha-<full 40-character commit>` tag policy; it
never records current image tags, Kubernetes manifests, or rollout status.
`website-k8s` remains the only source of Kubernetes desired state. Component
IDs are unique within their product repository, package identities are
unambiguous, and every component referenced by a deployment must be declared by
that same product entry.

Version 1 keeps the singular `deployment` form for an existing one-component
registration and adds the plural `deployments` form for one-to-many mappings.
The forms are mutually exclusive. Unknown repositories, duplicate component or
package identities, dangling component references, non-array validation
commands, and mutable package policies are configuration errors that stop work
before a claim or external mutation.

Legacy version 1 entries without `credential_refs` remain parseable so an
operator can migrate the host file without an unsafe flag day. They authorize
only the documented operator-supervised manual bootstrap path. The unattended
runner rejects them before repository access, Beads synchronization, package
access, or GitOps work. It also rejects a reference that is missing, reused
across repository boundaries, unresolved, or broader than its exact operation.

Repository onboarding is complete only when the canonical checkout is clean,
its exact remote and default branch match host configuration, repository-level
`AGENTS.md` is present, its private canonical Beads database is synchronized to
its own configured remote, and its trusted validation and delivery contracts
are usable. The operator owns registration in `/etc`; the factory never
discovers a repository and silently grants itself authority over it.

## Execution state machine

```text
ready
  -> claimed
  -> workspace_created
  -> executing
  -> validating
  -> reviewing
  -> branch_pushed
  -> awaiting_merge
  -> image_built
  -> deployment_requested
  -> deploying
  -> verifying
  -> cleaning_up
  -> completed
```

Every transition must be idempotent. After interruption, the runner discovers
the current Beads, Git, pull-request, CI, image, and ArgoCD state before it
performs another mutation.

`cleaning_up` is an Oracle-owned completion gate. Before resolving targets, the
Oracle acquires an exclusive repository/task lifecycle cleanup lock from
trusted factory state. No run may start in the task worktree while this lock is
held. The Oracle refreshes the remote default branch and requires
`git merge-base --is-ancestor <exact-task-head> <refreshed-remote-default>` to
succeed. It also proves that the dedicated worktree is clean and inactive.

Before mutation, the Oracle writes a trusted, resumable record containing the
repository, exact branch, task-head SHA, worktree path, default-ref SHA, check
results, and per-step status. With the lock still held, it checks activity
again immediately before removing the exact worktree, then deletes the local
task branch and deletes the exact remote task branch last. Each mutation moves
durably through `pending -> executing -> completed`, with `executing` recorded
before invocation and `completed` only after success.

Immediately before remote deletion, the Oracle refreshes exactly the remote
default and task refs, verifies that the task ref still equals the recorded
task-head SHA, reruns the default/protected exclusions, and reruns exact
merge-base ancestry against the refreshed remote default. Deletion then uses
an atomic ref lease bound to the recorded SHA, so a concurrent ref update fails
closed. The Oracle records final evidence and Bead closure before releasing the
lock.

On partial failure, the Oracle holds the lock while safely recording current
state, leaves the Bead open, and permits a later lock holder to revalidate and
resume idempotently from the recorded step. On recovery, an absent exact
resource in `executing` may be marked complete only when its trusted identity
record and every remaining applicable identity, ref, ancestry, and protection
check still pass; absence in `pending` or any ambiguity blocks. Failure or
ambiguity preserves remaining resources. Default or protected branches,
unmerged or active task branches, dirty or active worktrees, and resources
without an unambiguous task mapping are never cleanup targets.

## Concurrency

- The initial VPS supports one writing worker globally.
- Read-only analysis and review may run concurrently when they cannot update
  Beads or shared files.
- Later concurrency uses one Git worktree per task and serialized ownership of
  hot files, Beads state, and deployment manifests.

## Resource placement

Heavy container builds belong in GitHub Actions. The VPS runner performs source
edits and bounded validation only. Kubernetes workloads retain priority over
factory CPU, memory, and IO.
