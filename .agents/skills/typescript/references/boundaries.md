# Boundary examples

Bad: `const amount = (requestBody as Payment).amount` trusts JSON after a
compile-time assertion. The next operation accepts a string or missing value.

Better: parse the unknown body with the package's existing schema or a small
local guard, then use the narrowed `amount`. Test that missing and malformed
amounts fail before the write. Check the installed schema-library version for
the correct parsing API.

```ts
// Bad: a cast does not validate JSON.
await save((requestBody as Payment).amount);

// Better: the existing schema checks the runtime value.
const parsed = paymentSchema.safeParse(requestBody);
if (!parsed.success) return { kind: "invalid" };
await save(parsed.data.amount);
```

Bad: `{ loading: boolean; data?: Item[]; error?: Error }` can represent
loading, data and error at once.

Better: use `{ kind: "loading" } | { kind: "ready"; data: Item[] } |
{ kind: "failed"; error: Error }` when those are the real states. A switch
then makes unhandled states visible to TypeScript.
