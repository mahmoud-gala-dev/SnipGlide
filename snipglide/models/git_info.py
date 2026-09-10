"""Git data models for SnipGlide Git Developer Tools."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class GitCommit:
    """Represents a single Git commit."""
    hash: str
    short_hash: str
    author: str
    date: str
    message: str


@dataclass
class GitFileStatus:
    """Represents the status of a single file in the repository."""
    path: str
    status_code: str  # e.g., 'M', 'A', 'D', '??', 'R'
    is_staged: bool = False
    is_untracked: bool = False
    original_path: Optional[str] = None  # for renames


@dataclass
class GitRepoInfo:
    """High-level repository status information."""
    is_repo: bool = False
    root_path: str = ""
    current_branch: str = ""
    is_detached: bool = False
    ahead: int = 0
    behind: int = 0
    staged_files: List[GitFileStatus] = field(default_factory=list)
    modified_files: List[GitFileStatus] = field(default_factory=list)
    untracked_files: List[GitFileStatus] = field(default_factory=list)
    error_message: Optional[str] = None

    @property
    def total_changes(self) -> int:
        return len(self.staged_files) + len(self.modified_files) + len(self.untracked_files)

    @property
    def is_clean(self) -> bool:
        return self.total_changes == 0
