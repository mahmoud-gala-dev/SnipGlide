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
    duration: float = 0.0
    thumbnail_path: str = ""

    @property
    def is_video(self) -> bool:
        return self.capture_type.startswith("video") or self.filename.lower().endswith((".mp4", ".avi", ".mkv", ".mov"))

    @property
    def formatted_duration(self) -> str:
        if not self.is_video:
            return ""
        total_sec = int(self.duration)
        mins = total_sec // 60
        secs = total_sec % 60
        return f"{mins:02d}:{secs:02d}"
