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
4. The Oracle initializes that repository's own canonical Beads database,
   configures its own Dolt remote from trusted host configuration, performs the
   ownership/mode/readability preflight, and proves a pull/check/push cycle.
5. The repository adds bounded validation that is safe on untrusted source.
   Host configuration represents each invocation as an executable followed by
   an argument array; no command comes from a Bead or is passed to a shell.
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
broad credentials, invalid command arrays, unsynchronized Beads, duplicate
package identities, dangling component references, or a mutable tag policy all
fail closed before claim, push, publication, or deployment.

For every external operation, unattended preflight selects the operation key
from the target repository's `credential_refs`, resolves that non-secret key
through the trusted provider, and verifies the returned authorization audience
before use:

- source fetch uses `git_read`; branch push and pull-request mutation use
  `git_write` for that exact source repository;
- canonical task-state pull/push uses `beads_sync` for that exact Beads remote;
- GHCR image verification uses `package_read` constrained to that product's
  declared GHCR package set; and
- GitOps observation and GitOps branch/pull-request mutation use `gitops_read`
  and `gitops_write` from the target `website-k8s` registration, never from the
  product registration.

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

## Public snapshot publication

Public task visibility is a separate, optional workflow. Merely registering a
repository does not publish it. Root-owned host configuration must enable the
global `public_dashboard` registration and bind its exact object audience/ref,
public read URL, factory publisher policy, root-owned public-copy manifest,
and separate object-publish and cache-purge credential
references. Each contributing repository must also explicitly enable its own
`public_dashboard`, choose a public alias and display name, and select a policy
that permits contribution export. Missing, conflicting, overly broad, or
unresolved values deny the operation without credential fallback.
Before enabling automation, the operator provisions the bound object once as a
schema-valid empty snapshot. The global binding must require conditional
replacement by exact observed prior generation and a non-reusable,
monotonically advancing generation for every replacement. Content ETags,
absence-based creation, and generations that reset or can be reused do not
qualify. The factory-control repository follows the same independent
contribution opt-in as any product; global publisher authority alone does not
expose its Beads.

The operator owns `/etc/software-factory/public-dashboard-copy.yaml`, outside
repositories and Beads. Its monotonic authorization revision, canonical
content digest, and per-task digests bind each exact normalized repository
identity and canonical Bead ID to exact public ID, title, and summary values.
The exporter ignores purported approval in Bead or repository content. There
is no repository-wide title policy in the initial version. Unknown tasks,
duplicates, changed content or digest, and reuse for another repository fail
closed.

On the configurable schedule (initial default 60 seconds), the Oracle-owned
read-only exporter:

1. reads each enabled repository independently after its normal synchronized
   canonical-state checks and joins tasks only to exact current manifest
   entries;
2. constructs allowlisted public fields one by one, never by copying raw `bd`
   output, excluding tasks without approved public copy and relationships whose
   other endpoint is not public;
3. records `observedAt` for the attempt and, on success,
   `lastSuccessfulSyncAt` for the derived task set;
4. retains only the currently authorized subset of a failed repository's last
   valid set as `stale`, or marks it `unavailable` without a task set if no
   successful snapshot exists;
5. assembles a complete candidate in private runtime storage, stamps the
   prospective `publishedAt`, captures the current manifest revision and
   digest in its private publication record, and validates the exact version,
   closed field sets, enums, timestamps, relationship integrity,
   per-repository task limit, and global byte limit; and
6. acquires the exclusive public-dashboard publication/revocation lock and
   first reconciles any durable operation still in `executing`, then reloads
   registration and manifest and reauthorizes current and stale tasks;
7. observes the exact remote object generation and persists a
   `pending` record with that precondition, authorization revision/digest,
   candidate digest, stable operation ID, empty successor generation, and empty
   observed result; and
8. persists `executing`, invokes conditional replacement with the recorded
   prior generation and idempotency token where supported, observes the
   non-reusable successor generation and content, proves through provider
   evidence or trusted object metadata that the backend accepted/deduplicated
   that exact operation and every older generation precondition is permanently
   invalid, confirms relevant cache invalidation, persists the observed result
   and `completed`, and only then releases the lock. Matching content without
   successor-generation and exact-operation proof is not completion. A failed
   check or validation leaves the previous object intact.

Repositories can have different observation times in one publication; this is
not a globally transactional snapshot. The dashboard initially refreshes the
object every 30 seconds and warns after 5 minutes without a successful sync.
These timings are configurable defaults. It must present `unavailable` as
unknown data rather than zero tasks, and must not describe `in_progress` as
proof of a live worker.

Revocation acquires the same exclusive lock before changing the trusted
authorization revision or manifest and first reconciles any earlier
`executing` publication or revocation. While holding the lock, it advances the
revision and manifest only after observing the current remote generation
and persisting a `pending` record that binds the current and intended
authorization revisions/digests, expected remote precondition, candidate
digest, and operation ID. It durably applies the new manifest, moves to
`executing` before the external call, and conditionally replaces the object
with a snapshot reauthorized against the new manifest. Revoking all
publication replaces it with the schema-valid empty snapshot. The publisher
never deletes the object. The operation remains `executing` until the
non-reusable successor generation, expected content, and exact-operation proof
are observed and the relevant cache purge is confirmed; only then does it
persist `completed` and release the lock.

A publication already admitted under the lock finishes before revocation may
start. A candidate merely built under an older revision is rejected after it
later acquires the lock. A timeout, lost acknowledgement, or ambiguous remote
or cache response stays `executing`; while the process is alive the lock stays
held, and after interruption its durable state blocks admission. Recovery
reacquires the lock and records success only after observing the expected
successor generation plus evidence that the backend accepted/deduplicated the
exact operation and permanently fenced every older generation. Desired content
by itself is insufficient. Otherwise it retries only with the recorded
prior-generation precondition and operation ID.
No later candidate can publish until this reconciliation completes, so a
delayed old write cannot restore revoked data.

Disabling the global publisher, repository, or task follows this path.
Revocation is complete only when the exact object at the non-reusable successor
generation is confirmed to contain only the newly authorized or valid empty
snapshot, the exact operation is proven, relevant cache invalidation is
confirmed, and no prior uncertain mutation remains. A source outage cannot
preserve revoked stale data. Previously downloaded copies cannot be recalled.
Physical object deletion is an operator-only post-disable action after every
ambiguous operation is reconciled and automation is unable to issue writes; it
is outside publisher workflow and authority. The exact schema and content
prohibitions are defined by
[ADR 0002](decisions/0002-public-beads-dashboard.md).

The implementation validation profile must fault-test forged task metadata,
modified public copy or digest, unknown task IDs, cross-repository approval
reuse, source outage after revocation, and revocation racing both a built
candidate and the final publication step. It must also inject timeouts and
ambiguous acknowledgements for replace and cache purge; generation conflicts;
delayed writes; and restarts, proving recovery fencing and the gate that blocks
later candidates until reconciliation. The required ABA test starts an initial
publish at `G0`, loses its acknowledgement, retries/recovers it as `G1`,
replaces it for revocation as `G2`, and proves the delayed original `G0`
upload fails.

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

1. The Oracle pulls the repository and Beads state.
2. List ready work and select exactly one task.
3. Claim the task through the Oracle.
4. The Oracle creates `codex/<bead-id>-<slug>` in a dedicated worktree.
5. Construct the Codex prompt from trusted factory instructions plus the Bead
   as clearly delimited untrusted task data.
6. Run Codex with workspace-write, no broad host access, and structured output.
7. Execute validation commands from repository configuration as executable and
   argument arrays, without shell interpretation and never from Bead text.
8. Request read-only review when the configured risk policy requires it.
9. The Oracle pushes the branch and opens a pull request containing evidence,
   the Bead ID, and a statement that the Oracle will delete the exact remote
   task ref after a verified true merge. A GitHub auto-delete setting may
   exist, but the factory neither enables nor trusts it as lifecycle evidence.

Delegated architects, implementation workers, and reviewers do not create or
delete branches or worktrees, mutate pull requests, or perform lifecycle
cleanup. Architects and reviewers make no external mutations. Delegated roles
run only trusted validation commands supplied by the Oracle or recorded in
host configuration.

Every activation of a task worktree, including the start of a worker, reviewer,
or other factory run, must acquire shared participation in the same exact
repository/task lifecycle lock used by cleanup and retain it until that run is
inactive. A run cannot start while the Oracle holds the exclusive lock, and the
Oracle cannot acquire exclusivity while a run holds shared participation. An
activity marker or one-time check of the lock is not sufficient on its own.

## Deployment

1. CI validates the merged application commit.
2. CI publishes every affected component package with a
   `sha-<full 40-character commit>` tag and OCI source/revision metadata.
3. The Oracle creates or claims a linked deployment Bead in `website-k8s`.
4. A dedicated change updates every workload image mapped to the affected
   component, including matching jobs and scheduled jobs, to that exact tag.
5. The GitOps pull request is reviewed and merged under the environment policy.
6. ArgoCD reconciles the desired state.
7. A read-only observer checks ArgoCD health, pod readiness, relevant logs, and
   public health endpoints.
8. The deployment Bead and then the product Bead become eligible for local
   cleanup and closure after verification; their merged remote task refs were
   already handled by the merge-time lifecycle phase.

## Merge-time remote branch deletion

The Oracle owns every lifecycle mutation. Immediately after a successful merge
is observed, and before waiting for image, deployment, or promotion delivery,
it first requires `lifecycle.delete_merged_remote_branch: true` from the
selected root-owned policy. `git.delete_branch: false` remains the prohibition
for delegated and model-controlled Git operations; the lifecycle key authorizes
only this deterministic Oracle procedure and never a model-produced command.
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

The Bead remains open, and the dedicated worktree and local task branch remain
available, until its requested delivery level is verified. The Oracle then:

1. reacquires the exclusive repository/task lifecycle lock and loads the exact
   durable record created during merge-time deletion, retaining the lock
   through mutation-result observation, durable evidence persistence, and Bead
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
6. records final evidence and closes the Bead only after both local cleanup
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
  unsynchronized Beads database, unavailable repository-scoped credential, or
  non-immutable package mapping blocks work before any external mutation.
- Failed deployment blocks the deployment Bead and never triggers a production
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
