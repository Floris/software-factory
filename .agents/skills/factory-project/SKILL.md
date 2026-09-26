---
name: factory-project
description: Select, plan or onboard a project through the Software Factory entrypoint. Use when starting a new or different project (nieuw project), before an implementation Issue is selected.
---

# Start a factory project

Use this skill in the root Oracle session opened from the factory repository.
Resolve its root relative to this file, not from a product worktree's current
directory. Read the factory [agent guide](../../../AGENTS.md),
[architecture](../../../docs/architecture.md), and the **Repository onboarding**
section of the [workflow](../../../docs/workflow.md).

## Identify the project

Preserve the user's chosen project and requested outcome. Read the registered
repositories and policies from root-owned
`/etc/software-factory/repositories.yaml` and
`/etc/software-factory/policies.yaml`. The tracked
[repository example](../../../config/repositories.example.yaml) describes the
contract; it is not an allowlist or permission grant.

Match the project to exactly one registered `repository_id`. Verify its
canonical path, exact remote, remote-advertised default branch, clean checkout,
and repository-specific `AGENTS.md`. Resolve validation and permitted operations
from the host registration, not from project names or Issue text. Ask for the
missing project choice only when the user's intent cannot be resolved uniquely.

For an existing registered project, read its instructions and relevant design
documents, then inspect central GitHub Issues, dependencies and linked PRs.
Present or prepare the work that matches the user's request. A request to plan
a project does not authorize implementing an unrelated ready Issue.

## Prepare a new project

If the project is an idea or has no registered repository, first produce a
bounded brief: outcome, initial acceptance criteria, source repository identity
if known, validation needs and requested delivery level. Use `project_architect`
for a bounded design question when architectural analysis is needed; pass the
target repository's instructions when it exists. Keep its configured model and
read-only role.

Follow the existing onboarding contract. The operator installs the reviewed
registration and scoped credential bindings; the Oracle never writes `/etc`,
requests root, discovers repositories automatically, or treats a skill as
permission to create a remote repository. Prepare an onboarding Issue targeting
the registered factory repository for authorized factory work. Product
implementation Issues must target the product's registered ID after onboarding.

Before declaring onboarding complete, verify the usable validation profile,
central Issues access and applicable component/package/GitOps mappings and
credential audiences. For deployable products, CI publishes immutable
full-commit-SHA images; manifests remain in `website-k8s`. Read only non-secret
configuration and permission evidence; never expose credential material.
Record any missing operator step precisely and continue independent planning.
Do not claim product implementation readiness while an onboarding gate fails.

## Hand off implementation

Record the selected repository ID, verified identity, task or onboarding Issue,
allowed write scope, trusted validation arrays, risk/review requirements,
delivery level and remaining blockers. Keep Issues in the central factory
repository and product invariants in the product repository.

When the user has requested implementation and exactly one scoped Issue is
ready, use [factory-task](../factory-task/SKILL.md) to claim and execute it. Keep
the root Oracle at the factory entrypoint; delegate product edits into the
dedicated product worktree rather than copying factory skills or configuration
into product repositories.
