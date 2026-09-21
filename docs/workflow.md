# Workflow

## Repository onboarding

Onboarding is an explicit operator-and-Oracle workflow, not repository
auto-discovery:

1. The operator chooses an opted-in repository, adds its exact reviewed entry
   to root-owned `/etc/software-factory/repositories.yaml`, and provisions only
   the repository-scoped Git permissions the factory needs. Package-publish
   permissions remain in that repository's CI.
2. The Oracle verifies the exact remote and remote-advertised default branch,
   then creates a clean canonical checkout at the path reserved by the host
   configuration. A mismatch or ambiguous repository identity blocks.
3. The product repository adds repository-specific `AGENTS.md` instructions
   that preserve its invariants and factory boundaries.
4. The Oracle verifies that the central GitHub Issues repository is available
   and the target repository ID is registered. No product task database is initialized.
5. The repository adds bounded validation that is safe on untrusted source.
   Host configuration represents each invocation as an executable followed by
   an argument array; no command comes from an issue or is passed to a shell.
6. The product maps each deployable component to its OCI package repository or
   repositories. CI must validate pull requests and, after merge, publish each
   affected package as `sha-<full 40-character commit>` with OCI source and
   revision metadata (`org.opencontainers.image.source` and
   `org.opencontainers.image.revision`).
7. The product maps components to one or more registered `website-k8s`
   applications. This is stable routing only; manifests and current image
   values remain in `website-k8s`.
8. The Oracle validates the complete registration graph and its credential
   bindings. Only after every check passes may the repository contribute ready
   work.
9. A product change and its linked `website-k8s` deployment change complete the
   normal pull-request, immutable-image, ArgoCD, and verification flow below.

The singular `deployment` field remains accepted for an existing
one-component version 1 entry. New multi-component entries use `deployments`;
specifying both is invalid. Missing AGENTS guidance, unavailable or overly
broad credentials, invalid command arrays, unavailable central Issues, duplicate
package identities, dangling component references, or a mutable tag policy all
fail closed before claim, push, publication, or deployment.

For repository, package, and GitOps operations, unattended preflight selects
the operation key from the target repository's `credential_refs`, resolves that
non-secret key through the trusted provider, and verifies its authorization
audience before use:

- source fetch uses `git_read`; branch push and pull-request mutation use
  `git_write` for that exact source repository;
- GHCR image verification uses `package_read` constrained to that product's
  declared GHCR package set; and
- GitOps observation and GitOps branch/pull-request mutation use `gitops_read`
  and `gitops_write` from the target `website-k8s` registration, never from the
  product registration.

Supervised task-state reads and writes use the authenticated GitHub connector.
Unattended issue access requires a separately reviewed, root-owned binding
scoped to the central Issues repository; it cannot reuse a product's Git
credential. Unattended issue claims remain disabled until that binding and an
atomic coordination mechanism are implemented and tested.

GHCR publication is not a VPS credential operation. Before trusting a release,
the Oracle verifies that repository CI used its own GitHub Actions
`GITHUB_TOKEN`, granted `packages: write` only to the publish job, retained
`contents: read`, published only the declared package set, and produced the
required full-SHA tag and OCI metadata. CI must not read the root-owned host
registration, and the VPS credential provider must not issue registry-push
credentials.

A missing operation key, unresolved reference, repository or package audience
mismatch, broader permission, or fallback to an account-wide bootstrap
credential stops the unattended run before the operation. Older version 1
entries without `credential_refs` remain parseable only for the documented
operator-supervised migration path; omission never enables unattended access.
Likewise, a legacy one-component entry without package metadata may perform
only operations whose bindings and audiences can be proven; package publication
or deployment delivery waits for the component/package mapping migration.

## Task intake

A human or approved planning process creates an Issue in the central factory
repository. Its body must name exactly one registered `repository_id`. The
issue must state:

- the desired outcome and acceptance criteria;
- dependencies and affected repository;
- allowed write scope;
- trusted validation commands;
- risk level and review requirements;
- requested delivery level: code, merged change, DEV deployment, or promotion;
- whether the task may proceed without another human approval.

## Implementation

1. The Oracle refreshes the selected repository and central GitHub Issues.
2. List open, unblocked work and select exactly one task.
3. Check current issue comments for an active claim and record an Oracle claim
   with identity, time, repository ID, and worktree. An issue comment is not an
   atomic multi-Oracle lock; unattended claiming remains disabled until a
   trusted lock or equivalent compare-and-set mechanism is implemented.
4. The Oracle creates `codex/issue-<number>-<slug>` in a dedicated worktree
   named `issue-<number>`.
5. Construct the Codex prompt from trusted factory instructions plus the Issue
   as clearly delimited untrusted task data.
6. Run Codex with workspace-write, no broad host access, and structured output.
7. Execute validation commands from repository configuration as executable and
   argument arrays, without shell interpretation and never from Issue text.
8. Request read-only review when the configured risk policy requires it.
9. The Oracle pushes the branch and opens a pull request containing evidence,
   the Issue URL, and a statement that the Oracle will delete the exact remote
   task ref after a verified true merge. A GitHub auto-delete setting may
   exist, but the factory neither enables nor trusts it as lifecycle evidence.

Before merging, the Oracle resolves the registered repository's root-owned
policy. If `git.merge_pull_request: true`, it assigns the exact PR, base and
head refs, and head SHA to the read-only `pull_request_reviewer`. A READY verdict
is advice, not authority: the Oracle refreshes the PR identity, required CI
checks and review state, confirms the task head and target default branch, and
uses a true merge commit only when every gate still passes. It then immediately
runs the merge-time lifecycle phase. A BLOCKED verdict, stale evidence, or a
false or missing policy value prevents automatic merge; with a false value,
the Oracle asks the human for approval of that exact PR. No delegated agent
merges or deletes branches.

Delegated architects, implementation workers, and reviewers do not create or
delete branches or worktrees, mutate pull requests, or perform lifecycle
cleanup. Architects and reviewers make no external mutations. Delegated roles
run only trusted validation commands supplied by the Oracle or recorded in
host configuration.

For unattended operation, every activation of a task worktree, including the start of a worker, reviewer,
or other factory run, must acquire shared participation in the same exact
repository/task lifecycle lock used by cleanup and retain it until that run is
inactive. A run cannot start while the Oracle holds the exclusive lock, and the
Oracle cannot acquire exclusivity while a run holds shared participation. An
activity marker or one-time check of the lock is not sufficient on its own.

## Deployment

1. CI validates the merged application commit.
2. CI publishes every affected component package with a
   `sha-<full 40-character commit>` tag and OCI source/revision metadata.
3. The Oracle creates or selects a linked central deployment Issue with target
   `repository_id: website-k8s`.
4. A dedicated change updates every workload image mapped to the affected
   component, including matching jobs and scheduled jobs, to that exact tag.
5. The GitOps pull request is reviewed and merged under the environment policy.
6. ArgoCD reconciles the desired state.
7. A read-only observer checks ArgoCD health, pod readiness, relevant logs, and
   public health endpoints.
8. The deployment Issue and then the product Issue become eligible for local
   cleanup and closure after verification; their merged remote task refs were
   already handled by the merge-time lifecycle phase.

## Merge-time remote branch deletion

The reviewed implementation and its unattended host installation gates are
described in [the lifecycle runner guide](lifecycle-runner.md). Attended
sessions may use [the supervised procedure](supervised-lifecycle.md) from the
clean canonical factory `main` checkout, with private connector evidence and
an explicit root-owned lifecycle policy. This mode trusts the root Oracle's
attestation of GitHub PR, repository, and branch-protection facts.

The Oracle owns every lifecycle mutation. Immediately after a successful merge
is observed, and before waiting for image, deployment, or promotion delivery,
it first requires `lifecycle.delete_merged_remote_branch: true` from the
selected root-owned policy. `git.delete_branch: false` remains the prohibition
for delegated Git operations; the lifecycle key authorizes only the bounded
Oracle procedure, in installed or supervised mode.
If that lifecycle key is missing or false, deletion blocks. When authorized,
the Oracle:

1. acquires an exclusive repository/task lifecycle cleanup lock identified
   from trusted factory state before resolving any target, and holds it through
   all checks, mutation, mutation-result observation, and durable evidence
   persistence;
2. verifies the merged pull request's exact repository, number, base ref, head
   ref, recorded task-head SHA, and merge result against trusted factory state;
3. requires a true merge whose refreshed default branch contains the exact
   task head, using exactly
   `git merge-base --is-ancestor <exact-task-head> <refreshed-remote-default>`
   and blocks when the command does not succeed, so squash and rebase outcomes
   fail closed;
4. refreshes exactly the remote default and task refs plus applicable
   protection metadata, verifies the task ref is still the recorded task-head
   SHA, and rejects a shared, default, protected, active, updated, ambiguously
   owned, or otherwise unprovable head;
5. verifies that the dedicated worktree is clean and that no worker or factory
   run is active in it, without removing the worktree or local branch;
6. before mutation, writes a trusted, resumable record containing the
   repository, merged pull-request identity, exact branch, task-head SHA,
   worktree path, refreshed default-ref SHA, every check result, and a
   `pending` remote-deletion step;
7. persists that step as `executing`, repeats the exact remote ref, default,
   protection, identity, activity, cleanliness, and ancestry checks, and
   invokes deletion with an atomic ref lease bound to the recorded SHA; and
8. observes exact remote-ref absence, persists `completed`, and releases the
   lock while retaining the local task branch and dedicated worktree.

The leased deletion has semantics equivalent to:

```text
git push --force-with-lease=refs/heads/<task>:<recorded-head> origin :refs/heads/<task>
```

Any concurrent task-ref update makes the lease fail closed. GitHub's automatic
branch deletion setting is never substituted for this checked operation or its
durable evidence. If automation removes the ref before the Oracle has persisted
`executing`, the observed absence is still a `pending` absence and blocks.

The remote-deletion step uses `pending -> executing -> completed`. On recovery,
an already `completed` step remains complete. An absent exact remote ref in
`executing` may advance to `completed` only when the trusted record identifies
that exact resource, the merged pull-request identity still matches, and every
remaining applicable ref, ancestry, protection, cleanliness, and activity
check still passes. Absence in `pending`, a mismatched identity, or any
unprovable check blocks.

## Delivery verification, local cleanup, and closure

The Issue remains open, and the dedicated worktree and local task branch remain
available, until its requested delivery level is verified. The Oracle then:

1. reacquires the exclusive repository/task lifecycle lock and loads the exact
   durable record created during merge-time deletion, retaining the lock
   through mutation-result observation, durable evidence persistence, and Issue
   closure;
2. accepts remote absence only when the deletion step is `completed`, or under
   the narrow `executing` recovery rule above after all applicable checks are
   re-proven; absence in `pending` fails closed;
3. refreshes trusted identity, merge, default-ref, protection, and activity
   evidence, and proves the retained dedicated worktree is still clean and
   inactive;
4. immediately rechecks activity before removing only the recorded exact
   dedicated worktree, using its own durable `pending -> executing ->
   completed` step;
5. deletes only the recorded exact local task branch using a separate durable
   step after proving it is neither shared, default, protected, updated,
   active, nor ambiguously owned; and
6. records final evidence and closes the Issue only after both local cleanup
   steps complete.

Every mutation records `executing` before invocation and `completed` only after
success is observed. If a local resource is absent during recovery, it may be
accepted only when its step is already `completed`, or under the same narrow
`executing` recovery rule with exact identity and all remaining checks
re-proven. An absent resource in `pending` blocks.

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
- An invalid repository/component graph, canonical checkout mismatch,
  unavailable central Issues, unavailable repository-scoped credential, or
  non-immutable package mapping blocks work before any external mutation.
- Failed deployment blocks the deployment Issue and never triggers a production
  promotion.
- Failed or ambiguous remote deletion or local cleanup keeps the lifecycle lock
  while the Oracle safely records the failure and completed-step state, then
  leaves the task open. A later attempt reacquires the lock and resumes
  idempotently from that record; it never weakens merge identity, ancestry,
  cleanliness, activity, protection, ownership, or atomic-lease checks.
- Attempts are bounded. A later runner resumes from observed state rather than
  repeating mutations blindly.
- Cleanup removes only worktrees and runtime artifacts owned by the completed
  task; it never deletes product or deployment repositories.
