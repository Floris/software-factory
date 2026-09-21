# ADR 0003: Allow supervised Oracle branch cleanup

- Status: Accepted for attended sessions after host policy activation
- Date: 2026-09-21

## Context

The initial merged-task lifecycle required a root-installed runner, a host
launcher, and a separate GitHub read token. Those dependencies prevented the
Oracle from cleaning merged branches with the existing GitHub connector and
SSH identity. The operator asked for a procedure the Oracle can execute
without a daemon, recurring manual script invocation, or new token.

## Decision

The root Oracle may run the existing stateful lifecycle script from the clean
canonical factory `main` checkout in a supervised session. Root-owned host
registration and policy remain required. The Oracle supplies short-lived,
private, strictly scoped evidence from the authenticated GitHub connector.
The runner independently checks live Git refs, true-merge ancestry, the exact
dedicated worktree, and a SHA-bound deletion lease. It records each phase in
private durable runtime state. `git.delete_branch: false` continues to deny
delegated branch deletion; `lifecycle.delete_merged_remote_branch: true`
authorizes only this bounded Oracle operation.

The connector exposes PR and repository facts but does not expose the branch
protection flag. In supervised mode GitHub's SSH push is the protection gate.
The Oracle checks that no other task agent is active because legacy worktrees
do not yet participate in shared locks. The installed runner remains the
stronger unattended option when its credential and launcher are available.

## Consequences

- The operator changes the root-owned lifecycle policy once; no GitHub token
  or new service is required for supervised cleanup.
- Connector evidence is an Oracle attestation, not independently authenticated
  input to the runner. Ambiguous PR, repository, activity, or ref state blocks.
- The supervised mode must not be used where the SSH identity can bypass a
  protected-branch deletion rule. Its exact scope and recovery steps are in
  [the runbook](../supervised-lifecycle.md).
