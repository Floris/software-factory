---
name: python
description: Implement or review Python applications, libraries, scripts, tests and tooling with maintainable design, typing and error handling. Use for affected .py files, honoring the target runtime and local conventions.
---

# Python best practices

## Contents

- [Design principles](#design-principles)
- [Pythonic idioms](#pythonic-idioms)
- [Style and documentation](#style-and-documentation)
- [Typing](#typing)
- [Functions](#functions)
- [Classes and data models](#classes-and-data-models)
- [Errors and resources](#errors-and-resources)
- [Data structures and imports](#data-structures-and-imports)
- [Testing](#testing)
- [Performance](#performance)
- [Security](#security)
- [Anti-slop review](#anti-slop-review)
- [Tooling and verification](#tooling-and-verification)

Read the target `AGENTS.md`, Python version, imports, tests and tooling.
Factory scripts currently favor the standard library (`argparse`, `pathlib`,
`dataclasses` and `unittest`); other projects may differ. Use the project
entrypoint and trusted validation. Read [CLI and failure examples](references/cli-boundaries.md)
when changing subprocess or recovery behavior.

## Design principles

- Give domain knowledge one authoritative representation (DRY), but extract
  only a rule that really repeats. Similar-looking operations can have
  different contracts. Favor a short direct function over a speculative
  framework (KISS, YAGNI).
- Separate input parsing, decisions and external effects when that clarifies
  failure and testing. SOLID can expose mixed responsibilities, but it does
  not require inheritance, abstract base classes or dependency injection
  for each class. Prefer composition for independent behavior.

| SOLID lens | Practical question |
| --- | --- |
| Single responsibility | Does this unit have one coherent reason to change? |
| Open/closed | Can a genuine new variant be added without breaking callers? |
| Liskov substitution | Does a subtype honor the base contract? |
| Interface segregation | Does a caller need every method it receives? |
| Dependency inversion | Is an abstraction useful at this actual boundary? |

Use these lenses to simplify a concrete design; do not add hierarchy to
demonstrate all five.

```python
def normalize_label(raw: str) -> str:
    return raw.strip().casefold()


def labels_match(left: str, right: str) -> bool:
    return normalize_label(left) == normalize_label(right)
```

The shared rule has a name because callers must agree on normalization; it
needs no registry or service object.

## Pythonic idioms

- Iterate over values; use `enumerate` for positions, `zip` for pairs and
  `mapping.items()` for keys with values. Use comprehensions when the
  transformation fits one readable expression, otherwise use a loop.
- Use truthiness for collections; use `is None` when absence differs from
  zero, `False` or an empty value. `value or default` is wrong when the
  falsey value itself is valid.
- EAFP (try and catch a documented failure) suits lookup and resource races;
  LBYL suits simple validation. Neither is universally faster or safer.

```python
try:
    timeout = config["timeout"]
except KeyError:
    timeout = DEFAULT_TIMEOUT

for position, name in enumerate(names, start=1):
    print(position, name)
```

## Style and documentation

- Follow [PEP 8](https://peps.python.org/pep-0008/) and the repository's
  configured formatter: four-space indentation, `snake_case` functions,
  `PascalCase` classes, `UPPER_CASE` constants and grouped imports. Local
  line-length settings take precedence over a generic 79/88-column rule.
- Name values by meaning, not type. Avoid shadowing builtins such as `list`
  and `id`. Public or surprising functions need a docstring explaining
  contract, side effects and exceptions; avoid narrating the signature.
  [PEP 257](https://peps.python.org/pep-0257/) describes conventions.

```python
def parse_port(raw: str) -> int:
    """Return a TCP port, raising ValueError outside the valid range."""
    port = int(raw)
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    return port
```

## Typing

- Annotate public boundaries and non-obvious data shapes. Annotations alone
  do not validate JSON, CLI values or environment variables at runtime.
- Use `list[str]`, `dict[str, int]` and `str | None` only when the target
  interpreter supports them. Use `Protocol` or `TypedDict` for a real
  structural contract; avoid `Any` and casts that merely silence uncertainty.
- Narrow optional values before use. Validate external data before making a
  typed object. Run a checker only when it belongs to the project or task.

```python
def first_match(names: list[str], prefix: str) -> str | None:
    return next((name for name in names if name.startswith(prefix)), None)
```

The [Python 3.12 typing reference](https://docs.python.org/3.12/library/typing.html)
is versioned; older target interpreters may require older syntax.

For a dictionary returned by untrusted JSON, check values before creating a
typed record. `TypedDict` describes the shape to a checker, not to runtime:

```python
from typing import TypedDict


class ProjectInput(TypedDict):
    title: str


def parse_project(value: object) -> ProjectInput:
    if not isinstance(value, dict):
        raise ValueError("project title is required")
    title = value.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("project title is required")
    return {"title": title.strip()}
```

## Functions

- A function should perform one coherent operation and return a meaningful
  result. Use keyword-only parameters when same-type arguments or flags are
  easy to mix up. Avoid chains that only forward `*args` and `**kwargs`.
- Mutable defaults persist across calls. Allocate inside a function and
  avoid mutating a caller's collection unless the contract promises it.

```python
def append_tag(tag: str, tags: list[str] | None = None) -> list[str]:
    result = [] if tags is None else list(tags)
    result.append(tag)
    return result
```

## Classes and data models

- A `dataclass` suits a cohesive record when it removes real constructor
  boilerplate. Use `field(default_factory=list)` for mutable fields.
  `frozen=True` prevents field reassignment but does not deep-freeze nested
  values.
- A property suits a cheap derived attribute; do not hide I/O in a property.
  Use inheritance when substitutability is a real contract, otherwise keep
  objects composed of focused collaborators.

```python
from dataclasses import dataclass, field


@dataclass
class Report:
    title: str
    notes: list[str] = field(default_factory=list)
```

## Errors and resources

- Catch the narrow exception you can resolve. Translate it at the boundary
  that owns the user-facing outcome; propagate unexpected failures. Logging
  and re-raising at every layer duplicates noise.
- Preserve causes with `raise DomainError("context") from exc` when useful.
  An I/O failure must not become an empty result or successful exit.
- Use `with` or `try/finally` for files, locks, sockets and temporary state.
  Bound external I/O that could stall the workflow.

```python
from pathlib import Path


def read_config(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"configuration missing: {path.name}") from exc
```

Permission and decoding errors remain visible to the caller. For process
and recovery examples, use [CLI boundaries](references/cli-boundaries.md).

## Data structures and imports

- Choose `set` for membership, `dict` for keyed lookup, `deque` for queues,
  `tuple` for fixed positions and a generator when streaming a large input
  avoids retaining it. Favor the plain structure when data is small.
- Avoid wildcard imports and `sys.path` hacks. Follow the repository's
  import order and intended module entrypoint. Guard executable code with
  `if __name__ == "__main__":` where appropriate.

```python
def nonempty_lines(path: Path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            stripped = line.strip()
            if stripped:
                yield stripped
```

This generator holds its file while iterated; consume or close it promptly.

## Testing

- Test observable behavior and meaningful failure paths with the project's
  `unittest` or `pytest` setup. Cases should expose a plausible regression.
- Use temporary directories for real filesystem behavior, fakes for remote
  services and controlled clocks for time-sensitive logic. Mocking every
  file read can hide the actual path and encoding behavior under test.
- Test cleanup and retry against before/after state. A failed operation
  must not appear successful.

```python
import tempfile
import unittest
from pathlib import Path


class ConfigTests(unittest.TestCase):
    def test_read_config_preserves_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.txt"
            path.write_text("enabled\n", encoding="utf-8")
            self.assertEqual(read_config(path), "enabled\n")

    def test_missing_config_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.txt"
            with self.assertRaisesRegex(ValueError, "configuration missing"):
                read_config(path)
```

## Performance

- Profile a real slow path before optimizing. Builtins, generators and set
  membership often suffice. Consider I/O and memory before micro-optimizing
  Python operations.
- Cache only repeatable, side-effect-free results with a defined size and
  invalidation rule. `functools.lru_cache` retains arguments and results,
  has no TTL, and does not suit async functions, mutable results or live
  authorization data. See the [`functools` reference](https://docs.python.org/3.12/library/functools.html).

## Security

- Treat CLI values, files, logs and API inputs as untrusted; validate their
  allowed form and bounds at the boundary. A type hint is not validation.
- Invoke subprocesses with a trusted executable and argument array, without
  interpolating untrusted text through a shell. Check exit status when
  success matters and prevent operands from becoming unintended options.
- Keep secrets out of source and logs. Parameterize SQL; never `eval` or
  unpickle untrusted data. Use `secrets` for security tokens, not `random`.

```python
import subprocess

subprocess.run(
    ["git", "show", "--no-patch", "--end-of-options", trusted_ref],
    check=True, text=True, capture_output=True,
)
```

`trusted_ref` must come from authorized state. Consult the
[`subprocess` reference](https://docs.python.org/3.12/library/subprocess.html)
for platform-specific argument and timeout behavior.

## Anti-slop review

- Reject a class hierarchy for two functions, a `Protocol` with one caller
  and no real alternate behavior, or a helper that only forwards arguments.
- Reject mutable defaults, `except Exception: return []` after a failed
  read, and logging the same exception at every layer.
- Reject `cast(ProjectInput, json.loads(raw))` as input validation, an
  unbounded cache over live data, and tests that mock away the branch
  under change. Keep the typed boundary and real failure visible.

## Tooling and verification

Run only trusted validation commands supplied for the assigned task. Existing
`unittest`, formatting and packaging conventions govern. `ruff`, `mypy`,
`pyright`, `pytest`, `uv` and similar tools are options only when the project
or a scoped task selects them. Report the checks run and any behavior that
still requires an approved environment.
