"""Data models for Developer Projects and Terminal Command Library."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DeveloperProject:
    """Represents a local software development project profile."""
    id: Optional[int] = None
    name: str = ""
    project_path: str = ""
    language: str = ""
    framework: str = ""
    description: str = ""
    favorite: bool = False
    created_at: str = ""
    updated_at: str = ""


@dataclass
class TerminalCommand:
    """Represents a safe reference terminal command or shell snippet."""
    id: Optional[int] = None
    name: str = ""
    command: str = ""
    description: str = ""
    category: str = "General"
    project_id: Optional[int] = None
    favorite: bool = False
    created_at: str = ""
    updated_at: str = ""
