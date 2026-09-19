# Workflow

## Task intake

A human or approved planning process creates a Bead in the repository that owns
the work. The task must state:

- the desired outcome and acceptance criteria;
- dependencies and affected repository;
- allowed write scope;
- trusted validation commands;
- risk level and review requirements;
- requested delivery level: code, merged change, DEV deployment, or promotion;
- whether the task may proceed without another human approval.

## Implementation

1. Pull the repository and Beads state.
2. List ready work and select exactly one task.
3. Claim the task through the Oracle.
4. Create `codex/<bead-id>-<slug>` in a dedicated worktree.
5. Construct the Codex prompt from trusted factory instructions plus the Bead
   as clearly delimited untrusted task data.
6. Run Codex with workspace-write, no broad host access, and structured output.
7. Execute validation commands from repository configuration, never from Bead
   text.
8. Request read-only review when the configured risk policy requires it.
9. Push the branch and open a pull request containing evidence and the Bead ID.

## Deployment

1. CI validates the merged application commit.
2. CI publishes an immutable image tied to that commit.
3. The Oracle creates or claims a linked deployment Bead in `website-k8s`.
4. A dedicated change updates the deployment image and any matching migration
   job image.
5. The GitOps pull request is reviewed and merged under the environment policy.
6. ArgoCD reconciles the desired state.
7. A read-only observer checks ArgoCD health, pod readiness, relevant logs, and
   public health endpoints.
8. The deployment Bead and then the product Bead close after verification.

## Failure behavior

- Failed validation leaves the task active with a concise failure record.
- Ambiguous scope, missing credentials, or required human decisions block the
  task instead of expanding authority.
- Failed deployment blocks the deployment Bead and never triggers a production
  promotion.
- Attempts are bounded. A later runner resumes from observed state rather than
  repeating mutations blindly.
- Cleanup removes only worktrees and runtime artifacts owned by the completed
  task; it never deletes product or deployment repositories.
