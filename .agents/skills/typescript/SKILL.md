---
name: typescript
description: Implement or review TypeScript domain, server, browser and test code in registered projects. Use for affected .ts or .tsx files, following the local tsconfig, schema library and lint rules.
---

# TypeScript best practices

## Contents

- [Design and module boundaries](#design-and-module-boundaries)
- [Style and type modeling](#style-and-type-modeling)
- [Runtime data and narrowing](#runtime-data-and-narrowing)
- [Functions and asynchronous work](#functions-and-asynchronous-work)
- [Errors and resource outcomes](#errors-and-resource-outcomes)
- [Collections and data flow](#collections-and-data-flow)
- [Testing](#testing)
- [Performance](#performance)
- [Security](#security)
- [Anti-slop review](#anti-slop-review)
- [Tooling and verification](#tooling-and-verification)

Read the affected package's `tsconfig`, package manifest and adjacent patterns.
The registered projects use strict TypeScript but different validation-library
versions; inspect the installed API before adopting a newer pattern. Let the
repository's formatter and lint rules settle formatting.
Read [boundary examples](references/boundaries.md) when changing parsing,
state types or asynchronous errors. Use the official
[narrowing guide](https://www.typescriptlang.org/docs/handbook/2/narrowing.html)
for unfamiliar narrowing behavior.

## Design and module boundaries

- Place code near its owner: domain rules with domain code, transport parsing
  at the input boundary and UI state in the affected component. Extract a
  shared function when it represents one real rule used by multiple callers.
- Favor simple composition over a hierarchy of abstract services. A module
  should expose a small stable contract; avoid a barrel that hides cycles or
  an index file that eagerly imports unrelated server and browser code.
- Keep server-only code out of browser bundles. Check each package's existing
  module and import conventions before moving code across a boundary.

## Style and type modeling

- Follow local `tsconfig`, ESLint and formatter. Use `camelCase` for values,
  `PascalCase` for types/components, `const` for stable bindings and type-only
  imports when configured. Use descriptive names and keep public signatures
  explicit where inference obscures a contract.
- Model mutually exclusive outcomes with a discriminated union. Optional
  fields and flags are fine when combinations are meaningful; avoid them
  when they admit impossible states. Prefer an object parameter when several
  same-type arguments are easy to swap.
- A type alias is useful for a domain shape or state union. Avoid mapped
  types or generics that save no duplication and make a concrete flow harder
  to read.

```ts
type LoadResult<T> =
  | { kind: "ready"; value: T }
  | { kind: "missing" }
  | { kind: "unavailable"; reason: string };

function message(result: LoadResult<string>): string {
  switch (result.kind) {
    case "ready": return result.value;
    case "missing": return "No document found";
    case "unavailable": return result.reason;
  }
}
```

## Runtime data and narrowing

- JSON, route params, form data, environment values and database rows cross
  runtime boundaries. Start at `unknown` and validate or narrow before use;
  TypeScript's types do not inspect runtime values.
- Reuse the package's existing schema library and installed version. The
  current registered apps use Zod 3 and Zod 4; `safeParse` exists in both,
  while some newer helpers and error formatting differ.
- A cast, `any`, `!` or `as const` does not validate external data. Use a
  guard for a small shape and a schema where that is already the convention.
  Narrow nullable values explicitly before calling methods.

```ts
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readTitle(value: unknown): string | null {
  if (!isRecord(value) || typeof value.title !== "string") return null;
  const title = value.title.trim();
  return title.length > 0 ? title : null;
}
```

See the official [narrowing guide](https://www.typescriptlang.org/docs/handbook/2/narrowing.html)
for control-flow behavior.

## Functions and asynchronous work

- Make inputs and outputs clear, especially for exported functions. Keep
  impure effects near the boundary that owns them. Use a named object or
  overload only when it clarifies actual call patterns.
- Await work whose completion matters. An unawaited Promise can lose a
  rejection or let a request return before a write completes. If background
  work is intentional, give it an owner and failure path.
- Use `Promise.all` for independent work only when parallelism is safe and
  the failure policy is clear. Avoid concurrency that violates order,
  transaction boundaries or rate limits.

```ts
async function saveTitle(
  store: { save(title: string): Promise<void> },
  raw: unknown,
): Promise<{ ok: true } | { ok: false; reason: "invalid" }> {
  const title = readTitle(raw);
  if (title === null) return { ok: false, reason: "invalid" };
  await store.save(title);
  return { ok: true };
}
```

## Errors and resource outcomes

- Represent expected missing/invalid results as explicit outcomes where the
  caller needs to branch. Throw for unexpected operational failures and
  preserve their cause/context. Avoid catching everything and returning
  `null` or an empty array.
- Handle errors once at the owning boundary: a route chooses HTTP status,
  a job chooses retry/failure, and a UI chooses a visible message. Logging
  and rethrowing at every layer creates noisy duplicate reports.
- A `finally` block can release resources acquired in the same operation.
  Do not make a cleanup failure look like the primary operation succeeded.

```ts
try {
  await writer.publish(document);
} catch (error) {
  throw new Error("publish document failed", { cause: error });
}
```

Use this wrapper when it adds meaningful context; do not wrap each function
with the same generic message.

## Collections and data flow

- Use `Map` for keyed dynamic records and `Set` for membership when those
  semantics help. Plain objects and arrays remain good choices for JSON and
  ordered data. Do not mutate shared input unexpectedly.
- Prefer a readable `for...of` loop for branching or effects. `map` and
  `filter` suit clear transformations. Avoid repeated full-array scans in a
  hot path when a keyed lookup solves a measured cost.
- Distinguish absence from a valid zero, empty string or `false`. Use `??`
  for a nullish fallback and `||` only when all falsey values should fall
  back.

```ts
const pageSize = input.pageSize ?? 20; // 0 remains 0 for later validation
```

## Testing

- Use the package's existing runner and fixtures. Test valid and invalid
  boundary input, a meaningful state transition and failure reporting when
  those behaviors changed. A mock should replace an external effect, not
  the function under test.
- Assert observable results rather than private helper calls. Include a
  case that a plausible wrong implementation would fail, such as malformed
  input rejected before a write.

```ts
const saved: string[] = [];
const store = { save: async (title: string) => { saved.push(title); } };
const result = await saveTitle(store, { title: "  " });
if (result.ok || saved.length !== 0) throw new Error("invalid title was saved");
```

## Performance

- Measure slow paths before adding memoization or parallelism. React
  rendering and database latency need different remedies. Keep a cache
  bounded and define its invalidation and authorization scope.
- Avoid premature generic event buses, deep cloning of every object or
  memoizing cheap calculations. For large collections, use a single pass
  or lookup map when profiling shows it matters.

## Security

- Validate external input at every trust boundary and authorize protected
  operations where they execute. Client-side checks improve UX but do not
  secure a server mutation.
- Keep credentials and server-only dependencies out of browser modules.
  Treat user-controlled HTML and SQL as data: use React text rendering or
  text APIs, and parameterized queries. Never build a shell command by
  interpolating issue, log or form text.
- Avoid including raw exception details in user-facing responses.

## Anti-slop review

- Reject `as SomeType` immediately after `JSON.parse` without validation.
  Reject a union of flags that can represent contradictory states.
- Reject a new generic repository/provider/factory that only forwards one
  call, and a test that mocks the changed branch to return its expected value.
- Reject `catch { return [] }` for an unavailable dependency and a detached
  Promise for a required write. Show the real failure at its owning boundary.
  [Boundary examples](references/boundaries.md) give shorter bad/better cases.

## Tooling and verification

Run only trusted checks supplied for the assigned package. The registered
apps use different manifests, Zod versions and validation entrypoints;
do not invent a universal lint/test script or install a new compiler. Record
which checks ran and which behavior still needs an approved environment.
