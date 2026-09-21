# Roadmap

Status reviewed on 2026-09-21 against the VPS, repository state, Beads state,
Git history, and host configuration. Checked items are verified complete.
Unchecked items remain delivery work; their `Current` note records implemented
foundations without treating them as an operational capability.

## Phase 0 - Repository foundation

- [x] Record architecture and security boundaries.
- [x] Define Beads ownership and cross-repository linking.
- [x] Add configuration examples.
- [x] Define a neutral multi-repository component, package, and deployment
  routing contract.
- [ ] Add this repository to the shared workspace router.
  - Current: reusable agent definitions are centralized here, but the
    workspace-root `AGENTS.md` and `agents-md` routing entry are absent.

## Phase 1 - VPS bootstrap

- [x] Create a non-root factory user.
- [x] Create protected repository, worktree, log, and runtime directories.
- [ ] Install or verify Git, Codex CLI, Beads, and required project runtimes.
  - Current: Git, Codex CLI, Beads, and kubectl are available to the factory;
    Node.js and npm are not available to the `codex` user.
- [ ] Authenticate each integration with its own least-privilege identity.
  - Current: Git remote access works, but repository-by-repository credential
    references and operation/audience preflight have not been verified. The
    read-only Kubernetes observer identity is not configured. Unattended
    multi-repository execution remains disabled while an account-wide
    bootstrap credential is usable or any required `credential_refs` entry is
    absent.
- [ ] Cut over to one central Beads database and remote.
  - Current: the three legacy remotes can be cloned read-only and contain 24
    unique tasks. A disposable central candidate imported all 24 with
    repository routing metadata and retained `codex:codex` manifest ownership.
    This does not prove the inaccessible local factory and Expense Tracker
    databases have no unsynchronized changes: their manifests are currently
    `nobody:nogroup`. The host configuration and trusted runner have not been
    switched. Follow the gated migration runbook before any new claim.
- [ ] Register and preflight every opted-in product repository.
  - Current: the tracked contract supports one-to-many components, OCI package
    identities, and GitOps application mappings. Root-owned host registration,
    exact remote/default-branch verification, central Beads
    synchronization, operation-keyed credential references, and credential
    audience checks remain operator work for each repository.

## Phase 2 - Manual single-task runner

- [x] Onboard `expense-tracker` as the first product.
- [x] Read ready work without mutating it.
- [x] Atomically claim one task through the Oracle.
  - Evidence: `et-42p` was assigned to Software Factory with a claim lease.
- [x] Create one isolated Git worktree.
  - Evidence: `et-42p` has its own worktree and task branch.
- [ ] Invoke Codex with workspace-write and structured output.
  - Current: the sandbox policy, app worker, and result schema exist; no
    completed structured worker run has been recorded.
- [ ] Run trusted validation commands from repository configuration.
  - Current: `et-42p` was validated during manual delivery, but the factory
    still lacks a durable Node.js runtime and the trusted host profile omits
    the required integration-test command.
- [x] Produce a branch and reviewable diff; do not merge automatically.
  - Evidence: `et-42p` produced commit `a98e706`, was reviewed in product pull
    request #2, and merged as `9b1f244` before Oracle-owned cleanup.

## Phase 3 - Pull-request workflow

- [x] Push factory-created branches with a dedicated Git identity.
  - Evidence: the `et-42p` product branch and linked deployment branch were
    authored and pushed by Software Factory, then safely removed after merge.
- [x] Open pull requests with Bead and validation evidence.
- [ ] Observe CI without exposing Codex credentials to repository-controlled
  code.
  - Current: CI published the immutable `sha-9b1f244...` application image,
    but no isolated CI-observation run has yet demonstrated that
    repository-controlled execution cannot access Codex credentials.
- [x] Add a read-only review step for security-sensitive changes.
  - Evidence: the high-risk MCP change received independent read-only review
    before merge; cleanup task `sf-3rn` records that result.

## Phase 4 - GitOps handoff

- [x] Consume immutable application image identifiers from successful CI.
  - Evidence: Expense Tracker CI publishes a full-commit SHA image and the DEV
    application and migration job use the same immutable tag.
- [x] Create a linked deployment Bead in `website-k8s`.
  - Evidence: `wk-6ac` links product task `et-42p` to the immutable merged
    application commit.
- [x] Update deployment state through a separate pull request.
  - Evidence: website-k8s pull request #2 pinned the application and migration
    job to the same immutable image and was merged before public verification.
- [ ] Verify ArgoCD application health, workload readiness, logs, and health
  endpoints with a read-only DEV observer identity.
  - Current: the `codex` user has no usable Kubernetes observer kubeconfig.

## Phase 5 - Bounded DEV autonomy

- [ ] Add a systemd service and timer only after manual runs are reliable.
- [ ] Enforce one writer, runtime limits, attempt limits, and stale-claim
  recovery.
  - Current: writer and attempt limits are configured. Runtime limits and
    automated stale-claim recovery are not implemented; the expired `et-42p`
    claim required evidence-backed Oracle reconciliation.
- [ ] Permit automation only for explicitly opted-in DEV repositories.
  - Current: repositories are explicitly listed in host configuration, but no
    automation service enforces the allowlist yet.
- [ ] Keep staging and production promotion behind human review.
  - Current: policy disables automatic pull-request merging, but this has not
    been exercised by an autonomous runner.

## Phase 6 - Preview environments

- [ ] Add per-PR namespaces, quotas, temporary ingress, and automatic cleanup.
- [ ] Do not begin this phase until resource usage fits the 2-vCPU/8-GB VPS.

## Next milestone

Reconcile the inaccessible legacy Beads databases and cut over to the central
store through the trusted non-root runner. Fault-test ownership and sandbox
isolation before resuming claims. Then close the remaining repeatability gaps
in the manual runner: install a durable
trusted Node.js runtime, record one structured worker result, and execute the
configured validation profile from orchestration rather than an ad hoc shell.
Implement and fault-test the canonical Beads ownership/mode preflight and
postflight before unattended execution. Then configure the read-only
Kubernetes observer and verify ArgoCD and workload health without access to
Secrets. Register each opted-in repository in the root-owned host configuration
and replace any account-wide bootstrap access with verified repository-scoped
credentials. These are prerequisites for Phase 5 scheduling.
