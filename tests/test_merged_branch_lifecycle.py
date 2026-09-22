"""Exercise real Git refs and worktrees in disposable repositories."""

from __future__ import annotations

from contextlib import contextmanager, ExitStack
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "merged_branch_lifecycle.py"
spec = importlib.util.spec_from_file_location("merged_branch_lifecycle", SCRIPT)
assert spec and spec.loader
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()


class LifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bare = self.root / "remote.git"
        self.repo = self.root / "repo"
        self.workspaces = self.root / "worktrees"
        self.task = "issue-14"
        self.repository_id = "demo"
        self.worktree = self.workspaces / self.repository_id / self.task
        self.state_root = self.root / "state"
        self.state_root.mkdir(mode=0o700)
        git(self.root, "init", "--bare", "--initial-branch=main", str(self.bare))
        git(self.root, "clone", str(self.bare), str(self.repo))
        git(self.repo, "config", "user.name", "Fixture")
        git(self.repo, "config", "user.email", "fixture@example.test")
        (self.repo / "base.txt").write_text("base\n")
        git(self.repo, "add", "base.txt")
        git(self.repo, "commit", "-m", "base")
        git(self.repo, "push", "origin", "main")
        self.worktree.parent.mkdir(parents=True)
        git(self.repo, "worktree", "add", "-b", f"codex/{self.task}-work", str(self.worktree), "main")
        (self.worktree / "task.txt").write_text("task\n")
        git(self.worktree, "add", "task.txt")
        git(self.worktree, "commit", "-m", "task")
        self.head = git(self.worktree, "rev-parse", "HEAD")
        git(self.worktree, "push", "origin", "HEAD:refs/heads/codex/issue-14-work")
        git(self.repo, "merge", "--no-ff", "-m", "Merge pull request #7", f"codex/{self.task}-work")
        self.merge = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "push", "origin", "main")
        self.registration = {"workspace_root": str(self.workspaces)}
        self.entry = {"path": str(self.repo), "remote": "git@github.com:Floris/demo.git", "default_branch": "main"}
        self.fake_pr = {
            "state": "closed", "merged": True, "merge_commit_sha": self.merge,
            "head": {"ref": f"codex/{self.task}-work", "sha": self.head,
                     "repo": {"full_name": "Floris/demo"}},
            "base": {"ref": "main"},
        }

    def api(self, repo: str, endpoint: str) -> dict:
        self.assertEqual(repo, "Floris/demo")
        if endpoint == "pulls/7":
            return self.fake_pr
        if endpoint == "":
            return {"default_branch": "main"}
        if endpoint.startswith("branches/"):
            return {"protected": False, "commit": {"sha": self.head}}
        raise AssertionError(endpoint)

    def test_repository_config_does_not_require_beads_store(self) -> None:
        registration = {"version": 2, "repositories": [{
            "id": self.repository_id, "path": str(self.repo),
            "remote": str(self.bare), "policy": "demo",
            "credential_refs": {"git_read": "read", "git_write": "write"},
        }]}
        policies = {"policies": {"demo": {
            "lifecycle": {"delete_merged_remote_branch": True},
            "git": {"delete_branch": False},
        }}}
        with patch.object(lifecycle, "root_yaml", side_effect=[registration, policies]):
            observed, entry, policy = lifecycle.repository_config(self.repository_id)
        self.assertEqual(observed, registration)
        self.assertEqual(entry["id"], self.repository_id)
        self.assertTrue(policy["lifecycle"]["delete_merged_remote_branch"])

    def test_registered_underscore_repository_id_reaches_config_lookup(self) -> None:
        with patch.object(lifecycle, "repository_config", side_effect=RuntimeError("lookup reached")):
            with self.assertRaisesRegex(RuntimeError, "lookup reached"):
                lifecycle.process(self.task, "droppert_dev", 7)

        for repository_id in ("../outside", "bad/repo", "bad.repo", "bad repo"):
            with self.subTest(repository_id=repository_id):
                with self.assertRaisesRegex(lifecycle.Blocked, "invalid task"):
                    lifecycle.process(self.task, repository_id, 7)

    def connector_evidence(self) -> dict:
        return {
            "version": 1, "repo": "Floris/demo", "task_id": self.task,
            "repository_id": self.repository_id, "pr_number": 7,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "pull_request": {
                "number": 7, "state": "closed", "merged": True,
                "head": f"codex/{self.task}-work", "head_sha": self.head,
                "head_repo_full_name": "Floris/demo", "base": "main",
                "merge_commit_sha": self.merge,
            },
            "default_branch": "main", "open_pull_requests": [],
            "branch_info": {"name": f"codex/{self.task}-work", "sha": self.head,
                            "protected": False},
        }

    def write_evidence(self, evidence: dict) -> Path:
        directory = self.root / "connector-evidence"
        directory.mkdir(mode=0o700, exist_ok=True)
        path = directory / "issue-14.json"
        path.write_text(json.dumps(evidence))
        path.chmod(0o600)
        return path

    @contextmanager
    def patches(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(lifecycle, "STATE_ROOT", self.state_root))
            stack.enter_context(patch.object(lifecycle, "repository_config",
                                             return_value=(self.registration, self.entry, {})))
            stack.enter_context(patch.object(lifecycle, "github_name", return_value="Floris/demo"))
            stack.enter_context(patch.object(lifecycle, "github_json", side_effect=self.api))
            stack.enter_context(patch.object(lifecycle, "github_list", return_value=[]))
            yield

    def test_true_merge_deletes_only_exact_remote_ref_and_is_idempotent(self) -> None:
        with self.patches():
            result = lifecycle.process(self.task, self.repository_id, 7)
            self.assertEqual(result["remote_delete"], "completed")
            self.assertIsNone(lifecycle.remote_sha(self.repo, "refs/heads/codex/issue-14-work"))
            self.assertEqual(lifecycle.remote_sha(self.repo, "refs/heads/main"), self.merge)
            self.assertTrue(self.worktree.is_dir())
            self.assertEqual(lifecycle.process(self.task, self.repository_id, 7)["remote_delete"], "completed")

    def test_local_cleanup_requires_remote_evidence_and_removes_exact_resources(self) -> None:
        with self.patches():
            lifecycle.process(self.task, self.repository_id, 7)
            result = lifecycle.cleanup_local(self.task, self.repository_id, 7, "Merged code verified by Oracle")
            self.assertEqual(result["worktree_remove"], "completed")
            self.assertEqual(result["local_branch_delete"], "completed")
            self.assertFalse(self.worktree.exists())
            self.assertIsNone(lifecycle.local_ref_sha(self.repo, "codex/issue-14-work"))
            self.assertEqual(lifecycle.process(self.task, self.repository_id, 7)["remote_delete"], "completed")
            self.assertEqual(lifecycle.cleanup_local(self.task, self.repository_id, 7,
                                                     "Merged code verified by Oracle")["local_branch_delete"], "completed")

    def test_legacy_suffix_worktree_is_cleaned_by_exact_branch_identity(self) -> None:
        legacy_path = self.worktree.with_name(f"{self.task}-hotfix")
        git(self.repo, "worktree", "move", str(self.worktree), str(legacy_path))
        self.worktree = legacy_path
        with self.patches():
            state = lifecycle.process(self.task, self.repository_id, 7)
            self.assertEqual(state["worktree"], str(legacy_path))
            self.assertEqual(state["local_head"], self.head)
            state = lifecycle.cleanup_local(self.task, self.repository_id, 7,
                                            "Merged code verified by Oracle")
            self.assertEqual(state["local_branch_delete"], "completed")
        self.assertFalse(legacy_path.exists())

    def test_legacy_local_branch_at_exact_merge_is_cleaned(self) -> None:
        git(self.worktree, "reset", "--hard", self.merge)
        with self.patches():
            state = lifecycle.process(self.task, self.repository_id, 7)
            self.assertEqual(state["head"], self.head)
            self.assertEqual(state["local_head"], self.merge)
            self.assertEqual(state["remote_delete"], "completed")
            state = lifecycle.cleanup_local(self.task, self.repository_id, 7,
                                            "Merged code verified by Oracle")
            self.assertEqual(state["local_branch_delete"], "completed")

    def test_legacy_identity_rejects_other_path_or_local_commit(self) -> None:
        other_path = self.worktree.with_name("unrelated-worktree")
        git(self.repo, "worktree", "move", str(self.worktree), str(other_path))
        with self.patches():
            with self.assertRaisesRegex(lifecycle.Blocked, "dedicated path"):
                lifecycle.process(self.task, self.repository_id, 7)
        git(self.repo, "worktree", "move", str(other_path), str(self.worktree))
        git(self.worktree, "commit", "--allow-empty", "-m", "unmerged local change")
        with self.patches():
            with self.assertRaisesRegex(lifecycle.Blocked, "local task branch moved"):
                lifecycle.process(self.task, self.repository_id, 7)
        self.assertEqual(lifecycle.remote_sha(self.repo, "refs/heads/codex/issue-14-work"), self.head)

    def test_local_head_must_stay_fixed_after_remote_deletion(self) -> None:
        with self.patches():
            lifecycle.process(self.task, self.repository_id, 7)
            git(self.worktree, "reset", "--hard", self.merge)
            with self.assertRaisesRegex(lifecycle.Blocked, "local task branch moved"):
                lifecycle.cleanup_local(self.task, self.repository_id, 7,
                                        "Merged code verified by Oracle")
            self.assertTrue(self.worktree.exists())

    def test_dirty_worktree_blocks_local_cleanup(self) -> None:
        with self.patches():
            lifecycle.process(self.task, self.repository_id, 7)
            (self.worktree / "untracked.txt").write_text("keep me\n")
            with self.assertRaisesRegex(lifecycle.Blocked, "dirty"):
                lifecycle.cleanup_local(self.task, self.repository_id, 7, "Merged code verified by Oracle")
            self.assertTrue(self.worktree.exists())
            self.assertEqual(lifecycle.local_ref_sha(self.repo, "codex/issue-14-work"), self.head)

    def test_local_cleanup_rejects_missing_remote_deletion_evidence(self) -> None:
        with self.patches():
            state_file, _ = lifecycle.state_paths(self.repository_id, self.task)
            lifecycle.persist(state_file, {"task_id": self.task, "repository_id": self.repository_id,
                                           "pr_number": 7, "remote_delete": "pending"})
            with self.assertRaisesRegex(lifecycle.Blocked, "not durably complete"):
                lifecycle.cleanup_local(self.task, self.repository_id, 7, "Merged code verified by Oracle")
            self.assertTrue(self.worktree.exists())

    def test_executing_local_cleanup_recovers_exact_absence(self) -> None:
        with self.patches():
            state = lifecycle.process(self.task, self.repository_id, 7)
            state["worktree_remove"] = "executing"
            state["delivery_evidence"] = "Merged code verified by Oracle"
            state_file, _ = lifecycle.state_paths(self.repository_id, self.task)
            lifecycle.persist(state_file, state)
            git(self.repo, "worktree", "remove", "--", str(self.worktree))
            result = lifecycle.cleanup_local(self.task, self.repository_id, 7, "Merged code verified by Oracle")
            self.assertEqual(result["worktree_remove"], "completed")
            self.assertEqual(result["local_branch_delete"], "completed")

    def test_rebase_or_squash_style_merge_is_rejected(self) -> None:
        self.fake_pr["merge_commit_sha"] = self.head
        with self.patches():
            with self.assertRaisesRegex(lifecycle.Blocked, "squash, rebase"):
                lifecycle.process(self.task, self.repository_id, 7)
            self.assertEqual(lifecycle.remote_sha(self.repo, "refs/heads/codex/issue-14-work"), self.head)

    def test_moved_remote_head_is_rejected(self) -> None:
        git(self.worktree, "push", "origin", "HEAD:refs/heads/other")
        git(self.repo, "push", "origin", ":refs/heads/codex/issue-14-work")
        with self.patches():
            with self.assertRaisesRegex(lifecycle.Blocked, "remote ref mismatch"):
                lifecycle.process(self.task, self.repository_id, 7)

    def test_branch_shared_with_open_pr_is_rejected(self) -> None:
        with self.patches(), patch.object(lifecycle, "github_list", return_value=[{"number": 8}]):
            with self.assertRaisesRegex(lifecycle.Blocked, "shared"):
                lifecycle.process(self.task, self.repository_id, 7)
            self.assertEqual(lifecycle.remote_sha(self.repo, "refs/heads/codex/issue-14-work"), self.head)

    def test_executing_state_recovers_only_exact_absence(self) -> None:
        with self.patches():
            state_file, _ = lifecycle.state_paths(self.repository_id, self.task)
            state = {
                "task_id": self.task, "repository_id": self.repository_id, "pr_number": 7,
                "branch": "codex/issue-14-work", "head": self.head, "merge": self.merge,
                "default": "main", "worktree": str(self.worktree),
                "remote_delete": "executing", "local_cleanup": "pending",
            }
            lifecycle.persist(state_file, state)
            git(self.repo, "push", "origin", ":refs/heads/codex/issue-14-work")
            self.assertEqual(lifecycle.process(self.task, self.repository_id, 7)["remote_delete"], "completed")

    def test_missing_lifecycle_policy_fails_before_remote_access(self) -> None:
        with patch.object(lifecycle, "repository_config", side_effect=lifecycle.Blocked("policy denied")):
            with self.assertRaisesRegex(lifecycle.Blocked, "policy denied"):
                lifecycle.process(self.task, self.repository_id, 7)
        self.assertEqual(lifecycle.remote_sha(self.repo, "refs/heads/codex/issue-14-work"), self.head)

    def test_supervised_connector_evidence_runs_exact_merge_checks(self) -> None:
        path = self.write_evidence(self.connector_evidence())
        with patch.object(lifecycle, "EVIDENCE_ROOT", path.parent):
            evidence = lifecycle.load_supervised_evidence(path, self.task, self.repository_id, 7)
        with ExitStack() as stack:
            stack.enter_context(patch.object(lifecycle, "SUPERVISED_EVIDENCE", evidence))
            stack.enter_context(patch.object(lifecycle, "STATE_ROOT", self.state_root))
            stack.enter_context(patch.object(lifecycle, "repository_config",
                                             return_value=(self.registration, self.entry, {})))
            stack.enter_context(patch.object(lifecycle, "github_name", return_value="Floris/demo"))
            result = lifecycle.process(self.task, self.repository_id, 7)
        self.assertEqual(result["remote_delete"], "completed")
        self.assertIsNone(lifecycle.remote_sha(self.repo, "refs/heads/codex/issue-14-work"))

    def test_historical_pr_base_can_be_contained_in_current_default(self) -> None:
        evidence = self.connector_evidence()
        evidence["pull_request"]["base"] = "master"
        path = self.write_evidence(evidence)
        with patch.object(lifecycle, "EVIDENCE_ROOT", path.parent):
            loaded = lifecycle.load_supervised_evidence(path, self.task, self.repository_id, 7)
        with ExitStack() as stack:
            stack.enter_context(patch.object(lifecycle, "SUPERVISED_EVIDENCE", loaded))
            stack.enter_context(patch.object(lifecycle, "STATE_ROOT", self.state_root))
            stack.enter_context(patch.object(lifecycle, "repository_config",
                                             return_value=(self.registration, self.entry, {})))
            stack.enter_context(patch.object(lifecycle, "github_name", return_value="Floris/demo"))
            result = lifecycle.process(self.task, self.repository_id, 7)
        self.assertEqual(result["pr_base"], "master")
        self.assertEqual(result["default"], "main")
        self.assertEqual(result["remote_delete"], "completed")

    def test_supervised_evidence_rejects_stale_and_shared_head(self) -> None:
        evidence = self.connector_evidence()
        evidence["observed_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        path = self.write_evidence(evidence)
        with patch.object(lifecycle, "EVIDENCE_ROOT", path.parent):
            with self.assertRaisesRegex(lifecycle.Blocked, "stale"):
                lifecycle.load_supervised_evidence(path, self.task, self.repository_id, 7)
            evidence["observed_at"] = datetime.now(timezone.utc).isoformat()
            evidence["open_pull_requests"] = [{"number": 8}]
            path = self.write_evidence(evidence)
            with self.assertRaisesRegex(lifecycle.Blocked, "unshared"):
                lifecycle.load_supervised_evidence(path, self.task, self.repository_id, 7)

    def test_supervised_evidence_rejects_wrong_identity_and_permissions(self) -> None:
        evidence = self.connector_evidence()
        evidence["pull_request"]["head_sha"] = "0" * 40
        evidence["branch_info"]["sha"] = "0" * 40
        path = self.write_evidence(evidence)
        with patch.object(lifecycle, "EVIDENCE_ROOT", path.parent):
            with self.assertRaisesRegex(lifecycle.Blocked, "private"):
                path.chmod(0o644)
                lifecycle.load_supervised_evidence(path, self.task, self.repository_id, 7)
            path.chmod(0o600)
            with self.assertRaisesRegex(lifecycle.Blocked, "task identity"):
                lifecycle.load_supervised_evidence(path, self.task, self.repository_id, 8)
            with ExitStack() as stack:
                stack.enter_context(patch.object(lifecycle, "SUPERVISED_EVIDENCE", lifecycle.load_supervised_evidence(
                    path, self.task, self.repository_id, 7)))
                stack.enter_context(patch.object(lifecycle, "STATE_ROOT", self.state_root))
                stack.enter_context(patch.object(lifecycle, "repository_config",
                                                 return_value=(self.registration, self.entry, {})))
                stack.enter_context(patch.object(lifecycle, "github_name", return_value="Floris/demo"))
                with self.assertRaisesRegex(lifecycle.Blocked, "local task branch moved"):
                    lifecycle.process(self.task, self.repository_id, 7)

    def test_supervised_evidence_rejects_protected_branch(self) -> None:
        evidence = self.connector_evidence()
        evidence["branch_info"]["protected"] = True
        path = self.write_evidence(evidence)
        with patch.object(lifecycle, "EVIDENCE_ROOT", path.parent):
            with self.assertRaisesRegex(lifecycle.Blocked, "protected"):
                lifecycle.load_supervised_evidence(path, self.task, self.repository_id, 7)
        self.assertEqual(lifecycle.remote_sha(self.repo, "refs/heads/codex/issue-14-work"), self.head)


if __name__ == "__main__":
    unittest.main()
