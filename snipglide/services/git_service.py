"""Git service for repository inspection, diff viewing, and commit generation."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import List, Optional, Tuple

from snipglide.models.git_info import GitCommit, GitFileStatus, GitRepoInfo


class GitService:
    """Service to safely interact with local Git repositories using the git CLI."""

    def __init__(self, git_executable: Optional[str] = None):
        self._git_bin = git_executable or shutil.which("git") or "git"

    def is_git_available(self) -> bool:
        """Check if Git CLI is installed and accessible."""
        try:
            res = subprocess.run(
                [self._git_bin, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                timeout=5,
            )
            return res.returncode == 0
        except Exception:
            return False

    def _run_git(
        self,
        args: List[str],
        cwd: str,
        timeout: int = 15,
    ) -> Tuple[int, str, str]:
        """Safely execute git CLI without shell=True."""
        if not self.is_git_available():
            return -1, "", "Git executable not found in PATH."

        try:
            # On Windows, hide the console window when running subprocesses
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            proc = subprocess.run(
                [self._git_bin] + args,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                startupinfo=startupinfo,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -2, "", "Git command timed out."
        except Exception as e:
            return -3, "", str(e)

    def is_git_repo(self, path: str) -> bool:
        """Check whether the given directory is inside a Git working tree."""
        if not path or not os.path.isdir(path):
            return False
        code, stdout, _ = self._run_git(["rev-parse", "--is-inside-work-tree"], cwd=path)
        return code == 0 and stdout.strip() == "true"

    def get_repo_root(self, path: str) -> Optional[str]:
        """Get the root directory of the Git repository."""
        code, stdout, _ = self._run_git(["rev-parse", "--show-toplevel"], cwd=path)
        if code == 0 and stdout.strip():
            return os.path.normpath(stdout.strip())
        return None

    def get_repo_info(self, path: str) -> GitRepoInfo:
        """Collect high-level repository status and changed files."""
        if not path or not os.path.isdir(path):
            return GitRepoInfo(is_repo=False, error_message="Directory does not exist.")

        if not self.is_git_repo(path):
            return GitRepoInfo(is_repo=False, error_message="Not a Git repository.")

        root = self.get_repo_root(path) or path
        info = GitRepoInfo(is_repo=True, root_path=root)

        # 1. Current Branch
        code, stdout, _ = self._run_git(["branch", "--show-current"], cwd=root)
        if code == 0 and stdout.strip():
            info.current_branch = stdout.strip()
        else:
            # Maybe detached HEAD or newly initialized repo without commits
            code_rev, stdout_rev, _ = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
            if code_rev == 0 and stdout_rev.strip():
                branch = stdout_rev.strip()
                if branch == "HEAD":
                    info.is_detached = True
                    info.current_branch = "HEAD (detached)"
                else:
                    info.current_branch = branch
            else:
                info.current_branch = "main (no commits)"

        # 2. Ahead / Behind
        code_up, stdout_up, _ = self._run_git(["rev-parse", "--abbrev-ref", "@{upstream}"], cwd=root)
        if code_up == 0 and stdout_up.strip():
            code_counts, stdout_counts, _ = self._run_git(
                ["rev-list", "--left-right", "--count", "HEAD...@{upstream}"],
                cwd=root,
            )
            if code_counts == 0 and stdout_counts.strip():
                parts = stdout_counts.strip().split()
                if len(parts) >= 2:
                    try:
                        info.ahead = int(parts[0])
                        info.behind = int(parts[1])
                    except ValueError:
                        pass

        # 3. Status Porcelain v1
        code_st, stdout_st, err_st = self._run_git(["status", "--porcelain=v1", "-uall"], cwd=root)
        if code_st != 0:
            info.error_message = err_st.strip() or "Failed to read git status."
            return info

        for line in stdout_st.splitlines():
            if not line or len(line) < 3:
                continue
            index_status = line[0]
            worktree_status = line[1]
            file_entry = line[3:].strip()
            
            # Handle renames: old_name -> new_name
            orig_path = None
            if " -> " in file_entry:
                orig_path, file_entry = file_entry.split(" -> ", 1)

            # Staged changes (index status != ' ' and != '?')
            if index_status not in (" ", "?"):
                info.staged_files.append(
                    GitFileStatus(
                        path=file_entry,
                        status_code=index_status,
                        is_staged=True,
                        original_path=orig_path,
                    )
                )

            # Untracked files (??)
            if index_status == "?" and worktree_status == "?":
                info.untracked_files.append(
                    GitFileStatus(
                        path=file_entry,
                        status_code="??",
                        is_untracked=True,
                    )
                )
            # Unstaged / modified in worktree
            elif worktree_status != " " and worktree_status != "?":
                info.modified_files.append(
                    GitFileStatus(
                        path=file_entry,
                        status_code=worktree_status,
                        is_staged=False,
                    )
                )

        return info

    def get_recent_commits(self, path: str, count: int = 20) -> List[GitCommit]:
        """Fetch the most recent commits formatted safely."""
        if not self.is_git_repo(path):
            return []

        # Use unit separator %x1f between fields to prevent collision with message text
        fmt = "%H%x1f%h%x1f%an%x1f%ad%x1f%s"
        code, stdout, _ = self._run_git(
            ["log", f"-n{max(1, count)}", f"--pretty=format:{fmt}", "--date=iso"],
            cwd=path,
        )
        if code != 0 or not stdout.strip():
            return []

        commits = []
        for line in stdout.splitlines():
            parts = line.split("\x1f")
            if len(parts) >= 5:
                commits.append(
                    GitCommit(
                        hash=parts[0],
                        short_hash=parts[1],
                        author=parts[2],
                        date=parts[3],
                        message=parts[4],
                    )
                )
        return commits

    def get_diff(
        self,
        path: str,
        staged: bool = False,
        file_path: Optional[str] = None,
        max_lines: int = 2000,
    ) -> str:
        """Fetch working tree or staged diff, optionally filtered by file."""
        if not self.is_git_repo(path):
            return "Not a git repository."

        args = ["diff"]
        if staged:
            args.append("--cached")
        if file_path:
            args.extend(["--", file_path])

        code, stdout, stderr = self._run_git(args, cwd=path)
        if code != 0:
            return stderr.strip() or "Failed to load git diff."

        if not stdout.strip():
            return "(No changes detected)"

        lines = stdout.splitlines()
        if len(lines) > max_lines:
            truncated = lines[:max_lines]
            truncated.append(f"\n... [Diff truncated: showing {max_lines} of {len(lines)} lines] ...")
            return "\n".join(truncated)

        return stdout

    def generate_commit_message_heuristic(
        self,
        diff: str,
        status_info: Optional[GitRepoInfo] = None,
    ) -> str:
        """Generate a Conventional Commit message using rule-based heuristics."""
        changed_paths: List[str] = []
        if status_info:
            all_files = status_info.staged_files or (status_info.modified_files + status_info.untracked_files)
            changed_paths = [f.path.lower() for f in all_files]
        else:
            # Extract paths from diff headers: diff --git a/... b/...
            for match in re.finditer(r"diff --git a/(\S+) b/(\S+)", diff):
                changed_paths.append(match.group(2).lower())

        if not changed_paths and (not diff or diff.strip() == "(No changes detected)"):
            return "chore: update repository files"

        # Determine Conventional Commit type & scope
        commit_type = "feat"
        scope = ""
        summary = ""

        # Check file categories
        is_test = any("test" in p for p in changed_paths)
        is_doc = any(p.endswith((".md", ".txt", ".rst")) or "doc" in p for p in changed_paths)
        is_ci = any(".github" in p or "ci" in p or ".gitlab" in p for p in changed_paths)
        is_build = any(p in ("requirements.txt", "pyproject.toml", "setup.py", "package.json") for p in changed_paths)

        # Inspect diff keywords
        diff_lower = diff.lower()
        has_fix = "fix" in diff_lower or "bug" in diff_lower or "issue" in diff_lower or "patch" in diff_lower
        has_refactor = "refactor" in diff_lower or "clean" in diff_lower
        has_perf = "perf" in diff_lower or "optimiz" in diff_lower

        if is_test and len(changed_paths) == 1:
            commit_type = "test"
            scope = "tests"
            summary = "add unit tests and regression assertions"
        elif is_doc and len(changed_paths) <= 2:
            commit_type = "docs"
            scope = "documentation"
            summary = "update documentation and notes"
        elif is_ci:
            commit_type = "ci"
            summary = "update workflow automation configuration"
        elif is_build:
            commit_type = "build"
            summary = "update package dependencies and build configuration"
        elif has_fix:
            commit_type = "fix"
            summary = "resolve edge cases and improve error handling"
        elif has_perf:
            commit_type = "perf"
            summary = "optimize processing performance"
        elif has_refactor:
            commit_type = "refactor"
            summary = "refactor structure for better maintainability"
        else:
            commit_type = "feat"
            summary = "implement new functionality"

        # Guess scope from top-level directory or primary file
        if not scope and changed_paths:
            first_path = changed_paths[0].replace("\\", "/")
            parts = first_path.split("/")
            if len(parts) > 1:
                scope = parts[-2] if parts[-2] != "snipglide" else parts[-1].split(".")[0]
            else:
                scope = parts[0].split(".")[0]

        # Sanitize scope
        scope = re.sub(r"[^a-zA-Z0-9_\-]", "", scope)

        header = f"{commit_type}({scope}): {summary}" if scope else f"{commit_type}: {summary}"
        
        # Add bulleted file details if available
        bullets = []
        for p in changed_paths[:6]:
            bullets.append(f"- Update `{p}`")
        if len(changed_paths) > 6:
            bullets.append(f"- And {len(changed_paths) - 6} more files...")

        if bullets:
            return f"{header}\n\n" + "\n".join(bullets)
        return header
