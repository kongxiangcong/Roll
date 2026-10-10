import os
from pathlib import Path


def data_directory() -> Path:
    if configured := os.environ.get("ROLL_DATA_DIR"):
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Roll"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "roll"
