---
name: kubernetes-gitops
description: Review or edit Kubernetes, Kustomize and ArgoCD desired-state files in the registered GitOps repository. Use only for actual deployment manifests and definitions, not ordinary application YAML.
---

# Kubernetes and ArgoCD GitOps best practices

## Contents

- [Desired-state ownership](#desired-state-ownership)
- [Manifest structure and naming](#manifest-structure-and-naming)
- [Workloads and health](#workloads-and-health)
- [Services and networking](#services-and-networking)
- [Configuration and Secrets](#configuration-and-secrets)
- [Release consistency and ordering](#release-consistency-and-ordering)
- [Testing and verification](#testing-and-verification)
- [Performance and capacity](#performance-and-capacity)
- [Security](#security)
- [Anti-slop review](#anti-slop-review)

Read the target repository's `AGENTS.md`, its layout guide, the affected
application definition and related manifests. Confirm the file is actual
Kubernetes, Kustomize or ArgoCD desired state. A Homepage `settings.yaml` or
other application configuration is not a deployment manifest.
Read [release and selector examples](references/release-consistency.md)
when changing an image, Service or ArgoCD application. Check the official
[Kustomize guide](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)
against the repository's installed tooling when composing overlays.

## Desired-state ownership

- The registered `website-k8s` repository owns permanent Kubernetes,
  Kustomize and ArgoCD desired state. ArgoCD reconciles it after reviewed
  Git promotion. A local manifest edit or render is not proof of a live
  rollout.
- Confirm that the file is deployment state before applying this skill.
  Homepage `settings.yaml` and other application YAML belong to their
  product repositories and follow their own validation.
- Read the target repository's `AGENTS.md`, affected application definition,
  namespace/overlay layout and linked product release contract. Do not
  copy deployment state or Secrets into the factory repository.

## Manifest structure and naming

- Follow the existing application and overlay pattern. Keep resource names,
  namespace, labels and selectors aligned. A change to one side of a
  reference needs its target checked: Service to Pods, ConfigMap key to
  volume/env, ArgoCD Application path to files.
- Declare the resource shape directly. Avoid a templating layer or overlay
  split for a one-off value unless the repository already uses that
  mechanism. Kustomize can compose shared base and environment patches
  when those are real variants.
- Review a rendered manifest for unexpected resources, duplicate names,
  obsolete objects and changed selectors.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: document-web
spec:
  selector:
    app: document-web
  ports:
    - port: 80
      targetPort: http
```

The matching Pod template must carry `app: document-web` and expose a
container port named `http` for this example.

## Workloads and health

- Preserve the workload's existing security context, resource requests
  and limits unless the task has evidence to change them. Requests affect
  scheduling; limits can change failure behavior under load.
- Choose probes for the app's actual startup and readiness contract.
  A readiness probe should protect traffic to a not-yet-ready instance;
  a liveness probe should not restart an app for a temporary dependency
  outage. A startup probe can give slow initialization time when needed.
- Keep container command, working directory, volumes and port names
  consistent with the released image. A successful YAML parse cannot
  prove that an image implements a health endpoint.

```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: http
  periodSeconds: 5
```

Use `/ready` only if the application actually serves that endpoint. See
the [Kubernetes probe guide](https://kubernetes.io/docs/concepts/workloads/pods/probes/).

## Services and networking

- Compare Service selectors against Pod labels, not just label spelling.
  A typo can leave an apparently valid Service with zero endpoints or
  route traffic to the wrong workload.
- Keep ports and protocol names consistent across Service, workload and
  ingress/application route. Check the actual path/host contract when
  changing routing.
- Treat network policies and exposure as security-sensitive behavior.
  A broader selector or namespace change can alter which workload
  receives traffic.

## Configuration and Secrets

- Keep non-secret configuration in the repository's approved ConfigMap or
  manifest pattern. Reference Secrets by existing name/key; never commit
  credential values or rendered Secret manifests.
- Verify that every referenced key exists in the intended declared
  contract without reading live secret values. A missing key can prevent
  Pods from starting even when YAML validates.
- A ConfigMap value change may require a rollout depending on how the app
  consumes it. Name that behavior instead of assuming automatic reload.

```yaml
env:
  - name: DATA_SOURCE_URL
    valueFrom:
      secretKeyRef:
        name: document-database
        key: url
```

This example shows a reference only; use the target repository's actual
non-secret key contract.

## Release consistency and ordering

- Inspect every workload, migration Job and related resource that shares
  an image or schema contract. Where the repository requires a single
  release identity, use the same immutable digest or full-SHA image tag
  across them; never switch to a mutable `latest` tag.
- Use ArgoCD sync waves or hooks only when ordering is a real contract.
  A migration that must finish before a new workload starts needs that
  ordering and a failure policy verified for this app. Do not assume a
  wave number alone proves readiness.
- Keep image references tied to the approved artifact. Deployment and
  image build are separate evidence gates. See the
  [release examples](references/release-consistency.md) and
  [ArgoCD sync-wave guide](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/).

## Testing and verification

- Run only the trusted target-repository validation command. Render or
  parse manifests with the repository's installed tooling when supplied,
  then inspect the resource diff for labels, selectors, images and
  references.
- A schema check or Kustomize render cannot prove container startup,
  traffic routing or ArgoCD health. Report those as later runtime checks
  through the approved read-only observer path.
- Use focused regression tests for a changed deployment invariant when
  the repository has a suitable test harness. Do not add a test that
  merely searches for a string already visible in the manifest.

## Performance and capacity

- Base resource changes on observed usage and the target environment's
  capacity. Requests, limits, replica count and probe timing interact;
  a generic recommendation can make scheduling worse.
- Check image size and startup behavior before stretching health timers
  to hide a real failure. Do not add replicas without considering
  database connection limits and stateful dependencies.
- Keep deployment changes bounded to the requested app and release.

## Security

- Preserve least-privilege security context, namespace scope and existing
  network boundaries. Do not request root, cluster-admin, container socket
  access or access to Kubernetes Secret values for the factory.
- Avoid embedding credentials, rendered Secrets or live cluster state in
  Git, examples or diagnostics. References can be reviewed without
  exposing values.
- Use immutable image identities for releases and verify the exact
  artifact before promotion according to the target repository contract.

## Anti-slop review

- Reject a Service selector that no longer matches its Pods, a renamed
  ConfigMap key with unchanged consumers, or a probe path the image
  does not serve.
- Reject a web image update with a stale migration Job image where the
  release contract requires one identity. Reject a mutable image tag or
  a sync-wave change with no ordering/failure explanation.
- Reject the claim "deployment verified" after only a YAML parse or
  render. State separately what Git diff, static validation and observed
  runtime health actually prove.
