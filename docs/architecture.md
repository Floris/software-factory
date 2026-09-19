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
│   ├── expense-tracker/    canonical product checkout, clean `main`
│   └── website-k8s/        canonical GitOps checkout, clean `main`
├── worktrees/
│   ├── software-factory/<bead-id>/
│   ├── expense-tracker/<bead-id>/
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
  branch stays clean.
- `worktrees/<repository>/<bead-id>` is the only writable source workspace for
  an implementation task. One worktree belongs to one Bead and one branch.
- `runtime` contains resumable execution metadata and locks, never durable work
  or secrets, and is not a Git repository.
- `/etc/software-factory` contains root-provisioned, host-local configuration.
  It is readable by the factory user but is never committed.
- Codex receives one worktree as its working directory and writable root. It
  does not receive `/srv/software-factory/repos` as a general write target.

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
  -> completed
```

Every transition must be idempotent. After interruption, the runner discovers
the current Beads, Git, pull-request, CI, image, and ArgoCD state before it
performs another mutation.

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
