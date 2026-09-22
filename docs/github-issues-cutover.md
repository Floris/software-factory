# Beads to GitHub Issues cutover

The central Beads remote was exported on 2026-09-21. It contained 38 regular
issues: 37 closed and one open. The open epic `sf-evi` was carried to
[`software-factory#15`](https://github.com/Floris/software-factory/issues/15).
The closed records were initially retained in the previous remote; those refs
were deleted on 2026-09-22. No new Beads claims or writes are needed.
Migration work is tracked in
[`software-factory#14`](https://github.com/Floris/software-factory/issues/14).
The private JSONL export and local Beads archives were deleted on 2026-09-21
at the operator's request. The export's recorded SHA-256 was
`14a534d2b1f96790639f766e7950e96aeb596b3945a3c26c0d4252fe87f18eca`;
the remote `refs/dolt/data` was
`68384c00172154c9272f773c0d56731c45a01977` at export time.

This cutover changes task tracking only. It does not move application source,
Kubernetes desired state or lifecycle records. The operator removed the
top-level `beads` entry and its credential binding from root-owned host
configuration after deploying the matching runner source. The former Beads
refs and old worktree contents were removed after cutover. The local
retirement and exceptional old branches are tracked in
[`software-factory#25`](https://github.com/Floris/software-factory/issues/25).
On 2026-09-22, the operator authorized deletion of 18 exact remote refs across
eight repositories: eight `refs/dolt/data` refs, six
`refs/heads/__dolt_remote_info__` refs, three merged legacy task branches, and
one cancelled task branch. The Oracle recorded their names and SHA values in
issue #25, deleted each with a SHA-bound lease, and verified that only
`refs/heads/main` remained in each remote. A private durable execution journal
is held under `/srv/software-factory/runtime/remote-retirement/` on the VPS.
Deleting refs does not guarantee immediate erasure of unreachable Git objects
or GitHub PR metadata.

The GitHub connector in supervised sessions supplies issue read/write access.
Unattended execution still needs a reviewed, repository-scoped Issues
credential and atomic claim implementation before scheduling is enabled.
