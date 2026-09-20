# Software Factory

Control repository for the Codex- and Beads-driven development factory that
will run on the VPS alongside the existing K3s cluster.

This repository defines how work is selected, executed, reviewed, promoted,
and verified. It does not own application source code or Kubernetes desired
state.

## Current status

The repository currently contains the approved architecture, security
boundaries, Beads conventions, workflow, roadmap, and example configuration.
Executable orchestration tooling will be implemented and tested on the Linux
VPS, where Codex CLI, Beads, systemd, Git credentials, and the restricted K3s
observer identity are available.

## Sources of truth

- Product repositories own application code, tests, and product Beads.
- `website-k8s` owns Kubernetes and ArgoCD desired state plus deployment Beads.
- This repository owns factory policy, orchestration behavior, onboarding
  configuration, and factory-development Beads.
- GitHub records reviewed changes; GHCR stores immutable images; ArgoCD is the
  only component that reconciles permanent Kubernetes changes.

## Intended flow

```text
Beads ready work
    -> factory claims one task
    -> isolated Git worktree
    -> Codex implements and validates
    -> branch and pull request
    -> CI builds immutable image
    -> website-k8s deployment task and pull request
    -> ArgoCD reconciles DEV
    -> factory verifies health
    -> Beads task closes
```

## VPS directory layout

All Git projects use one predictable root:

```text
/srv/software-factory/
├── repos/                  clean canonical checkouts
│   ├── software-factory/
│   ├── <product-id>/
│   └── website-k8s/
├── worktrees/              task-specific writable Git worktrees
│   └── <repository>/<bead-id>/
└── runtime/                locks and resumable run metadata; never Git
```

The factory reads and synchronizes repositories from `repos/`. Codex workers
write only inside their assigned directory under `worktrees/`; they do not
implement changes directly in the canonical checkout. Host configuration lives
under `/etc/software-factory/`, outside every Git repository.

## Repository registration contract

The root-provisioned `/etc/software-factory/repositories.yaml` is the live
allowlist and routing source for every repository the factory may manage. The
tracked [`config/repositories.example.yaml`](config/repositories.example.yaml)
documents the contract with neutral placeholders; it is not deployment state.
An operator registers each repository with its exact canonical checkout,
remote, default branch, policy, per-repository Beads remote, and non-secret
credential references keyed by operation.

A product registration may define several `components`. Each component maps a
source directory to one or more OCI package repositories, all with the
`sha-<full 40-character commit>` publication policy. A `deployments` list maps
those component IDs to registered GitOps repositories and applications. The
legacy singular `deployment` entry remains valid for a one-component version 1
registration without requiring component metadata; a registration must not
specify both forms. Manifest contents, current image tags, and live rollout
state remain exclusively in the GitOps repository and cluster, not in host
configuration. A legacy entry cannot perform unattended package publication or
deployment delivery until its package identity, CI publication boundary, and
factory `package_read` binding are validated.

Before admitting work, the Oracle verifies the canonical checkout and remote,
repository `AGENTS.md`, Beads ownership and synchronized remote, trusted
argument-array validation profile, package/deployment references, and
repository-scoped credentials. Missing, ambiguous, or inconsistent data fails
closed. See the [workflow](docs/workflow.md#repository-onboarding) for the full
onboarding sequence.

`credential_refs` are provider lookup keys, never tokens or private keys. Git
read/write, Beads synchronization, package read, and GitOps read/write are
separate operations. Each reference must resolve to an identity scoped to the
exact repository or declared package set. Package publication is deliberately
absent: repository CI uses its own job-scoped GitHub Actions `GITHUB_TOKEN` and
does not read host registration or receive credentials from the VPS provider.
Version 1 entries that omit the new field remain readable for
operator-supervised migration, but are ineligible for unattended work;
automated credential preflight fails closed until the references are installed
and verified.

## Codex configuration

The tracked [`.codex/config.toml`](.codex/config.toml) applies the factory's
shared sandbox and approval policy whenever this trusted repository is opened
with Codex. It also makes the factory `worktrees/` and `runtime/` directories
writable, so the CLI does not need repeated `--add-dir` flags.

Machine-local Codex state remains in `/home/codex/.codex/` on the VPS. Project
trust records, TUI state, authentication files, and tokens must never be copied
into this repository. After authentication, start an interactive session with:

```sh
cd /srv/software-factory/repos/software-factory
codex
```

## Documentation

- [Architecture](docs/architecture.md)
- [Workflow](docs/workflow.md)
- [Security model](docs/security-model.md)
- [Beads model](docs/beads-model.md)
- [Roadmap](ROADMAP.md)
- [Why this is a separate repository](docs/decisions/0001-separate-control-repository.md)

## VPS bootstrap boundary

Do not install or activate services from a workstation checkout. On the VPS,
the first implementation task will:

1. create a non-root factory user and protected workspace;
2. clone this repository;
3. initialize and synchronize Beads;
4. create host-local configuration from the examples;
5. register explicitly opted-in product repositories and their component
   mappings;
6. implement a manually invoked, single-task runner before any timer or daemon.
