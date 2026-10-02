---
name: golang
description: Implement or review Go HTTP services and tests in registered projects. Use for affected .go files, following each module's go.mod, standard-library patterns and local verify target.
---

# Go service changes

Read the target `AGENTS.md`, the specific module's `go.mod`, its `Makefile` and
nearby handlers. Several registered services use Go 1.21 standard-library
HTTP and templates, including separate modules in one repository. Stay within
the affected module's conventions; do not assume a root module or framework.
The module `go 1.21` declarations matter even when the host Go binary is newer:
do not introduce Go 1.22 method-pattern routing without an explicit version
change.

- Keep handlers small enough to show input parsing, domain work and response
  selection. Place shared logic in a package when it serves multiple callers
  or owns a clear domain rule, not just to hide a short handler.
- Validate request method, path and input before side effects. Set an
  appropriate status for expected client errors and report server failures
  without exposing internal details to the client. Bound request bodies when
  reading them, and honor `r.Context()` in downstream work that supports it.
- Return errors with useful operation context; use `%w` when callers need to
  inspect the cause with `errors.Is` or `errors.As`. Do not log and return the
  same error at every layer. Close files and response bodies that your code
  opens.
- Use `html/template` for HTML output and preserve its contextual escaping.
  Keep static-file roots and template lookup aligned with the application's
  working-directory contract.
- Let `gofmt` handle formatting. Use short, lowercase package names, concise
  receivers and consistent initialisms such as `ID`, `URL` and `HTTP`. Keep a
  small interface at its consumer when a real test seam or alternate behavior
  needs it; avoid forwarding layers without a clear contract.
- Add tests for changed handler behavior and failure status when they would
  catch a regression. Use the registered `make verify` only when supplied as a
  trusted validation command for this task.

Read [HTTP boundary examples](references/http-boundaries.md) when changing a
handler or its error handling. The [Go review comments](https://go.dev/wiki/CodeReviewComments)
and [`go.mod` reference](https://go.dev/doc/modules/gomod-ref) clarify style
and language-version constraints.
