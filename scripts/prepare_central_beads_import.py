#!/usr/bin/env python3
"""Prepare a private, validated JSONL import for the central Beads candidate.

This tool never opens a Beads database, changes a source export, or publishes a
remote. Source names are operator-verified repository IDs, not issue prefixes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys


REPOSITORY_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")


def parse_source(value: str) -> tuple[str, Path]:
    repository_id, separator, name = value.partition("=")
    if not separator or not REPOSITORY_ID.fullmatch(repository_id) or not name:
        raise argparse.ArgumentTypeError("source must be repository-id=/private/export.jsonl")
    return repository_id, Path(name)


def private_regular_file(info: os.stat_result, path: Path) -> None:
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"source is not a regular file: {path}")
    if info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError(f"source must be owned by this user and private: {path}")


def read_issues(repository_id: str, path: Path) -> tuple[list[dict], str]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        private_regular_file(os.fstat(stream.fileno()), path)
        raw = stream.read()
    digest = hashlib.sha256(raw).hexdigest()
    issues: list[dict] = []
    for number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            raise ValueError(f"blank JSONL row in {path}:{number}")
        issue = json.loads(line)
        if not isinstance(issue, dict) or issue.get("_type", "issue") != "issue":
            raise ValueError(f"non-issue row in {path}:{number}")
        issue_id = issue.get("id")
        if not isinstance(issue_id, str) or not issue_id or not isinstance(issue.get("title"), str):
            raise ValueError(f"invalid issue ID or title in {path}:{number}")
        metadata = issue.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ValueError(f"invalid metadata for {issue_id}")
        current = metadata.get("repository_id")
        if current is not None and current != repository_id:
            raise ValueError(f"conflicting repository_id for {issue_id}")
        issue["metadata"] = {**metadata, "repository_id": repository_id}
        issues.append(issue)
    return issues, digest


def prepare(sources: list[tuple[str, Path]], output: Path) -> dict:
    if len({repository_id for repository_id, _ in sources}) != len(sources):
        raise ValueError("duplicate repository ID")
    if output.exists() or output.is_symlink():
        raise ValueError("output already exists")
    parent = output.parent.resolve(strict=True)
    info = parent.stat()
    if info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError("output directory must be owned by this user and private")

    issues: list[dict] = []
    source_hashes: dict[str, str] = {}
    for repository_id, path in sources:
        rows, digest = read_issues(repository_id, path)
        source_hashes[repository_id] = digest
        issues.extend(rows)

    ids = [issue["id"] for issue in issues]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate issue ID across source exports")
    known = set(ids)
    edges = 0
    for issue in issues:
        for edge in issue.get("dependencies") or []:
            if not isinstance(edge, dict) or edge.get("issue_id") != issue["id"]:
                raise ValueError(f"invalid dependency edge in {issue['id']}")
            if edge.get("depends_on_id") not in known:
                raise ValueError(f"dangling dependency in {issue['id']}")
            edges += 1

    payload = b"".join(
        json.dumps(issue, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        for issue in issues
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(output, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return {
        "issue_count": len(issues),
        "dependency_count": edges,
        "source_sha256": source_hashes,
        "output_sha256": hashlib.sha256(payload).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=parse_source, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.source, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"prepare-central-beads-import: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
