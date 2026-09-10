"""Shallow Project Framework and Language Detection Service.

Fast and safe: inspects root directory markers without recursively traversing folders,
executing commands, or scanning .env secret files.
"""
from __future__ import annotations

import json
import os
from typing import Tuple


def detect_project_type(project_path: str) -> Tuple[str, str]:
    """Detect primary programming language and framework for a given directory.

    Returns:
        (language, framework)
    """
    if not project_path or not os.path.isdir(project_path):
        return "Unknown", "None"

    language = "Unknown"
    framework = "None"

    try:
        # Shallow list of root items only
        entries = set(os.listdir(project_path))
    except Exception:
        return "Unknown", "None"

    # 1. Docker check
    has_docker = "Dockerfile" in entries or "docker-compose.yml" in entries or "docker-compose.yaml" in entries

    # 2. Python ecosystem detection
    has_py_files = (
        "requirements.txt" in entries
        or "pyproject.toml" in entries
        or "setup.py" in entries
        or "Pipfile" in entries
        or "poetry.lock" in entries
    )
    if "manage.py" in entries:
        language = "Python"
        framework = "Django"
    elif has_py_files:
        language = "Python"
        # Check requirements.txt or pyproject.toml shallowly for FastAPI / Flask
        req_file = os.path.join(project_path, "requirements.txt")
        pyproj_file = os.path.join(project_path, "pyproject.toml")
        req_content = ""
        if os.path.isfile(req_file):
            try:
                with open(req_file, "r", encoding="utf-8", errors="ignore") as f:
                    req_content = f.read(4096).lower()
            except Exception:
                pass
        elif os.path.isfile(pyproj_file):
            try:
                with open(pyproj_file, "r", encoding="utf-8", errors="ignore") as f:
                    req_content = f.read(4096).lower()
            except Exception:
                pass

        if "fastapi" in req_content:
            framework = "FastAPI"
        elif "flask" in req_content:
            framework = "Flask"
        elif "django" in req_content:
            framework = "Django"
        else:
            framework = "Standard Python"

    # 3. JavaScript / TypeScript ecosystem detection
    has_pkg_json = "package.json" in entries
    has_tsconfig = "tsconfig.json" in entries

    if has_pkg_json:
        language = "TypeScript" if has_tsconfig else "JavaScript"
        pkg_file = os.path.join(project_path, "package.json")
        try:
            with open(pkg_file, "r", encoding="utf-8", errors="ignore") as f:
                pkg_data = json.load(f)
                deps = {}
                deps.update(pkg_data.get("dependencies", {}))
                deps.update(pkg_data.get("devDependencies", {}))

                if "next" in deps:
                    framework = "Next.js"
                elif "react" in deps:
                    framework = "React"
                elif "vue" in deps or "nuxt" in deps:
                    framework = "Vue"
                elif "@angular/core" in deps:
                    framework = "Angular"
                elif "@nestjs/core" in deps:
                    framework = "NestJS"
                elif "express" in deps:
                    framework = "Express"
                elif "electron" in deps:
                    framework = "Electron"
                else:
                    framework = "Node.js"
        except Exception:
            framework = "Node.js"

    # 4. .NET detection
    if language == "Unknown":
        for item in entries:
            if item.endswith(".csproj") or item.endswith(".sln"):
                language = ".NET / C#"
                framework = ".NET Core"
                break

    # 5. Fallbacks with Docker
    if framework == "None" and has_docker:
        framework = "Docker Container"

    return language, framework
