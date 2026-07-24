from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class Snippet:
    id: Optional[int] = None
    shortcut: str = ""
    replacement: str = ""
    group_id: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    description: str = ""
    language: str = "Plain Text"
    enabled: bool = True
    favorite: bool = False
    usage_counter: int = 0
    created_date: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_date: str = field(default_factory=lambda: datetime.now().isoformat())
    hotkey: str = ""
    regex_enabled: bool = False
    app_filter: str = ""
    window_filter: str = ""
    notes: str = ""
