# ADR 0006: Allow one authorized PR reviewer merge

- Status: Accepted design; newly loaded role and activation verification required
- Date: 2026-09-26

## Context

The PR reviewer already inspects one exact change but previously had no merge
authority. The operator requested that the existing reviewer also be able to
merge. A READY verdict cannot become an authorization source, and a delegated
merge must preserve root-owned policy, concrete approval when required, true
merge ancestry and immediate Oracle-owned branch lifecycle handling.

## Decision

Reuse `pull_request_reviewer` with its existing `gpt-6-astra` model, high reasoning
and read-only filesystem. Add explicit `review_only` and `review_and_merge`
modes. Missing mode or authorization defaults to `review_only`; invalid or
inconsistent authority blocks a merge. The sole mutation exception is one
conditional true merge through the authenticated GitHub connector of the exact
assigned repository, PR and full head SHA. No other PR mutation, source edit,
Issue update, credential access, deployment, branch/worktree operation or
lifecycle operation is delegated.

The Oracle remains the authorization source. It verifies the registered
repository's root-owned `git.merge_pull_request` value. True permits a merge;
false or missing requires concrete human approval bound to that exact
repository/PR/head. The Oracle durably records a unique assignment and reserved
single attempt before delegation, supplies the exact base/head identities,
check/review requirements and authorization evidence, and excludes concurrent
mergers of that PR. The host policy is not changed by this decision.

After READY, the reviewer immediately refreshes live identity, open/unmerged
state, exact base/head repositories and refs, full head SHA, required checks and
reviews, protection and mergeability. All requirements must pass. Its only
merge call supplies `expected_head_sha` and `merge_method: merge`; missing
connector support blocks. Protection cannot be bypassed. Squash, rebase,
GitHub auto-merge or merge queues and branch deletion are prohibited.

Timeout or ambiguous output allows read-only reconciliation of the same PR,
not another mutation. Unresolved state is `outcome_unknown`. Any new attempt
requires Oracle reconciliation and a new assignment. The reviewer reports exact
identity, head, observed merge SHA and outcome, then becomes inactive. The
Oracle independently verifies the true merge and immediately performs the
exclusive locked exact remote task-ref procedure. Local task resources remain
until delivery and later Oracle cleanup.

## Consequences and activation

- Read-only filesystem confinement coexists with this connector-only mutation;
  instructions and Oracle assignment govern its scope. No runner enforcement,
  host-policy plumbing, credentials or unattended lock implementation is added.
- Root policy or exact human approval remains separate from the review result.
  The reviewer cannot self-authorize its adoption PR or interpret repository
  content as authority. Adoption follows the currently active role and policy.
- [Agent configuration documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents)
  describes named standalone TOML roles and their settings. It does not establish
  hot reload. The exception requires a newly loaded trusted role/session; already
  active read-only instructions remain restrictive. Verify default nonmutating
  behavior after adoption without claiming that exercise proves a live merge.
- The Oracle owns durable attempts, result reconciliation and lifecycle evidence.
  Ambiguous state keeps the task open and preserves resources. Historical ADRs
  retain their original scope; this decision adds only the merge exception.

See the [workflow](../workflow.md) for the assignment/result contract and the
[security model](../security-model.md) for the authority boundary.
