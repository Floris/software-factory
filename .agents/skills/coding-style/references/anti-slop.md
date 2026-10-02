# Anti-slop examples

These are decision examples, not templates to copy across languages.

## A failed read must remain visible

Bad: a repository lookup catches every exception and returns `[]`, so an
outage renders "no records" and may trigger an empty export.

Better: handle the expected "record absent" case as empty; propagate an
unavailable store as a typed error or failed response with context. Test that
the unavailable store cannot produce a successful export.

## Keep one-use behavior near its caller

Bad: one route calls `HandlerFactory -> ServiceRegistry -> QueryProvider` to
perform one database read. Each layer forwards the same argument and offers no
different policy or reuse.

Better: call a small query function from the route or existing service. Add a
boundary when there are independent implementations, transactions or policy
that the boundary actually owns.

## A test should challenge behavior

Bad: `assert normalize(" A ") == normalize(" A ")` or a mock that returns the
expected output without exercising the branch under change.

Better: assert `normalize(" A ") == "a"` and include a boundary input that
would expose the regression, while using real parsing and only mocking the
external service.

## Avoid speculative speed and bulk edits

Bad: cache mutable account state indefinitely because a function is called
twice, then reformat the entire directory while touching one validation rule.

Better: leave the read direct until measured cost and invalidation rules are
known; keep the diff on the validation rule and its focused test.
