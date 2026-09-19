# Workflow

## Task intake

A human or approved planning process creates a Bead in the repository that owns
the work. The task must state:

- the desired outcome and acceptance criteria;
- dependencies and affected repository;
- allowed write scope;
- trusted validation commands;
- risk level and review requirements;
- requested delivery level: code, merged change, DEV deployment, or promotion;
- whether the task may proceed without another human approval.

## Implementation

1. Pull the repository and Beads state.
2. List ready work and select exactly one task.
3. Claim the task through the Oracle.
4. Create `codex/<bead-id>-<slug>` in a dedicated worktree.
5. Construct the Codex prompt from trusted factory instructions plus the Bead
   as clearly delimited untrusted task data.
6. Run Codex with workspace-write, no broad host access, and structured output.
7. Execute validation commands from repository configuration, never from Bead
   text.
8. Request read-only review when the configured risk policy requires it.
9. Push the branch and open a pull request containing evidence and the Bead ID.

## Deployment

1. CI validates the merged application commit.
2. CI publishes an immutable image tied to that commit.
3. The Oracle creates or claims a linked deployment Bead in `website-k8s`.
4. A dedicated change updates the deployment image and any matching migration
   job image.
5. The GitOps pull request is reviewed and merged under the environment policy.
6. ArgoCD reconciles the desired state.
7. A read-only observer checks ArgoCD health, pod readiness, relevant logs, and
   public health endpoints.
8. The deployment Bead and then the product Bead become eligible for cleanup
   and closure after verification.

## Post-merge cleanup and closure

The Oracle owns cleanup. After the requested delivery level is verified and
before it closes the Bead, it:

1. acquires an exclusive repository/task lifecycle cleanup lock identified
   from trusted factory state before resolving any cleanup target, and holds it
   through all checks, mutations, evidence recording, and Bead closure;
2. while holding the lock, refreshes the remote default branch and resolves the
   exact task branch and dedicated task worktree from trusted factory state;
3. verifies the task head with exactly
   `git merge-base --is-ancestor <exact-task-head> <refreshed-remote-default>`
   and blocks cleanup when the command does not succeed;
4. verifies that the dedicated worktree is clean and no worker or factory run
   is active in it;
5. before the first mutation, writes a trusted, resumable cleanup record with
   the repository, exact branch, task-head SHA, worktree path, default-ref SHA,
   check results, and a status for every cleanup step;
6. performs only the recorded pending steps, in order: remove the exact
   dedicated worktree, delete the local task branch, and delete the exact
   remote task branch last, using the remote revalidation and atomic lease
   below; and
7. records the evidence and closes the Bead only after every cleanup step
   succeeds.

Holding the lock prevents any run from starting in the task worktree. The
Oracle performs a final activity check immediately before removing the exact
worktree. It records each successful mutation before attempting the next one,
so an interrupted cleanup can reacquire the same lock, revalidate the trusted
identities and safety checks, and resume from the recorded incomplete step.

Every mutation has the durable state machine `pending -> executing ->
completed`. The Oracle writes `executing` before invoking the mutation and
writes `completed` only after observing success. During recovery, a resource
already recorded as `completed` remains complete. An absent exact resource for
an `executing` step may be advanced to `completed` only when the trusted record
identifies that exact resource and all remaining applicable identity, ref,
ancestry, and protection checks still pass. An absent resource recorded as
`pending`, a mismatched identity, or an unprovable check blocks cleanup.

Immediately before deleting the exact remote task branch, the Oracle refreshes
exactly the remote default ref and remote task ref. It verifies that the
refreshed task ref still equals the trusted recorded task-head SHA, reruns the
default-branch and protected-branch exclusions, and reruns
`git merge-base --is-ancestor <recorded-task-head>
<refreshed-remote-default>`. Only after those checks succeed does it record the
remote-deletion step as `executing` and invoke deletion with an atomic ref lease
bound to the recorded SHA, with semantics equivalent to:

```text
git push --force-with-lease=refs/heads/<task>:<recorded-head> origin :refs/heads/<task>
```

Any concurrent task-ref update makes the lease fail closed. The Oracle then
records `completed` only after the leased deletion succeeds.

Cleanup must never delete a default or protected branch, an unmerged or active
branch, a dirty or active worktree, or any branch or worktree whose exact task
ownership is ambiguous. It is scoped to the one completed task and is
idempotent. A missing resource is accepted only when its step is already
recorded as `completed` or when the `executing` recovery rule above permits the
transition to `completed`; otherwise cleanup blocks.

## Failure behavior

- Failed validation leaves the task active with a concise failure record.
- Ambiguous scope, missing credentials, or required human decisions block the
  task instead of expanding authority.
- Failed deployment blocks the deployment Bead and never triggers a production
  promotion.
- Failed or ambiguous cleanup keeps the lifecycle lock while the Oracle safely
  records the failure and completed-step state, then leaves the task open. A
  later attempt reacquires the lock and resumes idempotently from that record;
  it never weakens the ancestry, cleanliness, activity, protection, or
  ownership checks.
- Attempts are bounded. A later runner resumes from observed state rather than
  repeating mutations blindly.
- Cleanup removes only worktrees and runtime artifacts owned by the completed
  task; it never deletes product or deployment repositories.
