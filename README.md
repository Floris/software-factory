# Software Factory

Control repository for the Codex- and GitHub Issues-driven development factory that
will run on the VPS alongside the existing K3s cluster.

This repository defines how work is selected, executed, reviewed, promoted,
and verified. It does not own application source code or Kubernetes desired
state.

## Current status

The repository currently contains the architecture, security boundaries,
central GitHub Issues task model, workflow, roadmap, and example
configuration. The manual task-store cutover is complete: Issues in this
repository hold new factory, product, and deployment work. The old Beads
store is historical. Unattended claims remain gated by a trusted atomic
coordination mechanism, scoped Issues access, and runner fault tests.
Executable orchestration tooling will be implemented and tested on the Linux
VPS, where Codex CLI, systemd, Git credentials, and the restricted K3s
observer identity are available.

## Sources of truth

- Product repositories own application code and tests.
- `website-k8s` owns Kubernetes and ArgoCD desired state.
- This repository owns factory policy, orchestration behavior, onboarding
  configuration, and the central task store for factory, product, and
  deployment work after cutover.
- GitHub records reviewed changes; GHCR stores immutable images; ArgoCD is the
  only component that reconciles permanent Kubernetes changes.

## Intended flow

```text
GitHub Issues ready work
    -> factory claims one task
    -> isolated Git worktree
    -> Codex implements and validates
    -> branch and pull request
    -> verified true merge and leased remote task-branch deletion
    -> CI builds immutable image
    -> website-k8s deployment task and pull request
    -> ArgoCD reconciles DEV
    -> factory verifies health
    -> local task worktree and branch cleanup
    -> GitHub Issue closes
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
│   └── <repository>/<issue-id>/
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
remote, default branch, policy, and non-secret credential references keyed by
operation. Central GitHub Issues hold task state; the host file has no task
database or task-sync binding.

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
repository `AGENTS.md`, central GitHub Issues access, trusted
argument-array validation profile, package/deployment references, and
repository-scoped credentials. Missing, ambiguous, or inconsistent data fails
closed. See the [workflow](docs/workflow.md#repository-onboarding) for the full
onboarding sequence.

`credential_refs` are provider lookup keys, never tokens or private keys. Git
read/write, Issues access, package read, and GitOps read/write are
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

Project-scoped role definitions under [`.codex/agents/`](.codex/agents/) pin
role-appropriate models and reasoning effort: the architect and reviewer use
the higher-capability analysis model, while the implementation worker uses the
bounded implementation model. No global agent model is set. Role definitions
also enforce that delegated agents cannot create or delete branches or
worktrees, mutate pull requests, or run lifecycle cleanup; those operations
belong to the Oracle.

The example policies intentionally combine `git.delete_branch: false` with
`lifecycle.delete_merged_remote_branch: true`. The first keeps deletion out of
delegated Git actions. The second grants only the root Oracle permission to
perform the locked, durable, exact merged task-ref lifecycle operation. The
[supervised runbook](docs/supervised-lifecycle.md) uses the existing GitHub
connector and SSH without a new host service or GitHub token.

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
- [GitHub Issues model](docs/issues-model.md)
- [Task-store cutover](docs/github-issues-cutover.md)
- [Roadmap](ROADMAP.md)
- [Why this is a separate repository](docs/decisions/0001-separate-control-repository.md)
- [Why tasks use GitHub Issues](docs/decisions/0004-github-issues-task-store.md)
- [Supervised lifecycle decision](docs/decisions/0003-supervised-branch-lifecycle.md)

## VPS bootstrap boundary

Do not install or activate services from a workstation checkout. On the VPS,
the first implementation task will:

1. create a non-root factory user and protected workspace;
2. clone this repository;
3. verify central GitHub Issues access and the registered repository ID;
4. create host-local configuration from the examples;
5. register explicitly opted-in product repositories and their component
   mappings;
6. implement a manually invoked, single-task runner before any timer or daemon.

The branch lifecycle modes are documented in [the lifecycle runner
guide](docs/lifecycle-runner.md) and [the supervised
runbook](docs/supervised-lifecycle.md).
