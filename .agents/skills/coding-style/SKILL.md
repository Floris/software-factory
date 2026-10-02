---
name: coding-style
description: Keep scoped code changes clear, idiomatic and verifiable across the factory's project languages. Use for application, test, script or configuration edits; pair with a matching stack skill when relevant.
---

# Code that earns its place

Read the assigned repository's `AGENTS.md`, nearby code, tests and tool
configuration before editing. The requested behavior and local conventions set
the style. Follow an existing formatter or linter; do not impose a new one for
a small change. Keep the public surface, naming and error handling consistent
with the surrounding module unless the task calls for a change.

## Make the change legible

- Express the domain rule directly. Prefer a named function when it captures a
  real concept or removes repeated logic; keep one-use flow in place when a
  helper would only make readers jump between files.
- Handle expected failure at the boundary that owns it. Preserve a useful
  error or status; never turn an unknown failure into apparent success.
- Introduce a dependency, registry, factory, generic type or DI layer only for
  an observed need. Use the repository's existing toolchain first.
- Comment on constraints and surprising decisions. Remove narration of what
  the next line already says, copied boilerplate and dead branches.
- Keep formatting and renaming near the change. Broad reformatting needs its
  own reason and scope.

## Check the claim

Test behavior where a regression would matter: a changed domain rule, input
boundary, failure path or user interaction. An assertion should be able to fail
for a realistic wrong implementation. Do not add tests that merely repeat the
same expression, mock away the behavior being tested or claim a validation ran
when it did not. Run only the trusted checks supplied for the task and report
the observed result.

For caching, memoization, concurrency or a fallback response, identify the
concrete need and define correctness when data is stale or a dependency fails.
A known product requirement may establish that need; performance work needs
evidence of cost. For concrete bad/better examples, read
[anti-slop examples](references/anti-slop.md) when reviewing an abstraction,
failure path or test design.
