from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class ChatNote:
    id: Optional[int] = None
    content: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    is_starred: bool = False
    tags: str = ""
    color: str = "#25D366"
