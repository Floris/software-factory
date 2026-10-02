# Release and selector examples

Bad: a web Deployment moves to image `sha-new`, while its migration Job keeps
`sha-old` and the release expects matching schema and application code.

Better: inspect the related workloads and use the same reviewed immutable
release identity where the repository contract requires it. Check the rendered
resources before promoting the change.

Bad: a Service selector changes from `app: api` to `app: web` while the Pod
template still labels its Pods `app: api`.

Better: compare the selector with the Pod labels and verify that it selects
only the intended workload. Use a repository-provided validation command and
review the resulting manifest diff.
