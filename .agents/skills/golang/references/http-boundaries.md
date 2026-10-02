# HTTP boundary examples

Bad: a handler ignores `ParseForm` and `ExecuteTemplate` errors, then returns
HTTP 200. Clients receive an incomplete page that appears successful.

Better: reject malformed form input with a client status before mutation.
Render to a buffer when a template error must be caught before sending the
success status; log the internal error once at the HTTP boundary and send a
generic server response. Test malformed input and template failure behavior.

```go
var page bytes.Buffer
if err := tmpl.Execute(&page, data); err != nil {
    log.Printf("render page: %v", err)
    http.Error(w, "Page unavailable", http.StatusInternalServerError)
    return
}
w.Header().Set("Content-Type", "text/html; charset=utf-8")
if _, err := w.Write(page.Bytes()); err != nil {
    log.Printf("write page: %v", err)
}
```

Bad: a new `Storage` interface has one implementation and one caller, with no
test seam or alternate behavior that needs it.

Better: call the concrete function. Introduce the smallest interface at the
consumer only if a genuine second implementation or focused test benefits.
