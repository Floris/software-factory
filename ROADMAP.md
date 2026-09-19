# Roadmap

Status reviewed on 2026-09-19 against the VPS, repository state, Beads state,
Git history, and host configuration. Checked items are verified complete.
Unchecked items remain delivery work; their `Current` note records implemented
foundations without treating them as an operational capability.

## Phase 0 - Repository foundation

- [x] Record architecture and security boundaries.
- [x] Define Beads ownership and cross-repository linking.
- [x] Add configuration examples.
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
  - Current: repository-specific SSH keys and Git remote access work. The
    read-only Kubernetes observer identity is not configured.
- [ ] Initialize this repository's factory-development Beads database and
  remote.
  - Current: this repository and `website-k8s` have no Beads database. The
    `expense-tracker` database is local embedded Dolt without a remote.

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
  - Current: trusted commands are configured, but the required runtime is
    missing and the current task also requires an integration-test command
    that is not in the host validation profile.
- [ ] Produce a branch and reviewable diff; do not merge automatically.
  - Current: the `et-42p` branch exists but has no diff or pushed review state.

## Phase 3 - Pull-request workflow

- [ ] Push factory-created branches with a dedicated Git identity.
  - Current: the Software Factory Git identity and remote authentication work;
    no task branch authored and pushed by that identity has been verified.
- [ ] Open pull requests with Bead and validation evidence.
- [ ] Observe CI without exposing Codex credentials to repository-controlled
  code.
- [ ] Add a read-only review step for security-sensitive changes.
  - Current: a read-only quality reviewer and workflow policy exist, and
    `et-42p` requires this review; no completed review run is recorded.

## Phase 4 - GitOps handoff

- [x] Consume immutable application image identifiers from successful CI.
  - Evidence: Expense Tracker CI publishes a full-commit SHA image and the DEV
    application and migration job use the same immutable tag.
- [ ] Create a linked deployment Bead in `website-k8s`.
- [ ] Update deployment state through a separate pull request.
  - Current: DEV deployment state exists, but no factory handoff PR with linked
    Bead evidence has been verified.
- [ ] Verify ArgoCD application health, workload readiness, logs, and health
  endpoints with a read-only DEV observer identity.
  - Current: the `codex` user has no usable Kubernetes observer kubeconfig.

## Phase 5 - Bounded DEV autonomy

- [ ] Add a systemd service and timer only after manual runs are reliable.
- [ ] Enforce one writer, runtime limits, attempt limits, and stale-claim
  recovery.
  - Current: writer and attempt limits are configured. Runtime limits and
    stale-claim recovery are not implemented; the `et-42p` lease expired while
    the task remained in progress.
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

Complete one manual `expense-tracker` task from ready-work discovery through
claim, isolated worker execution, trusted validation, read-only review, pushed
branch, and evidence-bearing pull request. This is the exit criterion for Phase
2 and the prerequisite for enabling Phase 5 scheduling.
