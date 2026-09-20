# ADR 0002: Publish a sanitized snapshot to a separate public dashboard

## Status

Accepted as a design contract. The exporter, schema, publisher, dashboard
product repository, static/object publication, and deployment do not yet
exist.

## Context

People need a public, read-only view of selected factory work. Canonical Beads
databases contain considerably more information than is safe to publish:
descriptions, acceptance criteria, comments, ownership, internal references,
paths, commands, logs, and even a task title can disclose private details.
Giving a web application read access to `.beads`, Dolt, or canonical
checkouts would also collapse the factory's trust boundary. Read-only access
to a sensitive source is not the same as public-safe data.

The repositories are synchronized independently. A temporary failure in one
repository must not make another repository look empty, and an exporter must
not replace a last known-good public view with malformed or partial output.

## Decision

The public dashboard will be a separate Next.js product in its own product
repository. This control repository defines only its publication contract.
Its application and deployment code belong respectively in that product
repository and `website-k8s`.

The trusted Oracle will own a deterministic, read-only exporter. It reads only
explicitly registered repositories whose `public_dashboard.enabled` value is
true, converts their canonical task state to a versioned candidate snapshot,
and rejects every field not in the public allowlist below. Publication is a
separate capability and process boundary: a narrowly scoped publisher can
write only the configured public snapshot object and invalidate its cache. It
cannot read Beads or source repositories. Export permission does not imply
publish permission, and both default to denied.

One optional, top-level host registration binds the exact object audience and
object ref, public read URL, publisher policy, operation-scoped publish and
cache-purge credential references, and a public-copy manifest at
`/etc/software-factory/public-dashboard-copy.yaml`. This root-provisioned,
operator-owned manifest is outside every repository and Beads database.
Repository and Bead content cannot create, modify, or imply approval.

For the initial version, explicit manifest entries are the only public-copy
authority; there is no repository-wide title policy. The versioned manifest
contains a monotonically increasing `authorizationRevision`, a digest of its
canonical contents excluding that digest field, and entries mapping the exact
normalized repository identity plus canonical Bead ID to exact `publicId`,
`publicTitle`, and `publicSummary` values. Each entry carries a digest over
that full mapping.
An absent entry makes a task private. An incomplete entry, duplicate or
unknown task, changed or incorrectly digested mapping, or cross-repository
reuse rejects the candidate. The exporter ignores similarly named fields in
Beads or repository files.

Raw `bd` output is never copied, forwarded, cached, or published. The exporter
constructs new values field by field. Publication follows this sequence:

1. read and sanitize each opted-in repository independently, joining canonical
   tasks to the exact current manifest entries by normalized repository
   identity and canonical Bead ID;
2. write the candidate, including its prospective `publishedAt`, to private
   runtime storage and capture the manifest revision and digest in its private
   publication record (not in the public snapshot);
3. validate it there against the exact supported schema, including recursive
   rejection of unknown fields and configured size/count limits;
4. acquire the exclusive public-dashboard publication/revocation lock, reload
   and reconcile any earlier `executing` operation, then reload the host
   registration and manifest, reject any revision or digest change, and
   revalidate every current and stale task authorization; and
5. record the observed exact remote generation and durable operation
   state, then conditionally replace the exact public object through the
   separately scoped publisher while retaining the lock through remote outcome
   observation, cache-purge confirmation, and the final durable state.

A repository export failure may retain only the still-authorized subset of
that repository's last valid public task set and marks it `stale`. If it has
never produced a valid snapshot, it is `unavailable` and has no task set; the
UI must not present that as zero work.
Other repositories can still be published. A failed whole-candidate
validation or publication leaves the previous public object untouched. The
snapshot is therefore not a globally transactional observation of all
repositories.

`observedAt` is when a repository read was attempted, `lastSuccessfulSyncAt`
is when its published task set was last successfully derived from synchronized
canonical state, and `publishedAt` is when the complete validated public
object became visible. These values are not interchangeable.

### Public snapshot allowlist

Version `1` allows exactly these fields; every object uses
`additionalProperties: false` semantics:

- snapshot: `schemaVersion`, `publishedAt`, `repositories`;
- repository: `publicAlias`, `displayName`, `availability`, `observedAt`,
  `lastSuccessfulSyncAt`, `tasks`;
- task: `publicId`, `publicTitle`, `publicSummary`, `status`, `priority`,
  `taskType`, `createdAt`, `updatedAt`, `relationships`; and
- relationship: `type`, `publicId`.

`schemaVersion` is the exact supported integer version. Timestamps are UTC
RFC 3339 values. `availability` is one of `available`, `stale`, or
`unavailable`; `tasks` is forbidden for `unavailable` and required otherwise.
Task status, priority, type, and relationship type are closed enums defined by
the eventual versioned schema, not pass-through strings. `publicId` is a
stable, public-safe identifier in the repository's public namespace.
Relationships are emitted only when both endpoint tasks are approved for
publication; dangling or cross-private relationships are dropped.

Task titles and summaries are not implicitly safe. Each task needs the exact
`publicId`, `publicTitle`, and `publicSummary` mapping approved in the current
root-owned manifest. There is no implicit or repository-wide fallback.
Missing or invalid approval excludes the task rather than exposing canonical
title, body, or task-supplied purported public fields.

The exporter never publishes task bodies/descriptions, acceptance criteria,
comments or notes, owners, assignees, email addresses, internal labels or
metadata, external references, repository paths or remotes, commands, logs,
evidence, credentials, or arbitrary URLs. The dashboard renders allowed
strings as escaped plain text. It supports no HTML or MDX, external images, or
arbitrary links.

The Next.js application fetches only the one configured public snapshot
origin. It has no access to `.beads`, Dolt, canonical repositories, the host
filesystem, credentials, Git, Kubernetes, mutation endpoints, Server Actions,
or a generic fetch proxy. It validates the fetched version and fields before
rendering and fails closed for unknown versions or fields.

Initial configurable defaults are a 60-second export interval, 30-second
client refresh interval, and a stale warning after 5 minutes. `in_progress`
means only that canonical task state had that value at
`lastSuccessfulSyncAt`; it does not prove a worker is currently active.

### Publication and revocation serialization

Publication and revocation share one exclusive public-dashboard lock. Every
trusted authorization revision or manifest change and every external publisher
mutation occurs only after acquiring it. The lock remains held through durable
state writes, acknowledged mutation, observation of the exact remote result,
cache-purge confirmation, and durable completion.

Before automation is enabled, the operator provisions the exact object once as
a schema-valid empty snapshot. The publisher never deletes it. Automated
publication and revocation only replace it, conditionally on its exact recorded
prior generation. The backend must assign a non-reusable, monotonically
advancing generation across every replacement. Content ETags,
`If-None-Match` against absence, or versions that reset or can be reused are
insufficient because they do not fence delayed writes across an ABA cycle.

A durable provider idempotency key is an additional defense but does not
replace the generation requirement unless the provider guarantee itself
permanently fences duplicate attempts. Before an external call, the Oracle
persists a record containing the expected prior generation, authorization
revision and manifest digest, candidate digest, operation ID, and an initially
empty successor generation and observed result. Each publication or revocation
moves durably through `pending -> executing -> completed`; `executing` is
persisted before invocation.

Completion requires observing the non-reusable successor generation and proof
that the backend accepted or durably deduplicated that exact operation, as well
as matching object content, confirmation that every older generation
precondition is permanently invalid, and confirmed relevant cache invalidation.
Desired content alone is not proof. The exact operation ID and candidate digest
must be observable in provider evidence or trusted object metadata outside the
public JSON schema.

Revocation acquires the lock before advancing the trusted authorization
revision or changing the manifest. While still holding it, the operation
observes the remote generation and persists `pending` with the current and
intended authorization revisions/digests before durably applying the new
manifest. It then persists `executing` before conditionally replacing the
object with the newly authorized snapshot. Revoking all publication replaces
it with the schema-valid empty snapshot. A candidate built before the change
is rejected when it later acquires the lock. An external publication already
admitted under the lock finishes before revocation can begin; if its result is
uncertain, it must be reconciled before revocation or any other operation can
proceed.

A timeout, lost acknowledgement, or ambiguous response remains `executing`.
No later publication or revocation may start. Recovery reacquires the same
lock and observes the remote generation, content, and exact-operation evidence.
It records success only for the expected successor generation accepted for
that operation, or retries with the recorded prior-generation precondition and
operation ID. This fencing prevents a delayed old write from restoring revoked
data; an unresolved operation continues to block.

At the completed revocation boundary, the object is confirmed at the
non-reusable successor generation with only the snapshot authorized by the new
revision (or the valid empty snapshot), the backend proves the exact operation,
the relevant cache invalidation is confirmed, and no earlier uncertain
mutation remains. Stale tasks survive only after matching them against that
current manifest, including during a source outage.

Disabling the global publisher, a repository, or a task uses this revocation
path. Already downloaded data cannot be recalled, so approval must assume
published values are permanently copyable.

Physical deletion is an operator-only post-disable lifecycle action, outside
publisher authority and workflow. It may occur only after every
`executing`/ambiguous operation is reconciled and automation is unable to issue
writes to the object.

Before implementation is accepted, fault tests must prove rejection of forged
Bead public metadata, modified copy or digest, unknown canonical task IDs,
cross-repository approval reuse, a source outage after revocation, and a
revocation racing an already built or publishing candidate. They must also
cover timed-out or ambiguous replace and cache-purge responses,
remote-generation conflicts, delayed old writes, restart recovery, and the
gate that blocks later candidates until reconciliation. The exact replay test
is: initial publication from `G0` loses its acknowledgement, retry/recovery
establishes `G1`, revocation replaces it at `G2`, and the delayed original
`G0` upload is rejected.

## Alternatives considered

- **Let the dashboard query Beads or Dolt read-only.** Rejected because it
  exposes a sensitive schema and host access to an Internet-facing product;
  future source fields could become public without review.
- **Publish raw `bd` JSON and hide fields in the UI.** Rejected because hidden
  fields still cross the public boundary and client-side filtering is not a
  security control.
- **Generate pages in this control repository.** Rejected because product code
  and deployment state have different owners and lifecycles.
- **Use one globally transactional aggregation run.** Rejected for the first
  version because independent repository availability is more useful and less
  brittle; the snapshot carries per-repository observation times instead.
- **Publish directly from the exporter.** Rejected because separating source
  read authority from public write authority limits credential impact and
  makes publication independently revocable.
- **Approve titles through repository configuration or task metadata.**
  Rejected because repository-controlled input could then grant itself public
  disclosure. The root-owned manifest is the sole copy authority for the
  initial version.

## Consequences

Public visibility is explicit and fail-closed, and the web product remains
outside the trusted factory. The cost is an additional schema, sanitizer,
publisher, cache-purge path, root-owned copy manifest, serialized revocation,
fault tests, and clear stale or unavailable UI states. Data can differ between
repositories within one snapshot, and public data remains copyable after
revocation. Any schema or manifest change requires a reviewed version change
and coordinated exporter and consumer support.
