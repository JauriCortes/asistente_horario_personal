import uuid
from datetime import datetime, timezone

from integrations.gcal import create_event
from storage import history, tasks


def _evt_id() -> str:
    return f"evt_{uuid.uuid4().hex[:8]}"


def schedule_task(task_id: str, slot: dict) -> str:
    """
    Crea el evento en Google Calendar y actualiza la tarea a status: scheduled.
    Devuelve el eventId de Google.
    """
    task = tasks.get_task(task_id)
    if not task:
        raise KeyError(f"Tarea no encontrada: {task_id}")

    event_id = create_event(
        summary=task.get("normalizedTitle", task.get("inputText", "Tarea")),
        start_dt=slot["start"],
        end_dt=slot["end"],
    )

    now = datetime.now(timezone.utc).astimezone().isoformat()

    tasks.update_task(task_id, {
        "status": "scheduled",
        "updatedAt": now,
        "calendar": {
            "status": "scheduled",
            "eventId": event_id,
            "scheduledStart": slot["start"],
            "scheduledEnd": slot["end"],
        },
    })

    history.append_event({
        "id": _evt_id(),
        "taskId": task_id,
        "timestamp": now,
        "type": "calendar_scheduled",
        "data": {
            "eventId": event_id,
            "scheduledStart": slot["start"],
            "scheduledEnd": slot["end"],
        },
    })

    return event_id
