# Central Beads migration

## State on 2026-09-21

The manual task-store cutover used the three Dolt remotes as its source. The
operator accepted possible loss of changes that existed only in the unreadable
local databases. The former `software-factory` and `expense-tracker` manifests
were `nobody:nogroup`, mode `0600`; a narrow `chown` attempt on the latter
returned `Operation not permitted`. The factory did not use root or weaken
permissions.

The two affected paths are:

- `/srv/software-factory/repos/software-factory/.beads/embeddeddolt/sf/.dolt/noms/manifest`
- `/srv/software-factory/repos/expense-tracker/.beads/embeddeddolt/et/.dolt/noms/manifest`

The original factory `.beads` directory was moved intact to a private recovery
directory. The Expense Tracker original remains untouched. Their inaccessible
local state was not compared with the remotes, so any unsynchronized changes
there are outside the new canonical store.

Read-only clones of the three configured Dolt remotes exported 10 `sf`, 6 `et`,
and 8 `wk` issues. All 24 IDs are unique. A candidate imported them with
`metadata.repository_id`; comparison showed unchanged non-routing issue fields
and seven retained dependency edges. The candidate replaced the factory's old
`.beads` directory, then `bd sync` pulled and pushed successfully to the
existing factory Dolt remote. A fresh independent clone of that remote
contained exactly the same 24 issue records and all 24 repository IDs. The
active factory `.beads` directory is `codex:codex` mode `0700`; its manifest is
`codex:codex` mode `0600` after synchronization.

This establishes one central store for supervised manual work. The live
`/etc/software-factory/repositories.yaml` still describes the legacy layout,
and no installed trusted host runner or fault-tested automation exists. Do not
enable unattended claims until those remaining gates pass.

## Import method and limits

The candidate began as a fresh clone of the factory Dolt remote, preserving its
remote history. The other two stores supplied issue JSONL, preserving their
issue IDs, fields, comments, timestamps, and dependencies. Their separate Dolt
histories remain in their old remotes. `bd export` omits non-issue tables and
memories by default; `bd export --all` can include sensitive memories. The
manual migration did not merge non-issue tables or memories.

`scripts/prepare_central_beads_import.py` validates private exports, duplicate
IDs, routing conflicts, and dependency edges before creating a private combined
JSONL file. It does not alter a database. Existing factory issues needed an
explicit metadata update in the candidate because Beads import retains local
fields when `updated_at` ties. That update changed their timestamps. The three
original remote histories remain available for audit. The accepted data-loss
decision applies only to possible unsynchronized local changes from this
cutover, not to future recovery.

## Remaining gates for unattended operation

1. Install a trusted host runner outside model write authority. It must run as
   the dedicated non-root factory user outside Codex's sandbox, accept only
   fixed operations and argument arrays, and pin the central database identity.
   Check canonical path, symlinks, owner, `0700` directory mode, `0600`
   manifest mode, and readability before and after every write. A failed
   postflight prevents publication.
2. Replace `/etc/software-factory/repositories.yaml` with a reviewed version 2
   central Beads registration and one central `beads_sync` binding. Reject mixed
   central and per-repository routing. Repository Git, package, and GitOps
   credential bindings remain separate. The current version 1 host file must
   not be used to select old task stores.
3. Fault-test a wrong-owner manifest, symlink, wrong database identity, and an
   attempted sandboxed write in disposable fixtures. Each must cause zero
   canonical mutation and no push. Verify normal sync, claim, heartbeat,
   update, and close retain the expected ownership and modes. Until then,
   unattended scheduling remains disabled.
4. Update product instructions that still direct agents to product-local
   Beads. Reconcile merged task `et-2vx` in the central store. Its remote task
   branch and worktree remain until the deterministic locked lifecycle procedure
   verifies and cleans those exact resources.

Rollback after a central write must preserve and replay that write; switching
to stale legacy stores is not a valid rollback.
