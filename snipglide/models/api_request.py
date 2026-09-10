from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any


@dataclass
class ApiRequest:
    id: Optional[int] = None
    name: str = "New Request"
    method: str = "GET"
    url: str = ""
    params: list[dict[str, Any]] = field(default_factory=list)
    headers: list[dict[str, Any]] = field(default_factory=list)
    auth_type: str = "none"  # "none", "bearer", "basic", "api_key"
    auth_data: dict[str, str] = field(default_factory=dict)
    body_type: str = "none"  # "none", "json", "raw", "form_urlencoded", "form_data"
    body_content: str = ""
    collection_name: str = "General"
    is_favorite: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ApiHistoryEntry:
    id: Optional[int] = None
    method: str = "GET"
    url: str = ""
    status_code: int = 0
    status_text: str = ""
    response_time_ms: float = 0.0
    response_size_bytes: int = 0
    created_at: Optional[datetime] = None


@dataclass
class ApiResponse:
    status_code: int = 0
    status_text: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    response_time_ms: float = 0.0
    response_size_bytes: int = 0
    content_type: str = "text/plain"
    is_error: bool = False
    error_message: str = ""
