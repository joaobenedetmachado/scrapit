"""
Compare a freshly scraped result against the previous JSON output.
Returns a dict of changed fields: {field: {"old": ..., "new": ...}}.
"""
import json
from pathlib import Path
from scraper.config import OUTPUT_DIR


def load_previous(name: str) -> dict | None:
    path = OUTPUT_DIR / f"{name}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def diff(old: dict, new: dict) -> dict:
    changes = {}
    all_keys = set(old) | set(new)
    skip = {"timestamp", "_id"}
    for key in all_keys:
        if key in skip:
            continue
        old_val = old.get(key)
        new_val = new.get(key)
        if str(old_val) != str(new_val):
            changes[key] = {"old": old_val, "new": new_val}
    return changes
