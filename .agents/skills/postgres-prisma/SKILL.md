---
name: postgres-prisma
description: Implement or review PostgreSQL schema, SQL migrations and Prisma data-access changes in registered apps. Use for affected .sql, .prisma or database-query files, not ordinary TypeScript edits.
---

# PostgreSQL and Prisma best practices

## Contents

- [Schema and data contracts](#schema-and-data-contracts)
- [Migrations and rollout](#migrations-and-rollout)
- [Query design](#query-design)
- [Transactions and concurrency](#transactions-and-concurrency)
- [Client lifecycle and errors](#client-lifecycle-and-errors)
- [Testing](#testing)
- [Performance](#performance)
- [Security](#security)
- [Anti-slop review](#anti-slop-review)
- [Tooling and verification](#tooling-and-verification)

Read the target `AGENTS.md`, `schema.prisma`, migration history, database
client setup and nearby queries. The registered apps use Prisma 6 and 7 with
different generator, datasource and adapter configuration. Check the installed
version and its matching documentation before changing those APIs; current
upstream defaults may describe a newer major release.
Read [query and migration examples](references/query-and-migration.md)
for schema evolution and raw SQL. Match the linked versioned documentation
in the chapters below to the project's installed Prisma major.

## Schema and data contracts

- Let the database enforce invariants that must hold across every writer:
  primary/foreign keys, uniqueness, non-nullability and appropriate checks.
  Application validation provides a useful message before a write but is
  not a substitute for a durable constraint.
- Name models, columns, relations and constraints consistently with the
  existing schema. Distinguish `NULL`, absent input, empty string and zero
  where the domain does. Choose types that represent the actual value and
  precision; do not store exact quantities in a floating-point column.
- Review delete behavior and referential actions before adding a relation.
  A default cascade may remove more data than the task intended.

```sql
CREATE TABLE "Document" (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title text NOT NULL CHECK (length(trim(title)) > 0),
    slug text NOT NULL UNIQUE
);
```

This is a standalone example, not a migration to paste into either app.
PostgreSQL's [constraint reference](https://www.postgresql.org/docs/current/ddl-constraints.html)
explains enforcement and naming.

## Migrations and rollout

- Treat applied migration files as history. Add a forward migration rather
  than editing an old one. Keep `schema.prisma`, generated client and SQL
  migration intent aligned according to the project's Prisma version.
- For a new required column on populated data, use separate expand and
  contract releases. Keep the column nullable (or provide a reviewed
  compatible database default) while old writers may still insert rows.
  Deploy readers and writers compatible with both shapes, then retire old
  writers before enforcing `NOT NULL`. A one-time backfill before that gate
  does not protect against later old-client inserts.
- For an index or constraint on a large table, consider lock duration and
  duplicate existing rows. Do not assume a migration that works on an
  empty database works on production-shaped data.

Expand release: add a nullable column in its own forward migration. Old
Prisma clients can still insert a document without `displayName`.

```sql
ALTER TABLE "Document" ADD COLUMN "displayName" text;
```

Deploy code that reads the old and new shapes and populates the new column
on every write. Keep both compatible during overlap. After all old writers
are drained or retired (or a reviewed default/trigger protects their writes),
run an approved, bounded catch-up backfill until zero nulls remain. The
backfill rule and batch/lock strategy depend on real data volume.

Contract release: verify zero nulls again after that gate, then apply a
separate forward migration for the constraint.

```sql
SELECT count(*) FROM "Document" WHERE "displayName" IS NULL;
-- Proceed only when the result is zero and all remaining writers populate it.
ALTER TABLE "Document" ALTER COLUMN "displayName" SET NOT NULL;
```

Do not ship the expand and contract steps as one automatically applied batch
while old writers may still be active. The release gate, transaction and lock
strategy need review for the actual deployment. See Prisma's
[version 7 migration history guide](https://www.prisma.io/docs/orm/v7/prisma-migrate/understanding-prisma-migrate/migration-histories);
use matching version 6 docs for the other app.

## Query design

- Select only the rows and columns the caller needs. Make pagination order
  deterministic. Bound user-controlled limits and understand the difference
  between offset and cursor pagination before changing an established API.
- Place filters and sort keys where existing indexes can support the query.
  Add an index for an observed access pattern and inspect write/storage
  cost; a redundant index slows mutations.
- Use Prisma query APIs for ordinary reads and writes. Reach for raw SQL
  when a needed PostgreSQL operation is not expressed well by the installed
  client and a parameterized query is clear.

```ts
const documents = await prisma.document.findMany({
  where: { ownerId },
  select: { id: true, title: true },
  orderBy: [{ createdAt: "desc" }, { id: "desc" }],
  take: Math.min(requestedLimit, 100),
});
```

Validate `requestedLimit` as a positive finite integer before this query.
The field names are illustrative; preserve the target schema's names.

## Transactions and concurrency

- Use `$transaction` when several database writes must commit or fail as
  one domain operation. Keep work short and bounded; avoid network calls
  inside an interactive transaction. A database transaction covers its
  own database work, not email, HTTP calls or other external effects.
- Think about concurrent writers. A read-then-write check can race; use a
  database constraint, conditional write or appropriate isolation strategy
  for an invariant that must survive concurrency.
- Retry only known transient failures when the operation is safe to repeat
  and attempts are bounded. An ambiguous external side effect is not
  automatically safe to replay.

```ts
await prisma.$transaction(async (tx) => {
  await tx.document.update({
    where: { id: documentId },
    data: { title: nextTitle },
  });
  await tx.auditEvent.create({
    data: { documentId, action: "title_updated" },
  });
});
```

The example is database-only. Authorization and input validation still
belong at the caller boundary. See Prisma's
[version 7 transaction guide](https://www.prisma.io/docs/orm/v7/prisma-client/queries/transactions);
check the installed major before adapting APIs.

## Client lifecycle and errors

- Reuse the application's existing client and pool factory. The two apps
  use different Prisma 6/7 generator, datasource and adapter layouts;
  do not copy a newer client constructor or pool setup across them.
- Handle expected uniqueness/not-found outcomes where the caller can
  choose a response. Preserve unexpected database errors with context
  for diagnostics and do not convert them to "no records".
- Close a process-owned client on shutdown according to existing
  lifecycle. Do not create a client per request or disconnect a shared
  client after one route finishes.

## Testing

- Test meaningful query and migration behavior in an approved disposable
  database when supplied. Seed representative old rows to exercise
  nullability/backfill, uniqueness and concurrent or failure behavior
  relevant to the change. For an expand/contract migration, test that an old
  client can still insert during overlap, that compatible writers populate
  the column, and that the constraint succeeds after old writers retire and
  catch-up reaches zero nulls.
- A mocked Prisma call can test application branching but cannot prove
  SQL constraints, migration validity or query plans. Name the scope of
  each check. A build/typecheck only proves the generated API usage.
- Never aim routine validation at a live database. When no approved test
  database is available, report the migration behavior as unverified.

## Performance

- Inspect actual query count, returned shape and database plan for a slow
  path. N+1 reads, unbounded lists and sorting without a suitable index
  often matter more than micro-optimizing application code.
- An index trades read speed for writes, storage and maintenance. A cache
  needs staleness, invalidation and authorization rules. Do not add either
  from intuition alone.
- Keep transactions short to reduce lock time; batch work only when it
  preserves domain boundaries and memory limits.

## Security

- Parameterize all runtime values. Prisma's tagged `$queryRaw` binds values;
  `$queryRawUnsafe` plus string interpolation can execute unintended SQL.
  Value placeholders cannot represent table or column identifiers: use a
  reviewed allowlist for truly dynamic identifiers.
- Authorize rows at the server operation and scope queries to the actor's
  permitted resources. A UI filter is not access control.
- Keep connection strings and credentials in approved runtime configuration,
  not migrations, logs or committed generated files.

```ts
const rows = await prisma.$queryRaw`
  SELECT id, title FROM "Document" WHERE "ownerId" = ${ownerId}
`;
```

The tagged template syntax binds `ownerId` as a value. Check the actual
schema names before adapting it. See Prisma's
[version 7 raw-query guide](https://www.prisma.io/docs/orm/v7/prisma-client/using-raw-sql/raw-queries).

## Anti-slop review

- Reject editing an applied migration or adding `NOT NULL` to populated
  data without a default/backfill plan.
- Reject a new client per request, an unbounded `findMany` for a page,
  or an index with no query evidence.
- Reject a mock-only test claimed to validate a migration, a catch-all
  returning an empty list after a database outage, and raw SQL formed
  by interpolating user text. The [query/migration examples](references/query-and-migration.md)
  show the narrower choices.

## Tooling and verification

Run only trusted commands supplied for the target repository. Generated
client and typecheck may be valid offline checks; migration application
needs an explicitly approved disposable database. Do not run `migrate`,
`reset`, `seed` or direct SQL against live data as routine validation.
Report installed Prisma major, checks observed and remaining runtime gaps.
