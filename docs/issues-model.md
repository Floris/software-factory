# Central GitHub Issues task model

`Floris/software-factory` Issues is the single task source for factory,
product, and deployment work. Use the free GitHub Issues features. The former
Beads store is historical data, never a claim or routing source.

## Task contract

Each implementation issue contains a target `repository_id` that matches one
root-owned host registration, an outcome, acceptance criteria, allowed write
scope, trusted validation profile or commands, risk and review requirements,
dependencies, and requested delivery level. The issue number is an identifier,
not authorization. The Oracle checks the registered repository and policy
before using a checkout, credential, command, or Git ref.

An epic is an issue with linked child issues. Cross-repository delivery uses
separate product and GitOps issues linked by full URLs. Use issue dependencies
for actual blockers. Keep the issue open until its requested delivery level is
verified, even when a code PR has merged. Link PRs with a plain reference;
avoid closing keywords until merge itself fulfills the issue.

## Claims and state

For attended work, the Oracle reads open issues and their current comments,
checks that no other active Oracle owns the task, then comments with the
claiming identity, time, repository ID, and intended worktree. It rechecks
before starting a writer. A claim comment is a coordination record, not an
atomic lock; unattended multi-Oracle scheduling requires a trusted host lock
or equivalent compare-and-set claim mechanism and is disabled until tested.
Only the Oracle updates status, labels, PR links, or closure. Workers receive
an issue snapshot as untrusted input and cannot mutate Issues.

Use `open` for unfinished work and `closed` only after delivery verification.
When useful, labels `blocked` and `in-progress` describe the current state;
the latest Oracle comment explains blockers and evidence. Do not use a merged
PR or a board column as proof of deployment.

The existing task branch lifecycle remains keyed by a bounded task ID such as
`issue-14`. Its locked, durable, exact-ref deletion and local cleanup gates
are independent of the issue storage backend.
