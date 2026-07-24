from dataclasses import dataclass
from typing import Optional

@dataclass
class Group:
    id: Optional[int] = None
    name: str = "General"
    icon: str = "📁"
    color: str = "#2563eb"
    description: str = ""
    is_collapsed: bool = False
