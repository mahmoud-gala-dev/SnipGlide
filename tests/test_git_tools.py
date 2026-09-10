"""Unit tests for GitService and Git models."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest

from snipglide.services.git_service import GitService
from snipglide.models.git_info import GitRepoInfo, GitCommit


class TestGitService(unittest.TestCase):
    """Test suite for GitService using a temporary Git repository."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="snipglide_git_test_")
        self.service = GitService()

        # Check if git is available
        if not self.service.is_git_available():
            self.skipTest("Git executable not available in environment.")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run_cmd(self, args, cwd=None):
        cwd = cwd or self.temp_dir
        return subprocess.run(
            ["git"] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            check=True,
        )

    def test_not_a_git_repo(self):
        self.assertFalse(self.service.is_git_repo(self.temp_dir))
        info = self.service.get_repo_info(self.temp_dir)
        self.assertFalse(info.is_repo)
        self.assertIn("Not a Git repository", info.error_message or "")

    def test_git_init_and_empty_repo(self):
        self._run_cmd(["init", "-b", "main"])
        self.assertTrue(self.service.is_git_repo(self.temp_dir))

        info = self.service.get_repo_info(self.temp_dir)
        self.assertTrue(info.is_repo)
        self.assertIn("main", info.current_branch)
        self.assertTrue(info.is_clean)
        self.assertEqual(len(info.staged_files), 0)
        self.assertEqual(len(info.modified_files), 0)

    def test_status_untracked_staged_modified(self):
        self._run_cmd(["init", "-b", "main"])
        self._run_cmd(["config", "user.name", "SnipGlide Tester"])
        self._run_cmd(["config", "user.email", "tester@snipglide.local"])

        # 1. Create file1.txt and file2.txt
        f1 = os.path.join(self.temp_dir, "file1.txt")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("Line 1\n")

        f2 = os.path.join(self.temp_dir, "file2.txt")
        with open(f2, "w", encoding="utf-8") as f:
            f.write("Initial file 2\n")

        # Status: 2 untracked
        info = self.service.get_repo_info(self.temp_dir)
        self.assertEqual(len(info.untracked_files), 2)
        self.assertEqual(len(info.staged_files), 0)

        # Stage and commit file1
        self._run_cmd(["add", "file1.txt"])
        self._run_cmd(["commit", "-m", "feat: initial commit"])

        # Modify file1 and stage file2
        with open(f1, "a", encoding="utf-8") as f:
            f.write("Line 2 modified\n")
        self._run_cmd(["add", "file2.txt"])

        info2 = self.service.get_repo_info(self.temp_dir)
        self.assertEqual(len(info2.staged_files), 1)
        self.assertEqual(info2.staged_files[0].path, "file2.txt")
        self.assertEqual(len(info2.modified_files), 1)
        self.assertEqual(info2.modified_files[0].path, "file1.txt")

    def test_recent_commits(self):
        self._run_cmd(["init", "-b", "main"])
        self._run_cmd(["config", "user.name", "SnipGlide Tester"])
        self._run_cmd(["config", "user.email", "tester@snipglide.local"])

        # Commit 1
        f = os.path.join(self.temp_dir, "app.py")
        with open(f, "w", encoding="utf-8") as fp:
            fp.write("print('v1')\n")
        self._run_cmd(["add", "app.py"])
        self._run_cmd(["commit", "-m", "feat(core): initial release"])

        # Commit 2
        with open(f, "a", encoding="utf-8") as fp:
            fp.write("print('v2')\n")
        self._run_cmd(["add", "app.py"])
        self._run_cmd(["commit", "-m", "fix(core): fix syntax issue"])

        commits = self.service.get_recent_commits(self.temp_dir, count=10)
        self.assertEqual(len(commits), 2)
        self.assertEqual(commits[0].message, "fix(core): fix syntax issue")
        self.assertEqual(commits[0].author, "SnipGlide Tester")
        self.assertEqual(commits[1].message, "feat(core): initial release")
        self.assertTrue(len(commits[0].short_hash) >= 4)

    def test_diff_viewer(self):
        self._run_cmd(["init", "-b", "main"])
        self._run_cmd(["config", "user.name", "SnipGlide Tester"])
        self._run_cmd(["config", "user.email", "tester@snipglide.local"])

        f = os.path.join(self.temp_dir, "test_file.py")
        with open(f, "w", encoding="utf-8") as fp:
            fp.write("def foo():\n    return 1\n")
        self._run_cmd(["add", "test_file.py"])
        self._run_cmd(["commit", "-m", "feat: add foo"])

        # Make an unstaged change
        with open(f, "w", encoding="utf-8") as fp:
            fp.write("def foo():\n    return 2\n")

        diff = self.service.get_diff(self.temp_dir, staged=False)
        self.assertIn("-    return 1", diff)
        self.assertIn("+    return 2", diff)

        # Stage the change and check staged diff
        self._run_cmd(["add", "test_file.py"])
        staged_diff = self.service.get_diff(self.temp_dir, staged=True)
        self.assertIn("+    return 2", staged_diff)

    def test_commit_message_heuristic(self):
        # 1. Test fix diff
        fix_diff = """diff --git a/snipglide/services/api.py b/snipglide/services/api.py
--- a/snipglide/services/api.py
+++ b/snipglide/services/api.py
@@ -1,2 +1,2 @@
- fix bug
+ handle edge case
"""
        msg = self.service.generate_commit_message_heuristic(fix_diff)
        self.assertTrue(msg.startswith("fix(api):") or msg.startswith("feat(api):") or "fix" in msg)

        # 2. Test test diff
        test_diff = """diff --git a/tests/test_calc.py b/tests/test_calc.py
new file mode 100644
+++ b/tests/test_calc.py
@@ -0,0 +1,5 @@
+def test_calc(): assert 1 == 1
"""
        msg_test = self.service.generate_commit_message_heuristic(test_diff)
        self.assertTrue(msg_test.startswith("test(tests):") or msg_test.startswith("test:"))


if __name__ == "__main__":
    unittest.main()
