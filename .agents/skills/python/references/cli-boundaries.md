# CLI and failure examples

Bad: `subprocess.run(f"git show {issue_title}", shell=True, check=False)`
mixes untrusted text into a command and ignores its result.

Better: resolve an authorized ref from trusted state, call
`subprocess.run(["git", "show", "--no-patch", "--end-of-options", ref],
check=True, text=True, capture_output=True)` and report a bounded, sanitized
failure. Verify the target command's argument contract before using this shape.

```python
# Bad: shared mutable default leaks entries between calls.
def add_entry(entry, entries=[]):
    entries.append(entry)
    return entries

# Better: allocate per call unless a list was supplied.
def add_entry(entry, entries=None):
    result = [] if entries is None else entries
    result.append(entry)
    return result
```

Bad: `except Exception: return True` tells a caller cleanup succeeded after
the filesystem operation failed.

Better: catch the expected absence as an idempotent result; let an unexpected
I/O error fail with the affected path and operation. Test both outcomes.
