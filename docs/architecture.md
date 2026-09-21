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
       -> verified true merge
       -> leased deletion of exact remote task ref
  -> GitHub CI
       -> immutable GHCR image
  -> linked website-k8s deployment work
       -> GitOps pull request
       -> ArgoCD
       -> K3s DEV
  -> read-only deployment verification
  -> safe local task branch and worktree cleanup
  -> Beads completion
```

## Source-of-truth boundaries

| Concern | Source of truth |
| --- | --- |
| Product requirements and work state | Central `software-factory` Beads |
| Application behavior | Product repository Git history |
| Container artifact | GHCR immutable digest or full commit tag |
| Deployment work state | Central `software-factory` Beads |
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
  synchronization, and worktree administration. Its default branch stays
  clean. Only deterministic Oracle operations may write its Git metadata.
  The one canonical `.beads` database is in `repos/software-factory` and is
  written only by the trusted host runner. Implementation and review workers
  receive no canonical checkout write access.
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
branch, policy, and trusted validation command arrays. One top-level Beads
registration identifies the central database and remote. A product
entry may additionally declare named components, the OCI package repositories
each component publishes, and the registered GitOps applications that consume
those components.

Policy separates model-controlled Git capability from deterministic lifecycle
authority. `git.delete_branch: false` prevents delegated/model-controlled
branch deletion. `lifecycle.delete_merged_remote_branch: true` authorizes only
the trusted Oracle runner's locked, durable deletion of the exact remote task
ref after a verified true merge. It is neither general branch-delete authority
nor permission to evaluate a model-produced command. A missing or false
lifecycle key blocks that remote mutation.

Each repository entry also carries non-secret `credential_refs` keyed by
operation. The
trusted credential provider resolves the reference; credential material never
appears in repository configuration. Git read/write resolve against the
selected source repository, while central Beads synchronization uses only its
top-level binding. Package read resolves against that
repository's declared package set, and GitOps read/write against the target
GitOps repository. A product credential is never a fallback for its deployment
repository or another product.

Package publication is outside the VPS credential provider. Repository CI uses
the GitHub Actions `GITHUB_TOKEN` with `packages: write` scoped to the publish
job and `contents: read` otherwise. The factory validates the workflow boundary,
successful run, full-SHA artifact identity, and OCI provenance; CI neither
reads host registration nor receives a registry-push credential from the VPS.

Repository IDs, canonical paths, and normalized Git repository
identities/remotes are each unique across registrations. The central Beads path
and remote have one explicit registration. Every repository entry
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
`AGENTS.md` is present, the central Beads database is synchronized and the
repository ID is valid, and its trusted validation and delivery contracts are
usable. The operator owns registration in `/etc`; the factory never
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
  -> merge_verified
  -> remote_ref_deleting
  -> remote_ref_deleted
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

The lifecycle has two Oracle-owned, independently locked phases. Immediately
after GitHub reports a successful true merge, the merge-time phase deletes the
exact remote task ref. The Oracle acquires the exclusive repository/task
lifecycle lock before resolving a target and proves the expected merged pull
request number, repository, base ref, head ref, and merge commit from trusted
factory state. It refreshes exactly the remote default and task refs, rejects a
shared, default, protected, active, or ambiguously owned head after refreshing
its protection metadata, and requires the remote task ref to equal the recorded
task-head SHA. It also requires the dedicated worktree to be clean and
inactive, and it requires
`git merge-base --is-ancestor <exact-task-head> <refreshed-remote-default>` to
succeed. A squash or rebase result therefore fails closed; the factory does
not manufacture ancestry or weaken this proof.

That same repository/task lifecycle lock is the task-worktree activation gate.
Before activating the worktree or starting any worker, reviewer, or other
factory run against it, the Oracle must acquire shared participation in that
exact lock and retain it until the run is inactive. An exclusive lifecycle lock
prevents a new activation from starting, and an active shared participant
prevents cleanup from acquiring exclusivity. A separate activity flag or a
one-time lock observation is not a substitute for participating in the lock.

Before remote mutation, the Oracle writes a trusted, resumable lifecycle record
containing the repository, merged pull-request identity, exact branch and
task-head SHA, worktree path, refreshed default-ref SHA, protection and
identity, cleanliness, and activity results, and a remote-deletion status. The
step moves durably through `pending -> executing -> completed`: `executing` is
persisted before the invocation, and `completed` only after an atomic deletion
with a force-with-lease bound to the recorded task-head SHA succeeds and remote
absence is observed. A concurrent ref update makes the lease fail closed. The
Oracle then releases the lock but deliberately retains the dedicated worktree
and local branch so later delivery and verification can use their exact
evidence. The exclusive lock remains held through deletion-result observation
and durable persistence of the `completed` evidence.

After the requested delivery level is verified, `cleaning_up` is the separate
closure gate. The Oracle reacquires the same exclusive lifecycle lock, loads
the prior record, and requires the remote-deletion step to be `completed`.
Prior remote absence is accepted only with that durable completed evidence, or
during narrow recovery of a step already recorded as `executing` when the
exact trusted identity still matches and every applicable merge, ref,
ancestry, protection, cleanliness, and activity check can be re-proven.
Absence while `pending` blocks. The Oracle rechecks that the retained worktree
is clean and inactive, then removes only the recorded exact worktree and local
task branch, each with its own durable `pending -> executing -> completed`
state, and closes the Bead only after both steps complete.
The exclusive lock remains held through observation of each local mutation,
durable evidence persistence, and Bead closure.

On partial failure, the Oracle records current state while holding the lock,
leaves the Bead open, and permits a later lock holder to revalidate and resume
idempotently. Any shared, default, protected, updated, active, dirty,
unmerged, ambiguously mapped, or otherwise unprovable ref or worktree fails
closed and preserves all remaining resources.

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
