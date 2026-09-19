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
5. onboard `expense-tracker` as the first product repository;
6. implement a manually invoked, single-task runner before any timer or daemon.
