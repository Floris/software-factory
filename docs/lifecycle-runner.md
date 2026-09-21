# Merged task-branch lifecycle runner

`scripts/merged_branch_lifecycle.py` is a manually invoked, single-task runner.
It deletes only a merged `codex/<task-id>-*` remote task ref, then removes that
task's dedicated local worktree and branch after the Oracle verifies delivery.
The runner is source code in this repository; it is **not** trusted while it is
executed from a checkout that Codex can write.

## Installation gate

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

The runner requires root-owned registration version 2 and a selected root-owned
policy with both `git.delete_branch: false` and
`lifecycle.delete_merged_remote_branch: true`. The current live host files are
still version 1 and have no lifecycle key; the runner correctly blocks there.
Updating those files and wiring the credential provider are separate operator
steps. This script must not be installed or scheduled until the normal worker
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

The Oracle supplies identifiers and delivery evidence; it never supplies a
branch-deletion command or a path. The runner resolves paths and policy from
root-owned configuration, fetches the pull request and branch protection state
from GitHub, proves the exact task head is a parent of the merge commit and an
ancestor of the refreshed default ref, and rejects moved or shared refs. Before
remote mutation it persists `pending`, then `executing`; deletion uses a
SHA-bound atomic lease. It observes exact remote absence before persisting
`completed`. The worktree and local branch have separate durable steps. A
missing resource in `pending` blocks; an exact missing resource in `executing`
can be recovered after the remaining identity and ancestry checks pass.

The Oracle records the completed steps in the central Bead and closes the task
only after its requested delivery level has been verified. A DEV deployment
task is not locally cleaned merely because its GitOps PR merged.

## Dolt refs

`refs/dolt/data` in `software-factory` is the active central Beads remote and
must stay. Dolt also pushes a visible `__dolt_remote_info__` branch containing
`DOLT_REMOTE.md` after successful data pushes. That branch is informational,
but deleting it while the central Git-backed remote is active is temporary:
the next sync can recreate it. Dolt's `DOLT_REMOTE_INFO_BRANCH` override can be
set to an empty string in every trusted central sync process to suppress new
info-branch writes; verify that setting before removing the existing central
info branch. The old Expense Tracker and `website-k8s` info branches no longer
serve the central database. They are outside this task-ref runner's scope;
remove them only after the legacy stores and host registration have been
retired and a separate reviewed maintenance operation verifies their exact
refs. Keep the old data refs until the accepted audit-retention decision is
explicitly changed.
