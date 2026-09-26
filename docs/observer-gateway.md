# Restricted observer gateway

The gateway supplies on-demand deployment status without giving the factory a
Kubernetes credential. It is a host service, not a Kubernetes controller. ArgoCD
remains the deployment path and `website-k8s` remains desired state. The tracked
files are reviewed installation artifacts and neutral examples; no live
installation or access is implied by static tests.

## Protocol and policy

Invoke only the root-installed client as non-root:

```text
/usr/bin/python3 -I -B -S /usr/local/lib/software-factory/observer_client.py --application sample-app
```

The fixed Unix socket is `/run/software-factory-observer/status.sock`. The client
sends exactly one UTF-8 JSON object and shuts down its write half. The broker
requires EOF within two seconds, at most 256 bytes, version `1`, operation
`status`, and a configured `application`. Duplicate keys, additional fields,
trailing bytes, arbitrary paths, URLs, selectors, verbs and timeouts are denied.
The client has an absolute 15-second budget and a 64 KiB response ceiling.

`policy.example.json` defines the non-secret schema: `version: 1` and up to 32
`applications`. Each entry has an exact Application `id`, `argocd_namespace`,
workload `namespace`, and up to 16 distinct `{kind, name}` bindings. Supported
kinds are Deployment, ReplicaSet, StatefulSet, Job and CronJob. Empty workloads
permit Argo-only observation. The operator derives installed bindings from
reviewed registration and GitOps routing. Argo references and Issue content
cannot expand them. Policy contains no expected image, replica count or release.

`connection.example.json` contains only `version: 1`, an HTTPS `server` without
credentials/path/query, and `ca_data`, base64 of the independently verified PEM
cluster CA. Replace its intentionally invalid placeholder before installation.
No kubeconfig, client certificate, exec plugin, proxy, redirect or TLS bypass is
supported. All requests are fixed GET routes for named Applications/workloads
and namespaced Pod/ReplicaSet/Job lists. No logs, Secrets, auth reviews, mutation
or token issuance are exposed.

## Projection and limits

Responses have `{version:1, ok:true, status:{application, workloads, observedAt}}`
or `{version:1, ok:false, error:<fixed-code>}`. Codes are `invalid_request`,
`unavailable`, `access_denied`, `limit_exceeded`, and `rate_limited`; errors never
include upstream bodies or exceptions. A complete successful observation is
not a health verdict. Unknown values and an absent configured workload remain
explicit; an absent transient migration Job has `present:false`, not success or
failure of a migration. Application health/sync are validated enums with an
optional full commit revision. Workload projections include identity/UID,
generation, selected observed counts, desired replicas or suspend state where
applicable, and template images. Pod projections contain readiness, phase,
deleting state, validated container image/digest, restarts and readiness.
Missing desired replicas or suspend values are `null`, never invented defaults.

The broker follows Deployment→ReplicaSet→Pod, CronJob→Job→Pod and direct
StatefulSet/ReplicaSet/Job→Pod controller name/kind/UID links. Labels alone grant
no inclusion. No annotations, environment, condition messages, arbitrary raw
objects, logs, URLs or credentials reach the client. Literal token reflection
in an otherwise valid projected field fails closed.

Kubernetes [typed collections](https://kubernetes.io/docs/reference/using-api/api-concepts/#collections)
can omit `kind` and `apiVersion` from their items. On every list page, the gateway
requires the collection's kind and API version to match the fixed requested
endpoint. It derives only absent item type fields from that validated type in
a copy of each item; explicitly conflicting fields, including `null`, fail
closed. Named-object identity, namespace, name, UID and controller ownership
checks still apply without inference outside the typed-list boundary.

There is one serial Accept=no broker and one collector at a time. Collection
starts are at least one second apart; early requests receive `rate_limited`.
The root-installed script collects in a fixed isolated Python subprocess with
an absolute ten-second timeout covering DNS, TLS, headers and trickling bodies.
Timeout kills and reaps the child before another collection. Each body is at
most 256 KiB; lists have at most four pages of 64 objects (256 total per list),
and final output is at most 64 KiB. Overflow, malformed data or failed pages
return a fixed error, never a partial/stale successful snapshot. The broker
exits after 30 seconds without an accepted connection. Backlog, CPU, memory,
file-descriptor and process limits bound contention.

## Identity and immutable installation

systemd 255 on Linux creates the socket as root:codex `0660` under a tmpfiles
root:codex `0750` directory. The service has a distinct DynamicUser, no codex
supplementary group, capabilities or writable source, and receives FD 3. It
does not use RuntimeDirectory, which could remove the listener on idle exit.
PID1's listening socket may report root peer credentials; the client instead
checks root ownership, nonwritable nonsymlink parents and exact socket metadata.
The broker allows the codex UID. Products executing with that same UID can get
the identical limited summary and compete for availability; this does not
authenticate the Oracle as a separate identity.

Both scripts refuse production execution from a worktree. Install their
verified reviewed versions, root-owned and nonwritable by other users, under
`/usr/local/lib/software-factory/`. Python uses `-I -B -S`, excluding environment,
user imports and worktree imports. Before private reads, broker and collector
set Linux `PR_SET_DUMPABLE=0`; failure aborts. The unit also disables core dumps,
stdout/stderr logging, privileges, home access and most host mutation.

The immutable unit binds three LoadCredential sources:

- `observer-token`: existing `/etc/software-factory/observer/token`, root-only;
- `observer-connection`: `/etc/software-factory/observer-connection.json`;
- `observer-policy`: `/etc/software-factory/observer-policy.json`.

Connection and policy are non-secret, but their original parent need not be
traversable by DynamicUser. The service validates copies in the fixed systemd
credential directory before reading bytes. It accepts either root/service-owned
private directories `0500`/`0700` and files `0400` without an access ACL, or the
root-owned systemd 255 layout: directory `0550`, files `0440`, and exactly five
Linux access ACL entries. Those entries grant owner and the one named service
UID `r-x` on the directory or `r--` on files, with the same mask and zero rights
for owning group and other. The group mode bits represent the ACL mask; they
do not grant the owning group access. Extra principals, ACL write/special bits,
wrong IDs, malformed ACLs and mask/mode mismatches are denied. Only explicit
absent/unsupported ACL results permit the private-mode fallback; permission
and other lookup failures fail closed.

The directory and fixed relative filenames are opened without following
symlinks. Descriptor-based type, owner, mode, ACL and size checks precede bounded
reads from the same file inode. Nonblocking file opens prevent an unexpected
FIFO from stalling validation. The operator verifies original source ownership
and nonwritability; the service cannot inspect root-private source parents. The root-owned unit and
systemd copies establish that provenance. Collector argv contains only fixed
code arguments; its environment contains only the credential-directory path,
never the token. The token's JWT subject, namespace, ServiceAccount name and
expiry are consistency-checked before requests. This is not signature
verification: the TLS-verified API is the authentication authority. Admin,
wrong-account, expired and revoked credentials have no fallback.

## Manual operator installation and renewal

These steps belong to the human operator, never to the Oracle or a worker:

1. Review the exact merged artifacts and public routing proposal. Validate the
   endpoint/CA and the dedicated observer RBAC independently. Keep the private
   token out of Git, runtime evidence, argv, environment, chat and logs.
2. Install both scripts root:root `0755` under the fixed `/usr/local/lib` directory
   with root-owned nonwritable parents. Install the two JSON sources root:root
   `0644` under protected `/etc/software-factory`; maintain the existing token
   source root-only `0600` under a root-only directory. Verify no symlinks or
   untrusted writable parents. Never run repository-controlled code with root.
3. Install reviewed units in `/etc/systemd/system` and the `.conf` in
   `/etc/tmpfiles.d`, root-owned nonwritable. Review syntax with
   `systemd-analyze verify`, create the tmpfiles directory, reload systemd and
   enable/start only the socket. No timer, scheduler, token Secret or renewal
   controller is installed.
4. Renew the observer token manually using the established private TokenRequest
   procedure, preserving the old file if issuance fails and recording actual
   expiry privately. Atomic replacement targets the same existing token source.
   Stop/restart the service after renewal so the activation-snapshotted
   LoadCredential copy refreshes; the socket remains the activation entrypoint.
5. Check the service UID differs from codex, no supplementary codex group,
   protected source/copy/socket metadata, disabled dumping, hardening and absence
   of credential access by codex/products. A private operator verifier must use
   `credential_metadata(fd, service_uid, directory=False)` from the reviewed,
   frozen installed gateway for each opened copy (`directory=True` for the
   directory). Bind the captured service UID to the running PID and its start
   time and verify that identity remains stable around the checks. Pass that
   verified non-root UID explicitly, even when the verifier runs as root;
   never substitute the verifier's effective UID or weaken the ACL check.
   The reusable validator reads only metadata and no credentials at import.
   Test generic errors for expired and wrong tokens using only private operator
   facilities. Verify fresh per-app
   status through the installed client as non-root; never hand a token or admin
   context to the factory. Record sanitized evidence only.

Live access is unverified until these steps and non-root status checks succeed.
Keep dependent delivery tasks open. Host installation introduces no Kubernetes
desired-state change and no factory root capability.
