---
name: kubernetes-gitops
description: Review or edit Kubernetes, Kustomize and ArgoCD desired-state files in the registered GitOps repository. Use only for actual deployment manifests and definitions, not ordinary application YAML.
---

# Kubernetes desired state through GitOps

Read the target repository's `AGENTS.md`, its layout guide, the affected
application definition and related manifests. Confirm the file is actual
Kubernetes, Kustomize or ArgoCD desired state. A Homepage `settings.yaml` or
other application configuration is not a deployment manifest.

- Keep changes in the registered GitOps repository and the assigned scope.
  Use the existing application, namespace and overlay structure. ArgoCD owns
  reconciliation; a manifest edit does not itself prove rollout health.
- Inspect all resources that share the affected image or contract. Preserve
  one immutable release identity across related workloads and migration jobs
  where the repository requires it; do not substitute a mutable tag.
- Keep selectors, labels, names, namespaces and resource references coherent.
  A change to one side of a Service or application selector needs the matching
  side checked.
- Preserve security context, probes, requests and limits unless the task
  supplies evidence for changing them. Choose probes that reflect the app's
  actual startup and health behavior.
- Reference Secrets by name and key where already declared. Never copy
  credential values, rendered Secrets or live cluster state into Git.
- Validate rendered or parsed manifests with the trusted repository command
  supplied for the task. Review the diff for unintended resources and describe
  what still requires ArgoCD or runtime verification after merge.

Read [release and selector examples](references/release-consistency.md) when
changing an image, Service or ArgoCD application. Check official
[Kustomize](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/),
[probe](https://kubernetes.io/docs/concepts/workloads/pods/probes/) and
[ArgoCD sync-wave](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/)
documentation against the repository's installed versions when those features
are involved.
