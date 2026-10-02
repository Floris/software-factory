---
name: nextjs
description: Build or review Next.js route, server action and React changes in the factory's Next.js projects. Use when affected files are Next.js app code; follow the installed version and repository conventions.
---

# Next.js application changes

Read the target `AGENTS.md`, `package.json`, relevant route and nearby tests.
The registered apps currently span Next.js 15 and 16, so check the installed
version and official documentation before adopting an API whose behavior may
have changed. Keep the repository's App Router and established data flow.

- Keep data access, credentials and authorization on the server. Check identity
  and resource access inside the server action or route handler that performs
  a mutation; a hidden button or protected layout is not that check.
- Use a Server Component for server-rendered data and add `use client` only
  where interaction or browser APIs need it. Pass the smallest serializable
  props across that boundary. In React, compute derived display values during
  render and perform user-triggered work in event handlers; use an Effect when
  synchronizing with an external system. Give list items stable identity keys.
- Treat form, URL and API inputs as untrusted at their entry point. Model
  expected validation errors distinctly from operational failures; preserve
  status and diagnostic context for the latter.
- Choose cache, revalidation and dynamic rendering based on the data's
  freshness and authorization rules. Confirm version-specific defaults before
  changing them. Preserve an existing route's explicit cache contract, such as
  `force-dynamic` with a bounded public-data cache, unless the task changes its
  freshness requirement. Do not cache user-specific responses without a proven
  key and invalidation path.
- Keep loading, empty and error states meaningful in the existing UI. Preserve
  accessible controls and keyboard operation for changed interactions.
- Use the repository's declared lint, typecheck, test and build entrypoints as
  supplied by the Oracle. Do not infer that a script present in one Next.js
  repository exists in another.

For route-boundary examples, read [server boundaries](references/server-boundaries.md)
when adding a mutation, fetch or cache decision. Check the installed release
against the official [security](https://nextjs.org/docs/app/guides/data-security),
[component-boundary](https://nextjs.org/docs/app/getting-started/server-and-client-components)
and [caching](https://nextjs.org/docs/app/guides/caching-without-cache-components)
guides before adopting a version-sensitive API.
