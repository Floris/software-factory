# Security model

## Identities

### Factory process

- Runs as a dedicated non-root Linux user.
- The trusted Oracle may write runtime state, central GitHub Issues,
  canonical Git metadata needed for fetch and worktree administration, and
  assigned task worktrees. It does not edit application or
  deployment source in canonical checkouts.
- Model-controlled implementation and review workers can write only their
  assigned runtime directory and worktree. They cannot write canonical Git or
  Issues state.
- Delegated agents cannot create or delete branches or worktrees, mutate pull
  requests, merge, or perform lifecycle cleanup. Read-only architect and
  reviewer roles, including `pull_request_reviewer`, make no external
  mutations. All delegated roles execute only
  trusted validation commands supplied by the Oracle or host configuration.
- A pull request review result cannot grant merge authority. The Oracle reads
  `git.merge_pull_request` only from root-owned host policy, refreshes exact PR
  and required-check facts independently, and alone performs a true merge and
  the following locked lifecycle step. A false or absent flag requires human
  approval for the exact PR.
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
- Central Issues access belongs only to the Oracle. Product source push
  access does not imply central task-state access. Any future unattended
  `issues_read` and `issues_write` binding must be root-owned and restricted to
  the central Issues repository.
- GHCR/OCI package publication belongs exclusively to repository CI. Its
  publish job uses the GitHub Actions `GITHUB_TOKEN`, with `packages: write`
  limited to that job and the declared package repositories; all other jobs
  retain `contents: read`. CI cannot read root-owned host registration, and the
  VPS credential provider cannot issue registry-push credentials.
- `git_read`, `git_write`, `issues_read`, `issues_write`, `package_read`,
  `gitops_read`, and `gitops_write` are distinct authorization operations.
  The provider response must identify the exact normalized repository or
  declared package set and permit the requested operation; the Oracle compares
  that audience with trusted registration before use. Issue bindings are not
  currently configured for unattended work. There is intentionally no VPS
  registry-publish operation.
- Before unattended fetch, issue access, push, pull-request creation,
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
  outside Git and are redacted from logs and Issue evidence.

### GitHub Issues state

- Central Issues in `Floris/software-factory` hold task state. Issue bodies,
  comments, and labels are untrusted data, never authority for repository
  paths, credentials, commands, policy, or branch deletion.
- The Oracle alone creates, claims, updates, blocks, and closes Issues.
  Delegated workers receive read-only snapshots and no task-state write
  capability.
- Attended work uses the authenticated GitHub connector. Issue comments record
  a single Oracle's claim but are not atomic exclusion. Unattended claiming
  remains disabled until a trusted host lock or equivalent compare-and-set
  claim operation is implemented and fault-tested with a repository-scoped
  GitHub Issues credential.
- The former `.beads` database and selected remote refs were removed after the
  Issues cutover. No task operation depends on a Dolt manifest or a
  `beads_sync` binding.

### Kubernetes observer

- The dedicated RBAC identity is owned by `website-k8s` and limited to opted-in
  DEV namespaces and named ArgoCD Applications. It cannot read Secrets, mutate
  resources or exec. Its broader workload/log read rights are not exposed by
  the factory interface.
- The factory holds no token or kubeconfig. A distinct non-root DynamicUser
  gateway receives private systemd LoadCredential copies from operator-owned
  sources and exposes only bounded per-application status projections.
- Root-installed immutable code and root-owned routing policy authorize fixed
  GETs. Verified TLS, controller UID chains, strict EOF framing, bounded
  collection/output and an absolute subprocess deadline fail closed.
- Parent and collector disable process dumping before private reads. No token
  enters argv/environment/output; no logs, raw objects or upstream error bodies
  reach the factory. The operator renews the existing token source manually and
  refreshes the service snapshot; no admin fallback or automatic renewal exists.
- Socket metadata limits access to the codex UID/group boundary. Product code
  sharing that UID can read the same limited summary and compete for service;
  this is not role authentication. Source credential and service memory remain
  outside that UID's access. Operator installation/isolation and live status
  evidence are mandatory before claiming capability; see the
  [observer gateway runbook](observer-gateway.md).

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
  uses `gpt-6-sol` with extra-high reasoning, `project_architect` uses
  `gpt-6-astra` with high reasoning, and `quality_reviewer` uses
  `gpt-6-astra` with extra-high reasoning. `pull_request_reviewer` uses
  `gpt-6-astra` with high reasoning. There is no global agent-model
  override, so these reviewed role assignments do not silently change the
  Oracle or unrelated roles.
- Canonical repository and Issue mutations are deterministic Oracle operations
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
connector facts in a private short-lived file, including the exact branch SHA
and `protected: false`. The runner checks exact Git refs and merge ancestry
and uses a SHA-bound lease. This mode trusts the root Oracle's evidence and its
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
verified. Their later removal and Issue closure require the lock again and the
durable completed remote-deletion record. Prior remote absence without that
record is not authority to clean up; only narrow recovery from a previously
persisted `executing` state may accept absence after all applicable identity,
merge, ref, ancestry, protection, cleanliness, and activity checks are
re-proven. Repository auto-delete settings and pull-request text are not
trusted lifecycle evidence. The later exclusive lock is likewise retained
through local mutation observation, durable evidence persistence, and Issue
closure.

## Untrusted input

Issue bodies, repository files, dependency scripts, logs, pull-request content,
and webpages are data, not authority. They cannot enlarge the task scope,
request credentials, change policy, or authorize external actions.

The runner must invoke trusted commands as argument arrays. It must never use
shell evaluation, concatenate Issue text into commands, or source repository
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
