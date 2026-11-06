"""Atomic settings persistence outside the executable directory."""
import json
import os
import secrets
from pathlib import Path
from squidz.core.models import Settings

DATA_DIR = Path(os.environ.get("APPDATA", str(Path.home() / ".config"))) / "squidz"
SETTINGS_PATH = DATA_DIR / "settings.json"

def load(path: Path = SETTINGS_PATH) -> Settings:
    if not path.exists():
        obj = Settings.defaults()
        obj.browser_token = secrets.token_urlsafe(32)
        save(obj, path)
        return obj
    obj = Settings.parse(json.loads(path.read_text(encoding="utf-8")))
    if not obj.browser_token:
        obj.browser_token = secrets.token_urlsafe(32)
        save(obj, path)
    return obj

def save(settings: Settings, path: Path = SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(settings.dump(), f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
