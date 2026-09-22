# Merged task-branch lifecycle runner

`scripts/merged_branch_lifecycle.py` is a manually invoked, single-task runner.
It deletes only a merged `codex/<task-id>-*` remote task ref, then removes that
task's dedicated local worktree and branch after the Oracle verifies delivery.
The supervised Oracle mode runs the reviewed file from the clean canonical
factory `main` checkout and uses the GitHub connector. Its checks, evidence
format, and one-time host change are in [the supervised runbook](supervised-lifecycle.md).
The installed mode below remains available for unattended operation.

## Unattended installation gate

An operator must review and install the script at
`/usr/local/lib/software-factory/merged_branch_lifecycle.py`, owned by root and
not writable by the factory account. The operator provisions
`/var/lib/software-factory/lifecycle` as a private `0700` directory owned by
the dedicated non-root factory account. This state path must be outside every
Codex workspace-write root. The host launcher resolves `SF_GITHUB_TOKEN` from
the repository-scoped credential provider for GitHub pull-request and branch
read access; the token is never written to the lifecycle record or passed on a
command line. The launcher also uses the registered Git write identity for the
exact repository. Do not run the source-tree copy against live refs.

The installed runner requires root-owned registration version 2 and a selected root-owned
policy with both `git.delete_branch: false` and
`lifecycle.delete_merged_remote_branch: true`. Updating those files and wiring
the credential provider are separate operator steps. The installed runner must
not be scheduled until the normal worker
launcher participates in the same lock: each worker/reviewer/factory run
against a dedicated task worktree takes a shared `flock` on
`/var/lib/software-factory/lifecycle/<repository-id>/<task-id>.lock` for its
whole active lifetime. Lifecycle operations take the exclusive lock. Existing
out-of-band worktrees require a supervised inactivity check before migration
to the lock protocol.

The fixed argument vectors are:

```text
["python3", "/usr/local/lib/software-factory/merged_branch_lifecycle.py", "remote-delete", "<task-id>", "<repository-id>", "<merged-pr-number>"]
["python3", "/usr/local/lib/software-factory/merged_branch_lifecycle.py", "local-cleanup", "<task-id>", "<repository-id>", "<merged-pr-number>", "--delivery-evidence", "<Oracle verification summary>"]
```

The Oracle supplies identifiers and delivery evidence. The installed runner resolves paths and policy from
root-owned configuration, fetches the pull request and branch protection state
from GitHub, proves the exact task head is a parent of the merge commit and an
ancestor of the refreshed default ref, and rejects moved or shared refs. Before
remote mutation it persists `pending`, then `executing`; deletion uses a
SHA-bound atomic lease. It observes exact remote absence before persisting
`completed`. The worktree and local branch have separate durable steps. A
missing resource in `pending` blocks; an exact missing resource in `executing`
can be recovered after the remaining identity and ancestry checks pass.

The Oracle records the completed steps in the central Issue and closes the task
only after its requested delivery level has been verified. A DEV deployment
task is not locally cleaned merely because its GitOps PR merged.

## Historical Dolt refs

The previous `refs/dolt/data` and Dolt information refs were removed on
2026-09-22 under the operator-authorized, exact-ref maintenance recorded in
[issue #25](https://github.com/Floris/software-factory/issues/25). This
task-branch runner did not target them and must never do so. Future
non-task-ref cleanup requires a separate reviewed decision with exact-ref
evidence.
