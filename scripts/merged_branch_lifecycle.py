#!/usr/bin/env python3
"""Trusted, single-task Git branch lifecycle runner.

The unattended mode requires a root-owned installation and a GitHub read token.
The supervised Oracle mode accepts short-lived connector evidence and runs from
the reviewed checkout. Repository and policy paths remain root-owned inputs.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener

import yaml


REGISTRATION = Path("/etc/software-factory/repositories.yaml")
POLICIES = Path("/etc/software-factory/policies.yaml")
STATE_ROOT = Path("/var/lib/software-factory/lifecycle")
SUPERVISED_ROOT = Path("/srv/software-factory/runtime/lifecycle")
EVIDENCE_ROOT = Path("/srv/software-factory/runtime/lifecycle-evidence")
SUPERVISED_EVIDENCE: dict | None = None
GIT = "/usr/bin/git"
TASK_ID = re.compile(r"[a-z][a-z0-9-]{1,31}(?:\.[0-9]{1,3})?")
REPOSITORY_ID = re.compile(r"[a-z][a-z0-9-]{1,31}")
SHA = re.compile(r"[0-9a-f]{40}")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


class Blocked(RuntimeError):
    """An unsafe or unproven lifecycle transition."""


def run(argv: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    if argv[0] != "git":
        raise Blocked("runner accepts only fixed Git operations")
    command = [GIT, "-c", "core.hooksPath=/dev/null", *argv[1:]]
    environment = os.environ.copy()
    for key in list(environment):
        if key.startswith("GIT_CONFIG_") or key in ("GIT_SSH_COMMAND", "GIT_ASKPASS", "SSH_ASKPASS"):
            del environment[key]
    environment.update({"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1",
                        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_SSH": "/usr/bin/ssh"})
    result = subprocess.run(command, cwd=cwd, env=environment, text=True, capture_output=True, check=False)
    if check and result.returncode:
        raise Blocked(f"{argv[0]} {argv[1]} failed (exit {result.returncode}): {result.stderr.strip()}")
    return result


def root_yaml(path: Path) -> dict:
    st = path.lstat()
    if not path.is_file() or path.is_symlink() or st.st_uid != 0 or st.st_mode & 0o022:
        raise Blocked(f"host configuration is not root-owned and immutable: {path}")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise Blocked(f"invalid host configuration: {path}")
    return data


def repository_config(repository_id: str) -> tuple[dict, dict, dict]:
    registration = root_yaml(REGISTRATION)
    policies = root_yaml(POLICIES)
    if registration.get("version") != 2:
        raise Blocked("central Beads registration version 2 is required")
    repositories = registration.get("repositories")
    if not isinstance(repositories, list):
        raise Blocked("missing repository registrations")
    central_beads = registration.get("beads")
    if not isinstance(central_beads, dict) or not central_beads.get("path") or not central_beads.get("remote"):
        raise Blocked("central Beads registration is missing")
    if any(isinstance(item, dict) and "beads" in item for item in repositories):
        raise Blocked("mixed central and per-repository Beads routing")
    matches = [item for item in repositories if isinstance(item, dict) and item.get("id") == repository_id]
    if len(matches) != 1:
        raise Blocked("repository ID is absent or ambiguous")
    entry = matches[0]
    bindings = entry.get("credential_refs")
    if not isinstance(bindings, dict) or not bindings.get("git_read") or not bindings.get("git_write"):
        raise Blocked("repository-scoped Git credential bindings are missing")
    if not central_beads.get("credential_ref"):
        raise Blocked("central Beads sync credential binding is missing")
    policy = policies.get("policies", {}).get(entry.get("policy"))
    if not isinstance(policy, dict) or policy.get("lifecycle", {}).get("delete_merged_remote_branch") is not True:
        raise Blocked("root-owned lifecycle deletion policy is missing or false")
    if policy.get("git", {}).get("delete_branch") is not False:
        raise Blocked("model-controlled Git branch deletion must remain denied")
    checkout = Path(entry.get("path", ""))
    if not checkout.is_absolute() or checkout.is_symlink() or not checkout.is_dir():
        raise Blocked("invalid canonical repository path")
    if run(["git", "rev-parse", "--show-toplevel"], checkout).stdout.strip() != str(checkout):
        raise Blocked("canonical repository path mismatch")
    if run(["git", "remote", "get-url", "origin"], checkout).stdout.strip() != entry.get("remote"):
        raise Blocked("Git origin differs from root-owned registration")
    if run(["git", "remote", "get-url", "--push", "origin"], checkout).stdout.strip() != entry.get("remote"):
        raise Blocked("Git push URL differs from root-owned registration")
    if run(["git", "status", "--porcelain"], checkout).stdout:
        raise Blocked("canonical checkout is dirty")
    return registration, entry, policy


def github_name(remote: str) -> str:
    match = re.fullmatch(r"(?:git@github\.com:|https://github\.com/)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\.git", remote)
    if not match or not REPO.fullmatch(match.group(1)):
        raise Blocked("unsupported GitHub remote identity")
    return match.group(1)


def github_data(repo: str, endpoint: str) -> object:
    if SUPERVISED_EVIDENCE is not None:
        evidence = SUPERVISED_EVIDENCE
        if repo != evidence["repo"]:
            raise Blocked("connector evidence repository mismatch")
        if endpoint == f"pulls/{evidence['pr_number']}":
            pr = evidence["pull_request"]
            return {"state": pr["state"], "merged": pr["merged"],
                    "merge_commit_sha": pr["merge_commit_sha"],
                    "head": {"ref": pr["head"], "sha": pr["head_sha"],
                             "repo": {"full_name": pr["head_repo_full_name"]}},
                    "base": {"ref": pr["base"]}}
        if endpoint == "":
            return {"default_branch": evidence["default_branch"]}
        owner = repo.split("/", 1)[0]
        branch = evidence["pull_request"]["head"]
        if endpoint == f"branches/{quote(branch, safe='')}":
            if evidence["branch_info"] is None:
                raise Blocked("connector branch evidence is missing")
            return evidence["branch_info"]
        if endpoint == f"pulls?state=open&head={quote(f'{owner}:{branch}', safe='')}&per_page=100":
            return evidence["open_pull_requests"]
        raise Blocked("connector evidence does not cover GitHub query")
    token = os.environ.get("SF_GITHUB_TOKEN", "")
    if not token:
        raise Blocked("trusted launcher did not supply GitHub read credentials")
    suffix = f"/{endpoint}" if endpoint else ""
    request = Request(
        f"https://api.github.com/repos/{repo}{suffix}",
        headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"},
    )
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=15) as response:
            result = json.load(response)
    except Exception as exc:
        raise Blocked("GitHub identity or protection query failed") from exc
    return result


def load_supervised_evidence(path: Path, task_id: str, repository_id: str, pr_number: int) -> dict:
    if path.parent != EVIDENCE_ROOT or path.is_symlink():
        raise Blocked("connector evidence must be in the fixed runtime directory")
    root = EVIDENCE_ROOT.lstat()
    if not stat.S_ISDIR(root.st_mode) or root.st_uid != os.getuid() or root.st_mode & 0o077:
        raise Blocked("connector evidence directory must be private")
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077 or st.st_size > 16384:
        raise Blocked("connector evidence file must be private and bounded")
    evidence = json.loads(path.read_text())
    required = {"version", "repo", "task_id", "repository_id", "pr_number", "observed_at",
                "pull_request", "default_branch", "open_pull_requests", "branch_info"}
    if not isinstance(evidence, dict) or set(evidence) != required:
        raise Blocked("invalid connector evidence schema")
    if evidence["version"] != 1 or (evidence["task_id"], evidence["repository_id"], evidence["pr_number"]) != (task_id, repository_id, pr_number):
        raise Blocked("connector evidence task identity mismatch")
    if not isinstance(evidence["repo"], str) or not REPO.fullmatch(evidence["repo"]):
        raise Blocked("invalid connector evidence repository")
    if not isinstance(evidence["default_branch"], str) or not isinstance(evidence["open_pull_requests"], list):
        raise Blocked("invalid connector evidence repository facts")
    pr = evidence["pull_request"]
    pr_fields = {"number", "state", "merged", "head", "head_sha", "head_repo_full_name", "base", "merge_commit_sha"}
    if not isinstance(pr, dict) or set(pr) != pr_fields or pr["number"] != pr_number:
        raise Blocked("invalid connector pull request evidence")
    if pr["head_repo_full_name"] != evidence["repo"] or not isinstance(pr["base"], str):
        raise Blocked("connector pull request repository or base mismatch")
    if not isinstance(pr["head"], str) or not pr["head"].startswith(f"codex/{task_id.replace('.', '-')}-"):
        raise Blocked("connector pull request task branch mismatch")
    if not all(isinstance(pr[key], str) and SHA.fullmatch(pr[key]) for key in ("head_sha", "merge_commit_sha")):
        raise Blocked("invalid connector commit identities")
    branch_info = evidence["branch_info"]
    if branch_info is not None:
        if (not isinstance(branch_info, dict) or set(branch_info) != {"name", "sha", "protected"}
                or branch_info["name"] != pr["head"] or branch_info["sha"] != pr["head_sha"]
                or branch_info["protected"] is not False):
            raise Blocked("connector branch is protected or has a mismatched identity")
    if pr["state"] != "closed" or pr["merged"] is not True or evidence["open_pull_requests"]:
        raise Blocked("connector evidence does not prove an unshared merged PR")
    try:
        seen = datetime.fromisoformat(evidence["observed_at"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - seen).total_seconds()
    except (AttributeError, TypeError, ValueError) as exc:
        raise Blocked("invalid connector evidence timestamp") from exc
    if seen.tzinfo is None or age < -30 or age > 900:
        raise Blocked("connector evidence is stale or in the future")
    return evidence


def github_json(repo: str, endpoint: str) -> dict:
    result = github_data(repo, endpoint)
    if not isinstance(result, dict):
        raise Blocked("invalid GitHub object response")
    return result


def github_list(repo: str, endpoint: str) -> list:
    result = github_data(repo, endpoint)
    if not isinstance(result, list):
        raise Blocked("invalid GitHub list response")
    return result


def remote_sha(checkout: Path, ref: str) -> str | None:
    result = run(["git", "ls-remote", "--exit-code", "origin", ref], checkout, check=False)
    if result.returncode == 2 and not result.stdout:
        return None
    if result.returncode or len(result.stdout.splitlines()) != 1:
        raise Blocked("remote ref cannot be proven exactly")
    sha, advertised = result.stdout.strip().split("\t", 1)
    if advertised != ref or not SHA.fullmatch(sha):
        raise Blocked("remote ref identity mismatch")
    return sha


def worktree_for(checkout: Path, workspaces: Path, task_id: str, branch: str, head: str) -> Path:
    output = run(["git", "worktree", "list", "--porcelain"], checkout).stdout
    matches: list[Path] = []
    for block in output.strip().split("\n\n"):
        fields = dict(line.split(" ", 1) for line in block.splitlines() if " " in line)
        if fields.get("branch") == f"refs/heads/{branch}":
            matches.append(Path(fields.get("worktree", "")))
            if fields.get("HEAD") != head:
                raise Blocked("local task branch moved")
    if len(matches) != 1:
        raise Blocked("task branch must have exactly one dedicated worktree")
    path = matches[0]
    if path.is_symlink() or not path.is_dir() or path.parent != workspaces or path.name != task_id.replace(".", "-"):
        raise Blocked("task worktree is outside the registered dedicated path")
    if run(["git", "status", "--porcelain"], path).stdout:
        raise Blocked("task worktree is dirty")
    return path


def verify(
    state: dict, entry: dict, registration: dict, *, require_remote: bool, require_worktree: bool = True
) -> tuple[Path | None, str | None]:
    checkout = Path(entry["path"])
    repo = github_name(entry["remote"])
    pr = github_json(repo, f"pulls/{state['pr_number']}")
    if not pr.get("merged") or pr.get("state") != "closed":
        raise Blocked("pull request is not merged")
    if (pr.get("head") or {}).get("ref") != state["branch"] or (pr.get("head") or {}).get("sha") != state["head"]:
        raise Blocked("pull request task head changed")
    if (pr.get("head") or {}).get("repo", {}).get("full_name") != repo:
        raise Blocked("pull request head repository mismatch")
    if (pr.get("base") or {}).get("ref") != state.get("pr_base", state["default"]) or pr.get("merge_commit_sha") != state["merge"]:
        raise Blocked("pull request base or merge identity mismatch")
    repository = github_json(repo, "")
    if repository.get("default_branch") != state["default"]:
        raise Blocked("repository default branch changed")
    default_ref = f"refs/heads/{state['default']}"
    task_ref = f"refs/heads/{state['branch']}"
    default_sha = remote_sha(checkout, default_ref)
    task_sha = remote_sha(checkout, task_ref)
    if not default_sha or (require_remote and task_sha != state["head"]):
        raise Blocked("default or task remote ref mismatch")
    if task_sha is not None and task_sha != state["head"]:
        raise Blocked("task remote ref moved")
    if task_sha is not None:
        branch_info = github_json(repo, f"branches/{quote(state['branch'], safe='')}")
        if branch_info.get("protected") is not False:
            raise Blocked("task branch is protected or protection is unknown")
        branch_sha = branch_info.get("sha") if SUPERVISED_EVIDENCE is not None else (branch_info.get("commit") or {}).get("sha")
        if branch_sha != state["head"]:
            raise Blocked("GitHub branch head differs from the recorded task head")
        owner = repo.split("/", 1)[0]
        head_filter = quote(f"{owner}:{state['branch']}", safe="")
        if github_list(repo, f"pulls?state=open&head={head_filter}&per_page=100"):
            raise Blocked("task branch is shared with an open pull request")
    run(["git", "fetch", "--no-tags", "origin", default_ref], checkout)
    if run(["git", "rev-parse", "FETCH_HEAD"], checkout).stdout.strip() != default_sha:
        raise Blocked("default ref moved during refresh")
    if run(["git", "merge-base", "--is-ancestor", state["head"], default_sha], checkout, check=False).returncode:
        raise Blocked("task head is not an ancestor of the default ref")
    if run(["git", "merge-base", "--is-ancestor", state["merge"], default_sha], checkout, check=False).returncode:
        raise Blocked("recorded merge is not on the default ref")
    parents = run(["git", "show", "-s", "--format=%P", state["merge"]], checkout).stdout.strip().split()
    if len(parents) != 2 or parents[1] != state["head"]:
        raise Blocked("squash, rebase, or ambiguous merge outcome")
    path = None
    if require_worktree:
        workspaces = Path(registration["workspace_root"]) / state["repository_id"]
        path = worktree_for(checkout, workspaces, state["task_id"], state["branch"], state["head"])
        if str(path) != state["worktree"]:
            raise Blocked("dedicated worktree identity changed")
    return path, task_sha


def state_paths(repository_id: str, task_id: str) -> tuple[Path, Path]:
    directory = STATE_ROOT / repository_id
    if STATE_ROOT.is_symlink() or not STATE_ROOT.is_dir() or STATE_ROOT.stat().st_uid != os.getuid():
        raise Blocked("trusted state root is absent or has the wrong owner")
    if STATE_ROOT.stat().st_mode & 0o077:
        raise Blocked("trusted state root must be private")
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077:
        raise Blocked("task state directory is not private")
    return directory / f"{task_id}.json", directory / f"{task_id}.lock"


def persist(path: Path, state: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(state, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise Blocked("lifecycle evidence is missing or untrusted")
    result = json.loads(path.read_text())
    if not isinstance(result, dict):
        raise Blocked("invalid lifecycle evidence")
    return result


def process(task_id: str, repository_id: str, pr_number: int) -> dict:
    if not TASK_ID.fullmatch(task_id) or not REPOSITORY_ID.fullmatch(repository_id) or pr_number < 1:
        raise Blocked("invalid task, repository, or pull request identity")
    registration, entry, _ = repository_config(repository_id)
    state_file, lock_file = state_paths(repository_id, task_id)
    with lock_file.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        repo = github_name(entry["remote"])
        if state_file.exists():
            state = load(state_file)
            if (state.get("task_id"), state.get("repository_id"), state.get("pr_number")) != (task_id, repository_id, pr_number):
                raise Blocked("requested task differs from durable evidence")
        else:
            pr = github_json(repo, f"pulls/{pr_number}")
            branch = (pr.get("head") or {}).get("ref", "")
            head = (pr.get("head") or {}).get("sha", "")
            merge = pr.get("merge_commit_sha", "")
            default = entry.get("default_branch", "")
            pr_base = (pr.get("base") or {}).get("ref", "")
            task_slug = task_id.replace(".", "-")
            if (not branch.startswith(f"codex/{task_slug}-")
                    or run(["git", "check-ref-format", "--branch", branch], Path(entry["path"]), check=False).returncode
                    or not isinstance(pr_base, str)
                    or run(["git", "check-ref-format", "--branch", pr_base], Path(entry["path"]), check=False).returncode
                    or not SHA.fullmatch(head) or not SHA.fullmatch(merge)):
                raise Blocked("pull request does not identify an exact task head")
            workspaces = Path(registration["workspace_root"]) / repository_id
            worktree = worktree_for(Path(entry["path"]), workspaces, task_id, branch, head)
            state = {"task_id": task_id, "repository_id": repository_id, "pr_number": pr_number,
                     "branch": branch, "head": head, "merge": merge, "default": default,
                     "pr_base": pr_base,
                     "worktree": str(worktree), "remote_delete": "pending",
                     "worktree_remove": "pending", "local_branch_delete": "pending"}
            verify(state, entry, registration, require_remote=True)
            persist(state_file, state)
        phase = state["remote_delete"]
        if phase == "completed":
            verify(state, entry, registration, require_remote=False,
                   require_worktree=state.get("worktree_remove") != "completed")
            if remote_sha(Path(entry["path"]), f"refs/heads/{state['branch']}") is not None:
                raise Blocked("completed deletion has a recreated remote ref")
            return state
        if phase == "pending":
            verify(state, entry, registration, require_remote=True)
            state["remote_delete"] = "executing"
            persist(state_file, state)
        elif phase != "executing":
            raise Blocked("invalid remote deletion state")
        _, task_sha = verify(state, entry, registration, require_remote=False)
        if task_sha is None:
            state["remote_delete"] = "completed"
            persist(state_file, state)
            return state
        checkout = Path(entry["path"])
        task_ref = f"refs/heads/{state['branch']}"
        run(["git", "push", f"--force-with-lease={task_ref}:{state['head']}", "origin", f":{task_ref}"], checkout)
        if remote_sha(checkout, task_ref) is not None:
            raise Blocked("remote task ref still exists after leased deletion")
        state["remote_delete"] = "completed"
        persist(state_file, state)
        return state


def local_ref_sha(checkout: Path, branch: str) -> str | None:
    ref = f"refs/heads/{branch}"
    present = run(["git", "show-ref", "--verify", "--quiet", ref], checkout, check=False)
    if present.returncode == 1:
        return None
    if present.returncode:
        raise Blocked("local branch presence cannot be proven")
    result = run(["git", "rev-parse", "--verify", ref], checkout)
    if not SHA.fullmatch(result.stdout.strip()):
        raise Blocked("local branch cannot be proven exactly")
    return result.stdout.strip()


def worktree_absent(checkout: Path, state: dict) -> bool:
    path = Path(state["worktree"])
    output = run(["git", "worktree", "list", "--porcelain"], checkout).stdout
    return (not path.exists() and not path.is_symlink()
            and f"worktree {path}\n" not in output
            and f"branch refs/heads/{state['branch']}\n" not in output)


def cleanup_local(task_id: str, repository_id: str, pr_number: int, delivery_evidence: str) -> dict:
    if not TASK_ID.fullmatch(task_id) or not REPOSITORY_ID.fullmatch(repository_id) or pr_number < 1:
        raise Blocked("invalid task, repository, or pull request identity")
    if len(delivery_evidence.strip()) < 12 or len(delivery_evidence) > 500:
        raise Blocked("Oracle delivery evidence is required")
    registration, entry, _ = repository_config(repository_id)
    state_file, lock_file = state_paths(repository_id, task_id)
    checkout = Path(entry["path"])
    with lock_file.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load(state_file)
        if (state.get("task_id"), state.get("repository_id"), state.get("pr_number")) != (task_id, repository_id, pr_number):
            raise Blocked("requested task differs from durable evidence")
        if state.get("remote_delete") != "completed":
            raise Blocked("remote task-ref deletion is not durably complete")
        if remote_sha(checkout, f"refs/heads/{state['branch']}") is not None:
            raise Blocked("remote task ref exists again")
        if "delivery_evidence" not in state:
            state["delivery_evidence"] = delivery_evidence.strip()
            persist(state_file, state)
        elif state["delivery_evidence"] != delivery_evidence.strip():
            raise Blocked("delivery evidence changed during recovery")
        worktree_phase = state.get("worktree_remove", "pending")
        if worktree_phase == "pending":
            verify(state, entry, registration, require_remote=False)
            state["worktree_remove"] = "executing"
            persist(state_file, state)
            worktree_phase = "executing"
        if worktree_phase == "executing":
            verify(state, entry, registration, require_remote=False, require_worktree=False)
            if not worktree_absent(checkout, state):
                verify(state, entry, registration, require_remote=False)
                run(["git", "worktree", "remove", "--", state["worktree"]], checkout)
            if not worktree_absent(checkout, state):
                raise Blocked("dedicated worktree still exists")
            state["worktree_remove"] = "completed"
            persist(state_file, state)
        elif worktree_phase != "completed":
            raise Blocked("invalid worktree cleanup state")
        if not worktree_absent(checkout, state):
            raise Blocked("completed worktree cleanup has reappeared")
        branch_phase = state.get("local_branch_delete", "pending")
        if branch_phase == "pending":
            verify(state, entry, registration, require_remote=False, require_worktree=False)
            if local_ref_sha(checkout, state["branch"]) != state["head"]:
                raise Blocked("local task branch moved or disappeared")
            state["local_branch_delete"] = "executing"
            persist(state_file, state)
            branch_phase = "executing"
        if branch_phase == "executing":
            verify(state, entry, registration, require_remote=False, require_worktree=False)
            local_sha = local_ref_sha(checkout, state["branch"])
            if local_sha is not None:
                if local_sha != state["head"]:
                    raise Blocked("local task branch moved")
                run(["git", "branch", "-d", "--", state["branch"]], checkout)
            if local_ref_sha(checkout, state["branch"]) is not None:
                raise Blocked("local task branch still exists")
            state["local_branch_delete"] = "completed"
            persist(state_file, state)
        elif branch_phase != "completed":
            raise Blocked("invalid local branch cleanup state")
        if local_ref_sha(checkout, state["branch"]) is not None:
            raise Blocked("completed local branch has reappeared")
        return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["remote-delete", "local-cleanup"])
    parser.add_argument("task_id")
    parser.add_argument("repository_id")
    parser.add_argument("pr_number", type=int)
    parser.add_argument("--delivery-evidence")
    parser.add_argument("--supervised-evidence", type=Path)
    args = parser.parse_args()
    try:
        if args.supervised_evidence is not None:
            global SUPERVISED_EVIDENCE, STATE_ROOT
            source = Path(__file__).absolute()
            canonical_source = Path("/srv/software-factory/repos/software-factory/scripts/merged_branch_lifecycle.py")
            if source != canonical_source or source.is_symlink() or source.parent.is_symlink():
                raise Blocked("supervised runner must use the canonical factory checkout")
            factory = canonical_source.parents[1]
            if run(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], factory).stdout.strip() != "main":
                raise Blocked("supervised runner requires factory main")
            if run(["git", "status", "--porcelain", "--", "scripts/merged_branch_lifecycle.py"], factory).stdout:
                raise Blocked("supervised runner source is modified")
            SUPERVISED_EVIDENCE = load_supervised_evidence(
                args.supervised_evidence, args.task_id, args.repository_id, args.pr_number)
            STATE_ROOT = SUPERVISED_ROOT
        else:
            installed = Path(__file__).resolve()
            trusted_root = Path("/usr/local/lib/software-factory")
            if (installed.parent != trusted_root or installed.is_symlink() or installed.stat().st_uid != 0
                    or installed.stat().st_mode & 0o022 or trusted_root.is_symlink()
                    or trusted_root.stat().st_uid != 0 or trusted_root.stat().st_mode & 0o022):
                raise Blocked("runner must be installed root-owned outside model-writable paths")
        if args.phase == "remote-delete":
            if args.delivery_evidence is not None:
                raise Blocked("delivery evidence belongs only to local cleanup")
            state = process(args.task_id, args.repository_id, args.pr_number)
        else:
            state = cleanup_local(args.task_id, args.repository_id, args.pr_number, args.delivery_evidence or "")
    except (Blocked, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"blocked: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"task_id": state["task_id"], "remote_delete": state["remote_delete"],
                      "worktree_remove": state["worktree_remove"],
                      "local_branch_delete": state["local_branch_delete"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
