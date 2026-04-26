import json
import os
from pathlib import Path

_DATA_FILE = Path(__file__).parent.parent / "data" / "tasks.json"


def _load_raw() -> dict:
    with open(_DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_raw(data: dict) -> None:
    tmp = _DATA_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _DATA_FILE)


def load_tasks() -> list[dict]:
    return _load_raw().get("tasks", [])


def get_task(task_id: str) -> dict | None:
    return next((t for t in load_tasks() if t["id"] == task_id), None)


def get_tasks_by_status(status: str) -> list[dict]:
    return [t for t in load_tasks() if t.get("status") == status]


def add_task(task: dict) -> dict:
    data = _load_raw()
    data["tasks"].append(task)
    _save_raw(data)
    return task


def update_task(task_id: str, updates: dict) -> dict:
    data = _load_raw()
    for i, task in enumerate(data["tasks"]):
        if task["id"] == task_id:
            data["tasks"][i] = {**task, **updates}
            _save_raw(data)
            return data["tasks"][i]
    raise KeyError(f"Tarea no encontrada: {task_id}")


def delete_task(task_id: str) -> None:
    data = _load_raw()
    original = len(data["tasks"])
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    if len(data["tasks"]) == original:
        raise KeyError(f"Tarea no encontrada: {task_id}")
    _save_raw(data)
