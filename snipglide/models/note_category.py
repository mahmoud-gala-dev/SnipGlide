from dataclasses import dataclass
from typing import Optional


@dataclass
class NoteCategory:
    id: Optional[int] = None
    name: str = ""
    icon: str = "N"
    color: str = "#2563eb"
    description: str = ""
