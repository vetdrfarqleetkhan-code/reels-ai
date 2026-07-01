from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .utils import PROJECTS_DIR, safe_name


def save_project(name: str, config: dict, script: str, files: dict[str, bytes]) -> Path:
    folder = PROJECTS_DIR / safe_name(name, "Untitled Reel")
    folder.mkdir(parents=True, exist_ok=True)
    config = {**config, "title": name, "saved_at": datetime.now(timezone.utc).isoformat()}
    (folder / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    (folder / "script.txt").write_text(script, encoding="utf-8")
    for relative, data in files.items():
        target = folder / safe_name(relative)
        target.write_bytes(data)
    return folder


def list_projects() -> list[dict]:
    projects = []
    if not PROJECTS_DIR.exists(): return projects
    for config_path in PROJECTS_DIR.glob("*/config.json"):
        try:
            config = json.loads(config_path.read_text(encoding="utf-8")); config["path"] = str(config_path.parent); projects.append(config)
        except (OSError, json.JSONDecodeError): pass
    return sorted(projects, key=lambda p: p.get("saved_at", ""), reverse=True)


def load_project(folder: Path) -> tuple[dict, str]:
    folder = folder.resolve()
    if PROJECTS_DIR.resolve() not in folder.parents: raise ValueError("Invalid project path.")
    return json.loads((folder / "config.json").read_text(encoding="utf-8")), (folder / "script.txt").read_text(encoding="utf-8")

