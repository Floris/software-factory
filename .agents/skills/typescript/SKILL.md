---
name: typescript
description: Implement or review TypeScript domain, server, browser and test code in registered projects. Use for affected .ts or .tsx files, following the local tsconfig, schema library and lint rules.
---

# TypeScript with honest boundaries

Read the affected package's `tsconfig`, package manifest and adjacent patterns.
The registered projects use strict TypeScript but different validation-library
versions; inspect the installed API before adopting a newer pattern. Let the
repository's formatter and lint rules settle formatting.

- Use local `camelCase` for values/functions and `PascalCase` for types and
  components. Prefer `const` for bindings that do not change and type-only
  imports where the package's compiler settings support them.
- Use `unknown` for external values until runtime validation or narrowing
  proves their shape. Static types disappear at runtime. Prefer an existing
  local schema for transport or persistence boundaries.
- Model meaningful states with a discriminated union when boolean flags or
  optional fields permit impossible combinations. Favor a named object or
  union over a generic with no real second use. Keep types close to the data
  they describe; infer from a schema when that is the local convention.
- Prefer straightforward control flow and explicit return values. Avoid `any`,
  unverified casts and non-null assertions as substitutes for an actual check.
  A narrow cast is acceptable when an external API's contract is proven and
  the limitation is documented nearby.
- Keep asynchronous failures observable. Await work whose completion matters;
  return or propagate a useful error instead of silently swallowing a rejected
  promise.
- Test both valid and invalid input at changed boundaries, plus the domain
  state transition being changed. Run only the repository's trusted validation
  commands supplied for this task; do not invent a linter or test command.

Read [boundary examples](references/boundaries.md) when changing parsing,
state types or asynchronous errors. Use the official
[narrowing guide](https://www.typescriptlang.org/docs/handbook/2/narrowing.html)
for unfamiliar narrowing behavior.
