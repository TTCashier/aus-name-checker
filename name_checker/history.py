"""Search history persistence."""

import json
from datetime import datetime

from .config import HISTORY_PATH


def load_history() -> list:
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text())
    return []


def save_history(names: list):
    history = load_history()
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "names": names,
    }
    history.append(entry)
    history = history[-50:]
    HISTORY_PATH.write_text(json.dumps(history, indent=2))


def get_last_names() -> list:
    history = load_history()
    if not history:
        return []
    return history[-1]["names"]
