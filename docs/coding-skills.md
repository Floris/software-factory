# Coding skills and project inventory

Inventory checked on **2026-10-02** from the eight registered repositories'
`AGENTS.md`, manifests and representative source files. Paths in the table are
relative to the named repository. The repository's current instructions and
configuration remain authoritative for each task.

| Repository | Representative files | Observed stack and useful skills |
| --- | --- | --- |
| `software-factory` | `scripts/observer_client.py`, `scripts/merged_branch_lifecycle.py`, `tests/test_merged_branch_lifecycle.py` | Python standard library CLI, dataclasses, pathlib, unittest: `coding-style`, `python`. No Python package manager or formatter is declared. |
| `expense-tracker` | `src/app/layout.tsx`, `src/server/ledger/input.ts`, `prisma/schema.prisma`, `src/server/database/factory.ts`, `scripts/publish_image.py`, `scripts/tests/test_publish_image.py` | Next.js 16, React 19, strict TypeScript, Zod 4, Prisma 7, ESLint and Vitest, with Python release helpers: `coding-style`, `nextjs`, `typescript`, plus `web-ui` for visible interface work, `postgres-prisma` for database work and `python` for Python helpers. |
| `pricewatch-droppert` | `apps/web/app/page.tsx`, `apps/worker/src/index.ts`, `packages/db/prisma/schema.prisma`, `packages/db/prisma/migrations/` | Next.js 15, React 19, strict TypeScript workspaces, Zod 3 and Prisma 6: `coding-style`, `nextjs` for web routes, `typescript`, plus `web-ui` for interface work and `postgres-prisma` for database work. Its bounded validation entrypoint is `npm run ci:validate`; a separate lint/test script is not assumed. |
| `droppert-platform` | `apps/json/go.mod`, `apps/json/internal/handlers/handlers.go`, `packages/ui/dist/droppert-ui.js`, `packages/ui/dist/droppert-ui.css` | Four Go 1.21 modules with standard-library HTTP/templates, plus maintained shared vanilla JS/CSS: `coding-style`, `golang` for Go and `web-ui` for templates/assets. The shared UI's `dist` files are maintained source under this repository's conventions. |
| `florisdroppert_com` | `go.mod`, `cmd/server/main.go`, `templates/home.html`, `Makefile` | Go 1.21 standard-library HTTP/templates: `coding-style`, `golang`, plus `web-ui` for templates/styles. |
| `treppord_com` | `go.mod`, `cmd/server/main.go`, `templates/home.html`, `Makefile` | Go 1.21 standard-library HTTP/templates: `coding-style`, `golang`, plus `web-ui` for templates/styles. |
| `droppert_dev` | `config/settings.yaml`, `config/services.yaml`, `public/icons/droppert-mark.svg`, `scripts/validate.sh` | Homepage presentation YAML, static assets and shell validation: `coding-style`, plus `web-ui` for presentation. Its YAML is application configuration, not Kubernetes desired state. |
| `website-k8s` | `apps/expense_tracker_dev/deployment.yaml`, `apps/expense_tracker_dev/migration-job.yaml`, `apps-definitions/expense-tracker-dev-app.yaml`, `tests/test_factory_observer.py` | Kubernetes/ArgoCD desired state with Python unittest validation: `coding-style`, `kubernetes-gitops` for manifests, `python` for Python tests. |

## Select and hand off

The eight skills live under `.agents/skills/`: [`coding-style`](../.agents/skills/coding-style/SKILL.md),
[`nextjs`](../.agents/skills/nextjs/SKILL.md),
[`typescript`](../.agents/skills/typescript/SKILL.md),
[`python`](../.agents/skills/python/SKILL.md),
[`golang`](../.agents/skills/golang/SKILL.md),
[`postgres-prisma`](../.agents/skills/postgres-prisma/SKILL.md),
[`web-ui`](../.agents/skills/web-ui/SKILL.md) and
[`kubernetes-gitops`](../.agents/skills/kubernetes-gitops/SKILL.md).

For a code or configuration task, select `coding-style` plus skills matching
the **actual affected files** and local tooling. A Next.js `.tsx` route usually
needs `nextjs` and `typescript`; add `web-ui` when its visible interaction or
presentation changes. A Go handler needs `golang`; a Go template also needs
`web-ui`. A Python script or test needs `python`. Kubernetes, Kustomize and
ArgoCD manifests need `kubernetes-gitops`; other YAML does not. Select
`postgres-prisma` only when schema, migrations or database-query code changes;
an unrelated TypeScript edit does not need it. Documentation
only edits need no coding skill. The Oracle supplies relevant absolute
`SKILL.md` paths to the writer and quality reviewer because product worktrees
do not discover this factory repository's skills on their own.

These skills explain code choices and review criteria. They do not change the
assigned Issue's write scope, command allowlist, repository instructions,
permissions, model selection or GitOps promotion path. Use the target
repository's validation command supplied for that task. The stack inventory is
a dated snapshot: lockfiles and `go.mod` can change, so inspect them again when
starting work. New upstream documentation may describe APIs unavailable in the
project's installed version.

## Sources and limits

The topic-based guides put practical decisions and code examples directly
in each `SKILL.md`, with focused references for additional cases. Their
packaging follows the [Agent Skills specification](https://agentskills.io/specification).
The [Vercel React best-practices skill](https://github.com/vercel-labs/agent-skills/blob/main/skills/react-best-practices/SKILL.md)
is a structural inspiration; its rule catalog is not copied or a dependency.
The guides use original examples and link their additional primary sources
within the relevant chapters.

The Next.js skill uses the official guides on
[data security](https://nextjs.org/docs/app/guides/data-security),
[Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components)
and [caching](https://nextjs.org/docs/app/guides/caching-without-cache-components).
The TypeScript skill follows the [narrowing handbook](https://www.typescriptlang.org/docs/handbook/2/narrowing.html).
The database skill uses Prisma's version 7 guides on
[transactions](https://www.prisma.io/docs/orm/v7/prisma-client/queries/transactions),
[raw queries](https://www.prisma.io/docs/orm/v7/prisma-client/using-raw-sql/raw-queries)
and [migration history](https://www.prisma.io/docs/orm/v7/prisma-migrate/understanding-prisma-migrate/migration-histories),
plus PostgreSQL's [constraint reference](https://www.postgresql.org/docs/current/ddl-constraints.html).
Prisma 6 and 7 differ from the newest documentation; check the installed
version before using an API example.
The web UI skill draws on [React's guidance on derived state and effects](https://react.dev/learn/you-might-not-need-an-effect),
[WAI-ARIA's native HTML advice](https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/)
and [MDN's `textContent` reference](https://developer.mozilla.org/en-US/docs/Web/API/Node/textContent).

Python guidance draws on [PEP 8](https://peps.python.org/pep-0008/),
[`subprocess`](https://docs.python.org/3/library/subprocess.html) and
[`unittest`](https://docs.python.org/3/library/unittest.html). Go guidance uses
the [code review comments](https://go.dev/wiki/CodeReviewComments),
[Effective Go](https://go.dev/doc/effective_go) and the
[`go.mod` reference](https://go.dev/doc/modules/gomod-ref). The GitOps skill
uses Kubernetes guidance on [Kustomize](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)
and [probes](https://kubernetes.io/docs/concepts/workloads/pods/probes/), plus
ArgoCD's [sync-wave documentation](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/).
These upstream sources explain principles; they do not override pinned
versions, repository-specific contracts or reviewed deployment policy.
