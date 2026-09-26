# ADR 0005: Isolate Kubernetes observation behind a status gateway

- Status: Accepted design; live installation and capability verification pending
- Date: 2026-09-26

## Context

The dedicated observer RBAC is owned by `website-k8s`, but implementation and
product processes share the factory Unix UID. Giving that UID a token or
kubeconfig would expose the observer credential to repository-controlled code.
A workspace sandbox does not separate same-UID credential readers.

## Decision

Use an on-demand serial systemd socket gateway with a distinct DynamicUser and
private LoadCredential copies. Only the operator installs immutable root-owned
code, units, non-secret routing/connection policy and the existing private token
source. The factory calls an installed non-root client for a strict per-app
status operation; it receives a bounded projection and never credentials.

No peer check distinguishes Oracle and product code sharing its UID. Both may
obtain the same limited status and contend for availability. Fixed GET routing,
UID ownership filtering, verified TLS, an isolated collector with an absolute
deadline, bounded parsing/output and process hardening contain that interface.
The operator owns manual renewal and service restart; there is no timer,
scheduler, credential provider framework or Kubernetes controller.

## Consequences

This repository owns gateway behavior; root-owned host policy owns installed
stable routes; `website-k8s` retains desired state and observer RBAC. No current
images, replicas or live mappings are copied into factory policy. The unit and
systemd credential copies establish source provenance where DynamicUser cannot
traverse original root-private parents. Operator verification of original
metadata and live isolation is a separate delivery gate. A successful projection
proves transport completeness, not application health or deployment delivery.
See the [gateway runbook](../observer-gateway.md) for schemas, bounds and proof.
