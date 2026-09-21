# Beads to GitHub Issues cutover

The central Beads remote was exported on 2026-09-21. It contained 38 regular
issues: 37 closed and one open. The open epic `sf-evi` was carried to
[`software-factory#15`](https://github.com/Floris/software-factory/issues/15).
The closed records remain read-only historical data in the previous remote;
no new Beads claims or writes are needed. Migration work is tracked in
[`software-factory#14`](https://github.com/Floris/software-factory/issues/14).
The private JSONL export is stored under the factory runtime root with a
`0700` parent directory and `0600` file mode. Its SHA-256 is
`14a534d2b1f96790639f766e7950e96aeb596b3945a3c26c0d4252fe87f18eca`;
the remote `refs/dolt/data` was
`68384c00172154c9272f773c0d56731c45a01977` at export time.

This cutover changes task tracking only. It does not move application source,
Kubernetes desired state, host policy, or lifecycle records. The operator may
remove the top-level `beads` entry and its credential binding from root-owned
host configuration after deploying the matching runner source. The lifecycle
runner accepts the existing version-2 host configuration during transition
and does not use its `beads` entry. The old `.beads` directory and remote must
not be treated as live task authority.

The GitHub connector in supervised sessions supplies issue read/write access.
Unattended execution still needs a reviewed, repository-scoped Issues
credential and atomic claim implementation before scheduling is enabled.
