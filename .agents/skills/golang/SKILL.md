---
name: golang
description: Implement or review Go HTTP services and tests in registered projects. Use for affected .go files, following each module's go.mod, standard-library patterns and local verify target.
---

# Go best practices for HTTP services

## Contents

- [Module and design boundaries](#module-and-design-boundaries)
- [Style and types](#style-and-types)
- [Functions, methods and interfaces](#functions-methods-and-interfaces)
- [HTTP handlers](#http-handlers)
- [Errors and cleanup](#errors-and-cleanup)
- [Context and concurrency](#context-and-concurrency)
- [Testing](#testing)
- [Performance](#performance)
- [Security](#security)
- [Anti-slop review](#anti-slop-review)
- [Tooling and verification](#tooling-and-verification)

Read the target `AGENTS.md`, affected `go.mod`, `Makefile` and nearby
handlers. The registered services use Go 1.21 modules with standard-library
HTTP/templates. Follow the module version even if the host compiler is newer.
Read [HTTP boundary examples](references/http-boundaries.md) for handlers and
the [Go review comments](https://go.dev/wiki/CodeReviewComments) for naming.

## Module and design boundaries

- First identify the affected module. `droppert-platform` has four Go 1.21
  modules rather than one root module; a change in one service should not
  silently edit another. Follow its `go.mod`, package layout and working
  directory contract. The [`go.mod` reference](https://go.dev/doc/modules/gomod-ref)
  explains language and module-version behavior.
- Keep packages focused on behavior they own. A package with one forwarding
  function adds navigation cost. Put shared logic in a new package when two
  callers need the same contract or the boundary isolates a distinct concern.
- Prefer simple composition. An interface should express what the consumer
  needs; inventing abstract services for every concrete implementation makes
  review and error tracing harder.

## Style and types

- Run `gofmt` through the repository's trusted verification workflow; use
  short, lowercase package names, clear exported names and Go initialisms
  (`ID`, `URL`, `HTTP`). Package comments and exported doc comments should
  explain contracts rather than repeat the identifier.
- Use zero values deliberately. A nil map cannot be assigned into; an empty
  slice and nil slice may serialize differently, so follow the API contract.
  A struct is preferable when fields have distinct meanings.
- Keep variable scope tight and names proportional to scope. Short `i` or
  `r` is fine in a small loop or handler; a long-lived value deserves a
  descriptive name. Avoid a utility package of unrelated helpers.

```go
type PageData struct {
    Title string
    Items []string
}
```

## Functions, methods and interfaces

- Return concrete results and `error`; do not bury expected failures in a
  zero value. Make a method only when it uses receiver state or belongs to
  the type's behavior. A free function is often enough.
- Define a small interface at the consumer only for a needed alternate
  implementation or test seam. Return concrete types from constructors when
  callers can use them directly.
- Pass parameters explicitly. Avoid a boolean flag with unclear meaning at
  call sites; a named option or separate operation can state intent better.

```go
type PageReader interface {
    ReadPage(ctx context.Context, slug string) (PageData, error)
}
```

This interface is useful when a handler has a real reader dependency; it is
not a requirement to wrap every package function.

## HTTP handlers

- Go 1.21 `ServeMux` patterns do not have Go 1.22's method-aware behavior.
  When adding a handler to these modules, check path and method explicitly
  inside the existing routing style unless the module version changes.
- Validate request method, path segment, content type and bounded body
  before side effects. Use a suitable 4xx response for invalid client input
  and a generic 5xx response for internal failure. Do not leak stack details.
- Set status and headers before writing the body. Buffer template output
  when a template error must be detected before sending HTTP 200. Use
  `html/template` for HTML and preserve contextual escaping.

```go
func page(w http.ResponseWriter, r *http.Request) {
    if r.URL.Path != "/page" {
        http.NotFound(w, r)
        return
    }
    if r.Method != http.MethodGet {
        w.Header().Set("Allow", http.MethodGet)
        http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
        return
    }
    w.Header().Set("Content-Type", "text/plain; charset=utf-8")
    _, _ = io.WriteString(w, "ready")
}
```

In real handlers, consider returned write errors if a later action or log
needs to distinguish a disconnect. Preserve each app's template/static root.

## Errors and cleanup

- Wrap failures with operation context: `fmt.Errorf("load page %q: %w",
  slug, err)`. Use `errors.Is` or `errors.As` when callers inspect causes.
  Never compare arbitrary error strings.
- Handle an error at the layer that can decide the outcome. Avoid logging and
  returning the same failure at every layer; log once at the owning boundary.
- `defer` the closure of files, response bodies and resources the function
  acquires. Check close errors when they can affect a write's correctness.
  Do not report a partial template as success; the
  [HTTP examples](references/http-boundaries.md) show buffering.

```go
body := http.MaxBytesReader(w, r.Body, 1<<20)
defer body.Close()
decoder := json.NewDecoder(body)
if err := decoder.Decode(&request); err != nil {
    http.Error(w, "invalid request", http.StatusBadRequest)
    return
}
```

For a JSON API, also reject trailing values and enforce the endpoint's
expected shape; a single successful `Decode` does not prove EOF.

## Context and concurrency

- Pass `r.Context()` into work that supports cancellation. For a locally
  bounded operation, derive a deadline and `defer cancel()`. A request
  cancellation is a failed/incomplete operation, not an empty success.
- A goroutine needs a clear owner, stop condition and error path. Do not
  start background work from a handler without a durable ownership contract.
  Protect shared mutable state with synchronization, or avoid sharing it.
- Channels and mutexes solve different problems. Prefer a direct call until
  concurrency gives a measured benefit. The
  [Go cancellation guide](https://go.dev/doc/database/cancel-operations)
  shows how context propagates to database work.

```go
ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
defer cancel()
result, err := reader.ReadPage(ctx, slug)
if err != nil {
    // Map expected errors; report an internal failure otherwise.
}
```

## Testing

- Use `httptest.NewRecorder` and `httptest.NewRequest` for changed handler
  behavior; assert status, headers and meaningful body content. Cover a
  malformed request and an internal failure when those paths can regress.
- Use table tests when cases share one contract, not when each case needs
  extensive setup. Test the concrete behavior rather than a mock that
  repeats the implementation. For cancellation, arrange a controlled
  blocked dependency and assert the handler returns.
- `go test -race` can find races in exercised paths, but a passing run does
  not prove race freedom. Run it only if supplied as an authorized validation
  command. See the [race detector guide](https://go.dev/doc/articles/race_detector).

```go
rec := httptest.NewRecorder()
req := httptest.NewRequest(http.MethodPost, "/page", nil)
page(rec, req)
if rec.Code != http.StatusMethodNotAllowed {
    t.Fatalf("status = %d, want 405", rec.Code)
}
```

## Performance

- Profile actual latency or allocation cost before rewriting code. Reuse a
  shared `http.Client` with explicit timeout policy when outbound requests
  need it; close response bodies so connections can be reused.
- Bound request bodies, result sizes and parallelism. A cache needs an
  ownership, capacity and invalidation rule; a global map without
  synchronization and lifecycle is not a performance design.
- Avoid early micro-optimization at the cost of clear error handling.

## Security

- Treat URL paths, form values and request bodies as untrusted. Validate
  allowed values before filesystem access or subprocess invocation. Use
  `html/template` for HTML; `text/template` does not provide HTML escaping.
- Keep secrets out of responses and logs. Use parameterized database
  operations. Set request and outbound deadlines appropriate to the service;
  preserve the repository's security contexts and deployment contract.
- A route hidden from navigation still needs its own authorization check
  when it changes protected state.

## Anti-slop review

- Reject a framework or interface stack around a one-operation handler,
  unchecked parse or template errors, and an HTTP 200 after partial failure.
- Reject a goroutine started from a request without an owner/cancel path,
  an unbounded shared map cache, or a retry that repeats an ambiguous write.
- Reject Go 1.22 method patterns in a `go 1.21` module and loop goroutines
  that capture an iteration variable incorrectly under Go 1.21 semantics.
  [Go 1.22 release notes](https://go.dev/doc/go1.22) explain the change.

## Tooling and verification

Use the trusted `make verify` target only when supplied for this task. It
formats, tests, vets and builds according to the registered repository; do
not introduce a new framework or a Go 1.22 API merely because the host
compiler is newer. Report which module and checks were actually exercised.
