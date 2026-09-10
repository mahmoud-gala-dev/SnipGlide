from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class SavedRegex:
    id: Optional[int] = None
    name: str = ""
    pattern: str = ""
    description: str = ""
    flags: str = ""
    replacement: str = ""
    favorite: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
