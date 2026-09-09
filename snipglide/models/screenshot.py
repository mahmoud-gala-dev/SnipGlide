from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class Screenshot:
    id: Optional[int] = None
    file_path: str = ""
    filename: str = ""
    capture_type: str = "full"  # "full" or "area"
    width: int = 0
    height: int = 0
    file_size: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    is_favorite: bool = False
    note: str = ""
