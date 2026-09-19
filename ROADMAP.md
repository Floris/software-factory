# Roadmap

## Phase 0 - Repository foundation

- Record architecture and security boundaries.
- Define Beads ownership and cross-repository linking.
- Add configuration examples.
- Add this repository to the shared workspace router.

## Phase 1 - VPS bootstrap

- Create a non-root factory user.
- Create protected repository, worktree, log, and runtime directories.
- Install or verify Git, Codex CLI, Beads, and required project runtimes.
- Authenticate each integration with its own least-privilege identity.
- Initialize this repository's factory-development Beads database and remote.

## Phase 2 - Manual single-task runner

- Onboard `expense-tracker` as the first product.
- Read ready work without mutating it.
- Atomically claim one task through the Oracle.
- Create one isolated Git worktree.
- Invoke Codex with workspace-write and structured output.
- Run trusted validation commands from repository configuration.
- Produce a branch and reviewable diff; do not merge automatically.

## Phase 3 - Pull-request workflow

- Push factory-created branches with a dedicated Git identity.
- Open pull requests with Bead and validation evidence.
- Observe CI without exposing Codex credentials to repository-controlled code.
- Add a read-only review step for security-sensitive changes.

## Phase 4 - GitOps handoff

- Consume immutable application image identifiers from successful CI.
- Create a linked deployment Bead in `website-k8s`.
- Update deployment state through a separate pull request.
- Verify ArgoCD application health, workload readiness, logs, and health
  endpoints with a read-only DEV observer identity.

## Phase 5 - Bounded DEV autonomy

- Add a systemd service and timer only after manual runs are reliable.
- Enforce one writer, runtime limits, attempt limits, and stale-claim recovery.
- Permit automation only for explicitly opted-in DEV repositories.
- Keep staging and production promotion behind human review.

## Phase 6 - Preview environments

- Add per-PR namespaces, quotas, temporary ingress, and automatic cleanup.
- Do not begin this phase until resource usage fits the 2-vCPU/8-GB VPS.
