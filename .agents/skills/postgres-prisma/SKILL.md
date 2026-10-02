---
name: postgres-prisma
description: Implement or review PostgreSQL schema, SQL migrations and Prisma data-access changes in registered apps. Use for affected .sql, .prisma or database-query files, not ordinary TypeScript edits.
---

# PostgreSQL and Prisma changes

Read the target `AGENTS.md`, `schema.prisma`, migration history, database
client setup and nearby queries. The registered apps use Prisma 6 and 7 with
different generator, datasource and adapter configuration. Check the installed
version and its matching documentation before changing those APIs; current
upstream defaults may describe a newer major release.

- Name models, fields, constraints and indexes consistently with the existing
  schema and SQL. Choose database constraints for invariants that must hold
  across every writer; pair them with clear application errors where needed.
- Preserve applied migration history. Add a forward migration for a schema
  change and consider existing rows, defaults, nullability, backfill order and
  compatibility with code that may run during rollout. Do not rewrite old
  migration files to make a fresh database pass.
- Shape queries around required rows and columns. Inspect filter, join and
  sort paths before proposing an index; account for write cost and existing
  indexes. Treat `NULL`, absent input, empty string and zero as distinct values.
- Parameterize runtime values. Use Prisma's tagged `$queryRaw` or the
  repository's query API; never concatenate user input into SQL. Dynamic table
  or column names require a reviewed allowlist, since value parameters cannot
  stand in for identifiers.
- Use a transaction when several writes form one atomic domain operation.
  Keep its work bounded and propagate failure. Follow the application's
  existing shared-client and pool lifecycle; do not create a client per request
  or invent a new pool policy.
- Validate with only the trusted command supplied for the task. A generic
  build does not prove a migration on populated data. Do not run migrate,
  reset, seed or direct SQL against a live database as routine validation;
  report the gap if an approved test database is unavailable.

Read [query and migration examples](references/query-and-migration.md) when
changing raw SQL or schema evolution. Match Prisma's versioned
[transactions](https://www.prisma.io/docs/orm/v7/prisma-client/queries/transactions),
[raw SQL](https://www.prisma.io/docs/orm/v7/prisma-client/using-raw-sql/raw-queries)
and [migration-history](https://www.prisma.io/docs/orm/v7/prisma-migrate/understanding-prisma-migrate/migration-histories)
guides to the project version. PostgreSQL's
[constraint reference](https://www.postgresql.org/docs/current/ddl-constraints.html)
explains database-enforced invariants.
