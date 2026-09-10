"""Active Project Context Service for SnipGlide Developer Tools.

Maintains the currently focused developer project across tools (Git, Commands, API, Snippets).
"""
from __future__ import annotations

from typing import Callable, List, Optional

from snipglide.models.project_models import DeveloperProject


class ActiveProjectManager:
    """Singleton manager tracking the currently active project profile."""
    _instance: Optional[ActiveProjectManager] = None

    def __new__(cls) -> ActiveProjectManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._active_project = None
            cls._instance._listeners = []
        return cls._instance

    @property
    def active_project(self) -> Optional[DeveloperProject]:
        return self._active_project

    def set_active_project(self, project: Optional[DeveloperProject]):
        self._active_project = project
        self._notify_listeners()

    def add_listener(self, callback: Callable[[Optional[DeveloperProject]], None]):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[Optional[DeveloperProject]], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self):
        for listener in list(self._listeners):
            try:
                listener(self._active_project)
            except Exception:
                pass


active_project_mgr = ActiveProjectManager()
