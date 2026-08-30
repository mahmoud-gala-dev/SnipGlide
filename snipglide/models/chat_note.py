from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class ChatNoteSection:
    id: Optional[int] = None
    name: str = ""
    icon: str = "💬"
    color: str = "#25D366"

@dataclass
class ChatNote:
    id: Optional[int] = None
    content: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    is_starred: bool = False
    section_id: Optional[int] = 1
    tags: str = ""
    color: str = "#25D366"
