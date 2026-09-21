# Supervised Oracle branch cleanup

This procedure lets the root Oracle clean one merged task branch with the
existing GitHub connector and Git over SSH. It runs only in an attended Codex
session, from the clean canonical factory `main` checkout. It needs no GitHub
token, root-installed script, daemon, or recurring operator command. The
root-owned host registration and policy remain the authority for repository
identity and permission.

## One-time operator change

After the reviewed change containing this procedure is merged, the operator
enables `lifecycle.delete_merged_remote_branch: true` in the selected policies
of `/etc/software-factory/policies.yaml`. Leave `git.delete_branch: false` and
`git.merge_pull_request: false` as they are. Make a backup first:

```sh
sudo cp -a /etc/software-factory/policies.yaml /etc/software-factory/policies.yaml.before-supervised-lifecycle
sudo sed -i 's/delete_merged_remote_branch: false/delete_merged_remote_branch: true/g' /etc/software-factory/policies.yaml
grep -n -E 'delete_branch:|delete_merged_remote_branch:' /etc/software-factory/policies.yaml
```

The Oracle creates private `0700` directories at
`/srv/software-factory/runtime/lifecycle` and
`/srv/software-factory/runtime/lifecycle-evidence` as its own user. No root
installation or credential change is needed. The runner refuses a false or
missing lifecycle flag and any non-root-owned or writable host policy.

## Evidence and execution

For **each** invocation the Oracle obtains fresh facts using the authenticated
GitHub connector: the exact merged PR, repository default branch, an
exact-head search for open PRs, and the exact branch API response through the
connector's `fetch` capability. The branch response must report the PR head
SHA and `protected: false`; an unavailable branch query blocks remote deletion.

The Oracle writes a private `0600` JSON file in the evidence directory. It is
an Oracle attestation of connector results, not a credential or a claim that
the local runner independently queried GitHub. Its exact schema is:

```json
{
  "version": 1,
  "repo": "owner/repository",
  "task_id": "sf-example",
  "repository_id": "registered-id",
  "pr_number": 12,
  "observed_at": "2026-09-21T12:00:00+00:00",
  "pull_request": {
    "number": 12,
    "state": "closed",
    "merged": true,
    "head": "codex/sf-example-task",
    "head_sha": "0000000000000000000000000000000000000000",
    "head_repo_full_name": "owner/repository",
    "base": "main",
    "merge_commit_sha": "1111111111111111111111111111111111111111"
  },
  "default_branch": "main",
  "open_pull_requests": [],
  "branch_info": {
    "name": "codex/sf-example-task",
    "sha": "0000000000000000000000000000000000000000",
    "protected": false
  }
}
```

For local cleanup after completed remote deletion, `branch_info` is `null`:
the remote branch must already be absent. The runner accepts only this schema,
the exact requested task/PR/repository,
and evidence no older than 15 minutes. It checks the registered Git remote,
clean canonical checkout and exact dedicated worktree, live default and task
refs, PR head and merge identity, true merge second parent, and ancestry. It
records the PR's historical base separately from the repository's current
default branch, so a PR merged into `master` before a rename can qualify only
when that exact merge is contained in the current `main` history. It
holds the task lock and writes durable `pending -> executing -> completed`
state. Remote deletion uses `--force-with-lease` bound to the recorded task
head and is considered complete only after exact remote absence is observed.
The local phase requires that prior completed state and delivery evidence.

Run from the canonical factory checkout, with one task at a time:

```text
["python3", "scripts/merged_branch_lifecycle.py", "remote-delete", "<task-id>", "<repository-id>", "<merged-pr-number>", "--supervised-evidence", "<private-json-path>"]
["python3", "scripts/merged_branch_lifecycle.py", "local-cleanup", "<task-id>", "<repository-id>", "<merged-pr-number>", "--delivery-evidence", "<verification summary>", "--supervised-evidence", "<fresh-private-json-path>"]
```

The Oracle does not start another writer or reviewer for that task during an
invocation and confirms no existing task agent is active. Current manually
created worktrees predate shared-lock participation, so the lock alone cannot
prove inactivity. Stop if activity is uncertain. Record the connector query,
exact SHA, runner result, and delivery observation in the central Bead. Keep
the Bead, worktree, and local branch until delivery is verified. Do not infer
successful cleanup from a missing ref without a completed durable record.

Only exact `codex/<task-id>-*` task branches are in scope. Dolt information
branches, `refs/dolt/data`, default branches, unmerged PRs, dirty or moved
worktrees, and branches with ambiguous ownership stay untouched.
