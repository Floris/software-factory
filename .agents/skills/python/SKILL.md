---
name: python
description: Implement or review Python scripts and tests in registered projects. Use for affected .py files, honoring the local Python version, standard-library conventions and validation entrypoints.
---

# Python in the registered repositories

Read the target `AGENTS.md`, imports, test layout and any project configuration.
The factory scripts currently favor standard-library `argparse`, `pathlib`,
`dataclasses` and `unittest`; do not assume a third-party formatter, test
runner or dependency manager exists. Match surrounding style and PEP 8 where
the repository has no more specific rule.

- Name functions and values in `snake_case`, classes in `PascalCase` and module
  constants in `UPPER_CASE`; annotate public boundaries where types clarify
  the contract. Avoid mutable default arguments.
- Keep CLI parsing at the entry point and pass explicit values to functions.
  Make ordinary results and error outcomes distinguishable to callers.
- Use `pathlib` for path operations where it fits the local code. Avoid
  embedding host-specific paths in reusable logic.
- When invoking another process, pass a trusted executable and argument array
  directly. Never interpolate issue text, logs or repository content into a
  shell command. Capture failure context without leaking credentials.
- Use a context manager or `try/finally` for files, locks and temporary
  resources that must be released. Bound external I/O with a deadline when a
  stalled operation would block the workflow.
- Keep exception handling specific. Propagate unexpected failures or wrap
  them with useful context; a broad `except` that reports success hides bugs.
- Add a focused `unittest` case for changed behavior or failure recovery when
  it could regress. Use temporary directories and fakes for external effects,
  then run only the trusted validation command supplied by the Oracle.

Do not add `sys.path` edits or a packaging/dependency setup to solve a local
import without checking the repository's intended entrypoint. See
[PEP 8](https://peps.python.org/pep-0008/) for baseline conventions and the
official [`subprocess` documentation](https://docs.python.org/3/library/subprocess.html)
for process argument behavior.

Read [CLI and failure examples](references/cli-boundaries.md) when touching
subprocess or recovery behavior.
