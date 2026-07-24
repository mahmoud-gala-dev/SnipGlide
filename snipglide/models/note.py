from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class Note:
    id: Optional[int] = None
    title: str = ""
    content: str = ""
    category_id: Optional[int] = None
    created_date: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_date: str = field(default_factory=lambda: datetime.now().isoformat())
    color: str = "#2563eb"
    pinned: bool = False
