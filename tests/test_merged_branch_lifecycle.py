"""Exercise real Git refs and worktrees in disposable repositories."""

from __future__ import annotations

from contextlib import contextmanager, ExitStack
import importlib.util
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
        self.task = "sf-test"
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
        git(self.worktree, "push", "origin", "HEAD:refs/heads/codex/sf-test-work")
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
            return {"protected": False}
        raise AssertionError(endpoint)

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
            self.assertIsNone(lifecycle.remote_sha(self.repo, "refs/heads/codex/sf-test-work"))
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
            self.assertIsNone(lifecycle.local_ref_sha(self.repo, "codex/sf-test-work"))
            self.assertEqual(lifecycle.process(self.task, self.repository_id, 7)["remote_delete"], "completed")
            self.assertEqual(lifecycle.cleanup_local(self.task, self.repository_id, 7,
                                                     "Merged code verified by Oracle")["local_branch_delete"], "completed")

    def test_dirty_worktree_blocks_local_cleanup(self) -> None:
        with self.patches():
            lifecycle.process(self.task, self.repository_id, 7)
            (self.worktree / "untracked.txt").write_text("keep me\n")
            with self.assertRaisesRegex(lifecycle.Blocked, "dirty"):
                lifecycle.cleanup_local(self.task, self.repository_id, 7, "Merged code verified by Oracle")
            self.assertTrue(self.worktree.exists())
            self.assertEqual(lifecycle.local_ref_sha(self.repo, "codex/sf-test-work"), self.head)

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
            self.assertEqual(lifecycle.remote_sha(self.repo, "refs/heads/codex/sf-test-work"), self.head)

    def test_moved_remote_head_is_rejected(self) -> None:
        git(self.worktree, "push", "origin", "HEAD:refs/heads/other")
        git(self.repo, "push", "origin", ":refs/heads/codex/sf-test-work")
        with self.patches():
            with self.assertRaisesRegex(lifecycle.Blocked, "remote ref mismatch"):
                lifecycle.process(self.task, self.repository_id, 7)

    def test_branch_shared_with_open_pr_is_rejected(self) -> None:
        with self.patches(), patch.object(lifecycle, "github_list", return_value=[{"number": 8}]):
            with self.assertRaisesRegex(lifecycle.Blocked, "shared"):
                lifecycle.process(self.task, self.repository_id, 7)
            self.assertEqual(lifecycle.remote_sha(self.repo, "refs/heads/codex/sf-test-work"), self.head)

    def test_executing_state_recovers_only_exact_absence(self) -> None:
        with self.patches():
            state_file, _ = lifecycle.state_paths(self.repository_id, self.task)
            state = {
                "task_id": self.task, "repository_id": self.repository_id, "pr_number": 7,
                "branch": "codex/sf-test-work", "head": self.head, "merge": self.merge,
                "default": "main", "worktree": str(self.worktree),
                "remote_delete": "executing", "local_cleanup": "pending",
            }
            lifecycle.persist(state_file, state)
            git(self.repo, "push", "origin", ":refs/heads/codex/sf-test-work")
            self.assertEqual(lifecycle.process(self.task, self.repository_id, 7)["remote_delete"], "completed")

    def test_missing_lifecycle_policy_fails_before_remote_access(self) -> None:
        with patch.object(lifecycle, "repository_config", side_effect=lifecycle.Blocked("policy denied")):
            with self.assertRaisesRegex(lifecycle.Blocked, "policy denied"):
                lifecycle.process(self.task, self.repository_id, 7)
        self.assertEqual(lifecycle.remote_sha(self.repo, "refs/heads/codex/sf-test-work"), self.head)


if __name__ == "__main__":
    unittest.main()
