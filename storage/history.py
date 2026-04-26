import json
import os
from pathlib import Path

_DATA_FILE = Path(__file__).parent.parent / "data" / "task-history.json"


def _load_raw() -> dict:
    with open(_DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_raw(data: dict) -> None:
    tmp = _DATA_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _DATA_FILE)


def load_events(task_id: str | None = None) -> list[dict]:
    events = _load_raw().get("events", [])
    if task_id:
        return [e for e in events if e.get("taskId") == task_id]
    return events


def append_event(event: dict) -> dict:
    data = _load_raw()
    data["events"].append(event)
    _save_raw(data)
    return event


def count_events_by_type(task_id: str, event_type: str) -> int:
    return sum(
        1 for e in load_events(task_id) if e.get("type") == event_type
    )
