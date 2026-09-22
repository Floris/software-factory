# ADR 0004: Use central GitHub Issues for task state

- Status: Accepted; supersedes ADR 0002 for new task work
- Date: 2026-09-21

## Context

The central Beads database requires an embedded Dolt manifest, remote sync,
and ownership recovery before routine task work. Its manifest became
unreadable again after the manual cutover. The factory already uses GitHub for
source repositories, CI, PR review, and merge evidence. GitHub Issues is
included in the free plan.

## Decision

Use Issues in `Floris/software-factory` as the single task source for factory,
product, and GitOps work. Route each issue by an explicit, validated
`repository_id`; link cross-repository issues and PRs by URL. Keep durable
architecture and runbooks in Git-tracked Markdown. Git remains the source and
promotion audit boundary, and root-owned host configuration remains the
repository and credential authority. A GitHub issue cannot supply commands,
paths, permissions, or policy authority.

The 37 closed Beads were initially archived; their local archives and selected
remote refs were later removed at the operator's request on 2026-09-22, as
recorded in [issue #25](https://github.com/Floris/software-factory/issues/25).
The one open Bead, `sf-evi`, maps to factory issue #15. No future task is
created in Beads. In supervised sessions, the Oracle uses the existing
authenticated GitHub connector. Unattended task
claiming remains disabled until a bounded, tested coordination mechanism and
least-privilege Issues credential exist.

## Consequences

- No Dolt manifest, Beads remote, or `beads_sync` credential is needed for
  supervised task work.
- GitHub availability is now the task-intake dependency. Source work, review,
  delivery, and branch cleanup retain their existing independent gates.
- Issue comments can record attended claims, but do not provide atomic
  multi-Oracle exclusion. The trusted host runner must supply that before
  unattended scheduling.
