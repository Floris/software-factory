---
name: nextjs
description: Build or review Next.js route, server action and React changes in the factory's Next.js projects. Use when affected files are Next.js app code; follow the installed version and repository conventions.
---

# Next.js and React best practices

## Contents

- [Route and component design](#route-and-component-design)
- [Server and client boundaries](#server-and-client-boundaries)
- [Input and authorization](#input-and-authorization)
- [Rendering and state](#rendering-and-state)
- [Caching and freshness](#caching-and-freshness)
- [Errors and UX](#errors-and-ux)
- [Testing](#testing)
- [Performance](#performance)
- [Security](#security)
- [Anti-slop review](#anti-slop-review)
- [Tooling and verification](#tooling-and-verification)

Read the target `AGENTS.md`, `package.json`, relevant route and nearby tests.
The registered apps currently span Next.js 15 and 16, so check the installed
version and official documentation before adopting an API whose behavior may
have changed. Keep the repository's App Router and established data flow.
Read [server-boundary examples](references/server-boundaries.md) for mutation,
fetch and cache decisions. Check the installed release against the official
[security](https://nextjs.org/docs/app/guides/data-security) and
[component-boundary](https://nextjs.org/docs/app/getting-started/server-and-client-components)
guides before adopting a version-sensitive API.

## Route and component design

- Follow the app's existing App Router layout, route groups, server actions
  and data-access boundaries. Put one route's work near that route; promote
  shared behavior only when multiple callers have the same contract.
- Keep a component focused on one visible responsibility. Extract a child
  when it owns a distinct interaction or substantial rendering logic, not
  merely because the file crossed an arbitrary line count.
- Use the installed Next.js version. Registered apps currently use 15 and
  16; copy no cache directive, async request API or route convention from
  newer docs without checking that app's package lock and existing code.

## Server and client boundaries

- Fetch protected data and use credentials on the server. Server Components
  can render data and pass serializable, minimal props to a Client Component
  that needs interaction or browser APIs.
- Put `"use client"` on the smallest meaningful interactive boundary.
  A client import can pull its dependencies into the browser bundle; keep
  server-only modules out of that tree.
- A server action is a server endpoint. Validate and authorize inside it.
  A protected page, hidden button or client-provided user ID does not grant
  access to a mutation.

```tsx
// Server component: data stays on the server.
export default async function DocumentPage() {
  const documents = await listVisibleDocuments();
  return <DocumentPicker options={documents.map(({ id, title }) => ({ id, title }))} />;
}
```

The example assumes `listVisibleDocuments` already applies the current
principal's read policy. Keep the client props limited to needed fields.

## Input and authorization

- Treat route params, search params, form data, action arguments and API JSON
  as untrusted. Parse their shape and bounds at the entry point with the
  repository's installed schema library or a small guard.
- Check identity and resource-specific authorization on each read or
  mutation that needs it. Reject an unauthorized direct action invocation
  before a database write or cache invalidation.
- Separate expected validation errors from operational failures. Give a
  field error or suitable 4xx status for bad input; preserve the real
  failure for server diagnostics without leaking details to the client.

```ts
export async function saveTitle(
  documentId: string,
  formData: FormData,
): Promise<{ kind: "invalid" | "saved" }> {
  "use server";
  const parsedId = documentIdSchema.safeParse(documentId);
  const parsed = titleSchema.safeParse({ title: formData.get("title") });
  if (!parsedId.success || !parsed.success) return { kind: "invalid" };
  const actor = await requireActor();
  await assertCanEdit(actor, parsedId.data);
  await updateTitle(parsedId.data, parsed.data.title);
  return { kind: "saved" };
}
```

Adapt the return shape and authorization API to the project. `safeParse`
exists in both registered Zod majors; do not assume every Zod 4 helper
exists in Zod 3.

## Rendering and state

- Render derived values from props and state directly. Use an event handler
  for an event-caused action; use an Effect to synchronize with an external
  system such as a browser subscription. Do not copy props to state solely
  to calculate display text.
- Give list children stable keys from data identity, not their position
  when rows can reorder. Keep form controls labeled and status visible.
- Server and Client Components have different loading and failure paths.
  Use the route's existing loading/error boundaries and make empty data
  distinct from an unavailable dependency.

```tsx
function Count({ items }: { items: readonly string[] }) {
  return <p>{items.length} documents</p>;
}
```

No Effect or extra state is needed for this derived count. See
[React's Effect guidance](https://react.dev/learn/you-might-not-need-an-effect).

## Caching and freshness

- Decide whether data is public or principal-specific, how stale it may be,
  and what event invalidates it. Then choose the installed version's cache,
  revalidation or dynamic rendering mechanism. Preserve existing explicit
  route contracts unless the task changes freshness behavior.
- Next.js 15 distinguishes fetch Data Cache behavior from a static Full
  Route Cache. Do not infer one cache from the other. A route with
  `force-dynamic` opts fetches out of the Data Cache; an existing bounded
  `unstable_cache` around a public database query is a separate contract.
  Check the
  [version 15 caching guide](https://nextjs.org/docs/15/app/guides/caching)
  for that app and version 16 docs for the other.
- A shared cache of protected data needs a proven identity scope and
  invalidation path. Default to the existing per-request data flow when
  those properties are unknown. Avoid indefinite caches for mutable data.

For a public catalog whose product contract allows stale-while-revalidate
with a 300-second revalidation interval, a Next.js 15 fetch may express
that policy when its route configuration permits fetch caching:

```ts
const response = await fetch(publicCatalogURL, {
  next: { revalidate: 300 },
});
if (!response.ok) throw new Error("public catalog unavailable");
const catalog: unknown = await response.json();
```

The interval is not a hard maximum age: a request after it may receive
stale data while refresh runs, and a failed refresh can retain old data.
If the requirement is a hard age limit, define an explicit freshness and
failure policy. Validate the response shape before use. Do not replace an existing
`force-dynamic` plus `unstable_cache` public-query contract with this fetch
example; inspect Next.js 16 configuration before adapting it. Private
documents need an actor-scoped authorized read.

## Errors and UX

- Show meaningful loading, empty, validation, success and failure states for
  changed flows. A failed save must not clear the form and display "Saved".
- Keep operational diagnostics on the server and a safe message in the UI.
  Do not catch an exception and render a normal empty-state page.
- Support keyboard operation and visible focus for controls. Prefer native
  HTML semantics before custom roles.

## Testing

- Test action/route boundaries directly for invalid and unauthorized input;
  a UI test that hides a button does not prove the server enforces access.
- Test changed user interactions at the visible boundary, including a
  rejected save or loading/error outcome when it matters. Use the app's
  existing Vitest or other registered validation, not an assumed command.
- Test caching through observable freshness when the task changes cache
  behavior. Avoid tests that merely assert a directive string exists.

## Performance

- Keep client bundles small by leaving data assembly and server libraries
  on the server. Reduce large serialized props to fields needed by the
  interaction.
- Use measured latency and waterfall evidence before parallelizing fetches
  or adding memoization. Parallel work must preserve authorization,
  ordering and failure semantics.
- Avoid a new client global store for state local to one form or component.

## Security

- Review every server action and route handler as a public entry point.
  Validate input, enforce authorization, parameterize database access and
  keep secrets out of client modules and serialized props.
- Rely on React text escaping for ordinary values; raw HTML needs separate
  sanitization and review. Do not expose stack traces or secret-bearing
  errors to the browser.
- The official [Next.js data-security guide](https://nextjs.org/docs/app/guides/data-security)
  explains server boundaries; verify examples against the app's major
  version before using a newer API.

## Anti-slop review

- Reject `"use client"` on a whole page when only one control is interactive.
  Reject a Server Component that imports browser-only code, or a Client
  Component that imports a secret-bearing server module.
- Reject authorization done only in a layout, hidden button or client
  precheck. Reject `catch { return [] }` when a data source is unavailable.
- Reject automatic Effects that copy props into state, unbounded cache
  entries, and cache changes without a freshness contract. The
  [server-boundary examples](references/server-boundaries.md) show concrete
  failure cases.

## Tooling and verification

Run only the validation commands supplied for the target repository. One
registered app has lint, typecheck, Vitest and build scripts; the other
uses a bounded `npm run ci:validate` entrypoint. Do not install dependencies,
run live workers or call production databases merely to follow this guide.
Report which checks actually ran and any unverified runtime behavior.
