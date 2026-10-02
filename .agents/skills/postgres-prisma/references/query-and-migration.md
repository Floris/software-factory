# Query and migration examples

Bad: build a SQL string from a request parameter and pass it to an unsafe raw
query. A quote in `ownerId` changes the query's meaning.

```ts
await prisma.$queryRawUnsafe(
  `SELECT * FROM "Entry" WHERE "ownerId" = '${ownerId}'`
);
```

Better: bind the value with Prisma's tagged query API. The placeholder is for
a value, not a table or column name. Check the installed Prisma version and
the existing model naming before adapting the example.

```ts
await prisma.$queryRaw`
  SELECT * FROM "Entry" WHERE "ownerId" = ${ownerId}
`;
```

Bad: add a non-null column without a default or backfill to a table with
existing rows, or edit an already applied migration until a fresh database
passes.

Better: plan a forward change that handles existing rows and the rollout's
old/new application overlap. Test it on an approved disposable database with
representative old rows when that environment is supplied; otherwise report
that data-migration behavior remains unverified.
