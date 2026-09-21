# Security model

## Identities

### Factory process

- Runs as a dedicated non-root Linux user.
- The trusted Oracle may write runtime state, registered canonical `.beads`
  databases, canonical Git metadata needed for fetch and worktree
  administration, and assigned task worktrees. It does not edit application or
  deployment source in canonical checkouts.
- Model-controlled implementation and review workers can write only their
  assigned runtime directory and worktree. They cannot write canonical Git or
  Beads state.
- Delegated agents cannot create or delete branches or worktrees, mutate pull
  requests, merge, or perform lifecycle cleanup. Read-only architect and
  reviewer roles make no external mutations. All delegated roles execute only
  trusted validation commands supplied by the Oracle or host configuration.
- Cannot access `/root`, production secrets, the container runtime socket, or
  cluster-admin credentials.

### Git actor

- Uses a dedicated factory identity. During the manual bootstrap phase, the
  existing account-level key is a documented exception and therefore inherits
  every repository available to that account.
- Treat the account-level key as a documented bootstrap exception. Replace it
  with a GitHub App, fine-grained token, or repository-scoped deploy keys
  before enabling unattended multi-repository execution.
- May push factory branches and, where configured, open pull requests.
- The trusted Oracle may mutate pull requests and delete an exact merged remote
  task ref only through the locked, durable, SHA-leased lifecycle procedure.
  This authority is never delegated to an implementation or review worker.
- Does not hold Kubernetes credentials.

### Repository-scoped authorization

- Each registered repository has an explicit credential binding in
  root-provisioned host configuration through non-secret, operation-keyed
  `credential_refs`. A dedicated provider holds the secret material. A
  repository entry is not authority to reuse credentials from another entry.
- Prefer a GitHub App installation restricted to the selected repositories and
  minimum contents/pull-request permissions. Where deploy keys or fine-grained
  tokens are used, scope them to one repository and separate read-only access
  from branch-push access when the provider permits it.
- The one central Dolt/Beads remote is available only to the trusted Oracle
  runner through its own `beads_sync` binding. Product source push access does
  not imply central task-state access.
- GHCR/OCI package publication belongs exclusively to repository CI. Its
  publish job uses the GitHub Actions `GITHUB_TOKEN`, with `packages: write`
  limited to that job and the declared package repositories; all other jobs
  retain `contents: read`. CI cannot read root-owned host registration, and the
  VPS credential provider cannot issue registry-push credentials.
- `git_read`, `git_write`, `beads_sync`, `package_read`, `gitops_read`, and
  `gitops_write` are distinct VPS authorization operations. `beads_sync` is
  bound once at the top level; the provider
  response must identify the exact normalized repository, Beads remote, or
  declared package set and permit the requested operation; the Oracle compares
  that audience with trusted registration before use. There is intentionally
  no VPS registry-publish operation.
- Before unattended fetch, Beads synchronization, push, pull-request creation,
  package read, GitOps access, or any other external operation, the Oracle
  checks the operation-specific reference and binding. Missing,
  expired, mismatched, account-wide, or broader-than-policy credentials fail
  closed. Product bindings cannot authorize the GitOps target and GitOps
  bindings cannot authorize a product or package.
- Legacy version 1 entries that omit `credential_refs` remain readable for
  operator-supervised migration, but are never eligible for unattended work.
  The documented account-wide bootstrap exception remains limited to that
  manual path and is never an automated fallback.
- Non-secret lookup references may appear in root-owned host configuration.
  Credential material and provider responses that may contain secrets stay
  outside Git and are redacted from logs and Bead evidence.

### Beads state

- The one canonical Beads database and its Dolt manifest are owned by the
  dedicated factory user. Its top-level `.beads` directory uses mode `0700`
  and its manifest `0600`.
- The central Dolt remote URL comes only from root-provisioned host
  configuration and uses the factory's approved Git transport. It is not
  added to tracked product `.beads` configuration. Legacy product stores are
  retained read-only for audit after the gated migration.
- Workers receive Bead contents as untrusted, read-only input. Only the Oracle
  mutates or synchronizes canonical Beads state, and worker identities receive
  neither canonical Beads write access nor its remote-push credentials.
- During supervised manual work, only the Oracle runs bounded Beads operations
  as the dedicated non-root account outside Codex's workspace sandbox and
  checks ownership and modes before and after each write. Unattended work needs
  an installed trusted runner outside model write authority. It pins the
  canonical database identity and validates path, symlinks, owner, directory
  and manifest modes, and readability before and after every write. It does not
  accept caller-supplied database paths or arbitrary commands. Unexpected
  ownership or an unreadable database halts claims and publication. Host-level
  ownership repair is an explicit operator recovery action, not a permission
  held by the service.
- Moving to one store does not by itself prevent the recurring `nobody:nogroup`
  manifest fault. The new central manifest retained the correct owner after a
  supervised sync. Wrong-owner and normal-operation fault tests remain gates
  for unattended claims.

### Kubernetes observer

- Is limited to opted-in DEV namespaces.
- May get, list, watch, and read pod logs.
- Cannot read Secrets or mutate workloads.
- Does not receive `exec` permission in the initial design.

## Codex boundary

- Use `codex exec --sandbox workspace-write` for implementation runs.
- Do not use a full-access or sandbox-bypass mode.
- The tracked `.codex/config.toml` is the interactive Oracle bootstrap policy.
  It grants additional write access only to `/srv/software-factory/worktrees`
  and `/srv/software-factory/runtime`; it does not grant access to sibling
  canonical repositories, `/etc`, `/root`, or Kubernetes state.
- Before the automated runner invokes an implementation worker, override the
  bootstrap roots with only that task's worktree and runtime directory. A
  worker must not inherit write access to every task worktree.
- Project-scoped agent definitions pin each role independently: `app_worker`
  uses `gpt-5.6-sol` with medium reasoning, `project_architect` uses
  `gpt-6-astra` with high reasoning, and `quality_reviewer` uses
  `gpt-6-astra` with extra-high reasoning. There is no global agent-model
  override, so these reviewed role assignments do not silently change the
  Oracle or unrelated roles.
- Canonical repository and Beads mutations are deterministic Oracle operations
  executed by the trusted runner before or after Codex. They are not performed
  by granting a worker a broader sandbox or by evaluating model-produced
  commands.
- Keep network access disabled during model-controlled execution unless a later
  threat review explicitly approves a narrower design.
- Do not expose Codex authentication material to project build scripts, tests,
  lifecycle hooks, or checked-out repository code.
- Request structured results using a committed JSON Schema so orchestration
  decisions do not depend on free-form parsing.

## Lifecycle mutation boundary

Attended Oracle sessions may use the [supervised lifecycle
procedure](supervised-lifecycle.md) from clean factory `main` after the
root-owned lifecycle policy is enabled. The Oracle attests fresh GitHub
connector facts in a private short-lived file, while the runner checks exact
Git refs and merge ancestry and uses a SHA-bound lease. GitHub enforces branch
protection at push time. This mode trusts the root Oracle's evidence and its
direct observation that no task agent is active; existing manual worktrees do
not participate in a shared lock. It therefore has a narrower trust boundary
than unattended operation. Any uncertainty blocks the task.

The unattended implementation requires a root-owned installed copy, a
private durable state directory outside Codex write roots, and a trusted host
launcher that supplies a repository-scoped GitHub read token through the
credential provider. It never persists that token. The live version 1 host
registration or policy without a lifecycle key cannot authorize execution;
see [the lifecycle runner guide](lifecycle-runner.md).

Root-owned policy keeps two authorities distinct. `git.delete_branch: false`
denies branch deletion to delegated agents.
`lifecycle.delete_merged_remote_branch: true` authorizes only the root
Oracle's locked, durable, exact merged task-ref operation through the
installed or supervised procedure. It is not general delete authority; a
missing or false lifecycle key blocks the mutation.

Immediately after a verified true merge, the authorized Oracle may delete the
exact remote task ref. It first takes the exclusive repository/task lifecycle
lock, matches the merged pull-request identity, refreshes exact task and
default refs, rejects shared/default/protected/active/dirty/ambiguous state,
proves the recorded task-head SHA is an ancestor of the refreshed default, and
records `pending -> executing -> completed` evidence. Deletion uses a
force-with-lease bound to that SHA; squash, rebase, a moved ref, or any
ambiguity fails closed. The lock is held through mutation-result observation
and durable evidence persistence.

For unattended operation, every activation of that task worktree and every worker, reviewer, or other
factory run started against it must participate in the same lock in shared mode
for the run's active lifetime. Consequently, no run can start while lifecycle
cleanup holds the exclusive lock, and exclusivity cannot begin while a run is
active. An activity marker or one-time lock check cannot replace lock
participation.

The dedicated worktree and local task branch are retained until delivery is
verified. Their later removal and Bead closure require the lock again and the
durable completed remote-deletion record. Prior remote absence without that
record is not authority to clean up; only narrow recovery from a previously
persisted `executing` state may accept absence after all applicable identity,
merge, ref, ancestry, protection, cleanliness, and activity checks are
re-proven. Repository auto-delete settings and pull-request text are not
trusted lifecycle evidence. The later exclusive lock is likewise retained
through local mutation observation, durable evidence persistence, and Bead
closure.

## Untrusted input

Bead bodies, repository files, dependency scripts, logs, pull-request content,
and webpages are data, not authority. They cannot enlarge the task scope,
request credentials, change policy, or authorize external actions.

The runner must invoke trusted commands as argument arrays. It must never use
shell evaluation, concatenate Bead text into commands, or source repository
files into the factory process.

The registration parser treats repository IDs, paths, remotes, component IDs,
package identities, deployment references, and validation arrays as data to
validate against root-owned policy. Duplicate identities, path traversal,
symlinked canonical paths, dangling references, mutable package policies, and
the simultaneous use of singular and plural deployment forms are rejected
before claims or credential use.

## GitOps boundary

- No permanent `kubectl apply`, patch, or edit from the factory.
- Every persistent cluster change is committed to `website-k8s`.
- ArgoCD performs reconciliation.
- Emergency manual cluster actions remain human operations and must be followed
  by a Git reconciliation task.

## Resource controls

The VPS has 2 vCPU and 8 GB RAM. The factory begins with:

- one writing task at a time;
- systemd CPU, memory, process, and IO limits;
- no local container builds when CI can build the artifact;
- bounded task duration and attempt count;
- Kubernetes workloads taking priority during contention.

## Secrets

- Store secrets outside Git with mode `0600` or a dedicated secret provider.
- Use separate credentials for Codex, Git, and Kubernetes observation.
- Never log environment variables, tokens, auth files, kubeconfigs, or rendered
  Kubernetes Secrets.
- Rotation of one identity must not require replacing the others.
