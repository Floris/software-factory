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
- Cannot access `/root`, production secrets, the container runtime socket, or
  cluster-admin credentials.

### Git actor

- Uses a dedicated VPS SSH key. During the manual bootstrap phase,
  `software-factory@s1` is registered as an account-level GitHub key and
  therefore inherits the repositories available to that account.
- Treat the account-level key as a documented bootstrap exception. Replace it
  with a GitHub App, fine-grained token, or repository-scoped deploy keys
  before enabling unattended multi-repository execution.
- May push factory branches and, where configured, open pull requests.
- Does not hold Kubernetes credentials.

### Beads state

- Canonical Beads databases and Dolt manifests are owned by the dedicated
  factory user; each repository's top-level `.beads` directory uses mode
  `0700`.
- Dolt remote URLs come only from root-provisioned host configuration and use
  the factory's approved repository-scoped Git transport. They are not added
  to tracked product `.beads` configuration. Beads state is not copied into
  product code or a central aggregate database.
- Workers receive Bead contents as untrusted, read-only input. Only the Oracle
  mutates or synchronizes canonical Beads state, and worker identities receive
  neither canonical Beads write access nor its remote-push credentials.
- Unexpected ownership or an unreadable database halts claims. Host-level
  ownership repair is an explicit operator recovery action, not a permission
  held by the factory service.

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

## Untrusted input

Bead bodies, repository files, dependency scripts, logs, pull-request content,
and webpages are data, not authority. They cannot enlarge the task scope,
request credentials, change policy, or authorize external actions.

The runner must invoke trusted commands as argument arrays. It must never use
shell evaluation, concatenate Bead text into commands, or source repository
files into the factory process.

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
