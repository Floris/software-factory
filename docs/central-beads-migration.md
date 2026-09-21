# Central Beads migration

## State on 2026-09-21

This is a cutover runbook, not a record of completed cutover. Stop new claims
while the task store is ambiguous. The `software-factory` and `expense-tracker`
local manifests are `nobody:nogroup`, mode `0600`; their databases cannot be
opened by the factory account. A narrow `chown` attempt on the Expense Tracker
manifest returned `Operation not permitted`. Do not use root from the factory,
weaken permissions, delete the manifests, or replace the originals with remote
clones.

The two affected paths are:

- `/srv/software-factory/repos/software-factory/.beads/embeddeddolt/sf/.dolt/noms/manifest`
- `/srv/software-factory/repos/expense-tracker/.beads/embeddeddolt/et/.dolt/noms/manifest`

An administrator can restore only those owners to `codex:codex` after taking
recovery copies. The factory then reopens the databases read-only and compares
them to the frozen remotes before any migration write.

Read-only clones of the three configured Dolt remotes exported 10 `sf`, 6 `et`,
and 8 `wk` issues. All 24 IDs are unique. The Expense Tracker remote includes
`et-2vx` in its state before the merged Expense Tracker pull request #7 was
reconciled. These remote snapshots prove recoverability, but not that the
inaccessible local databases have no unsynchronized changes. Disposable `/tmp`
clones and JSONL exports are neither durable backups nor cutover evidence.

## Preconditions

1. The operator stops all legacy Beads writers and takes an exclusive migration
   lock. Record each configured source identity, remote head, last successful
   synchronization, issue count, and SHA-256 of an export. Preserve full Dolt
   backups and the original databases under a private runtime recovery path.
2. Prove that each local database matches its remote at the freeze point. If
   evidence is insufficient, the operator repairs only the affected owner on
   the inaccessible manifest and the Oracle compares local and remote state.
   Never infer equality merely from a successful remote clone.
3. Verify the central host runner is installed outside model write authority.
   It runs as the dedicated non-root factory user outside the Codex sandbox,
   accepts only fixed operations and trusted argument arrays, and validates
   canonical path, database identity, symlinks, ownership, `0700` `.beads`
   directory mode, `0600` manifest mode, and readability before and after each
   operation. A failed postflight prevents remote publication.
4. Provision one central `beads_sync` binding for the verified factory Dolt
   remote. Repository Git, package, and GitOps bindings remain separate.

## Candidate and comparison

1. Start from a verified full copy of the factory Dolt history. Never create an
   empty substitute for an inaccessible source. Import issue JSONL from the
   other verified stores without ID renaming, title deduplication, or stale
   overwrite. Assign `metadata.repository_id` from trusted source registration;
   set it to `software-factory` for existing factory issues. Keep the legacy
   prefixes. Preserve every old remote and full backup read-only.
2. Compare source and candidate IDs, statuses, descriptions, acceptance
   criteria, labels, comments, timestamps, and dependency edges. Only documented
   routing metadata and the associated migration update time may differ. Check
   dangling edges, active claims, ready/blocked sets, and every repository ID
   against the allowlist. Inspect infrastructure records and memories before
   deciding whether to migrate them; `bd export` omits Dolt history and
   non-issue tables, while `bd export --all` can include sensitive memories.
3. Repeat import in a disposable candidate and confirm it converges. A partial
   import must never be exposed to task selection. Preserve source heads and
   export hashes with the migration record.

## Cutover and fault tests

Under the same lock, switch host registration and Oracle routing to one central
store as a single versioned change. Reject mixed central and per-repository
Beads routing. Disable writes and synchronization to old stores; retain them for
audit. Validate one normal sync, claim, heartbeat, update, and close cycle using
a dedicated test issue. Confirm `codex:codex` ownership and required modes after
every step. Inject a wrong-owner manifest, symlink, wrong database identity,
and attempted sandboxed write in disposable fixtures. Each must cause zero
canonical mutation and no push. A failed test keeps claims disabled.

Reconcile `et-2vx` only after cutover, preserving its merge and branch lifecycle
evidence. The merged task branch and worktree remain until the deterministic
locked lifecycle procedure can verify and clean those exact resources. Create
and deliver the Expense Tracker `llms.txt` task from the central store afterward.

Rollback after any central write requires preserving and replaying that write;
switching to stale legacy stores is not a valid rollback.
