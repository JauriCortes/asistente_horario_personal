import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.ai_client import ai_client
from integrations.gcal import CalendarAuthError, get_events
from storage import tasks

_STALE_DAYS = 3  # días sin avanzar para considerar tarea estancada

_DAILY_SYSTEM = """Sos el asistente de horario de un estudiante universitario. Generá el mensaje de buenos días del lunes (resumen semanal proactivo).

Reglas:
- Máximo 3-4 oraciones.
- Tono informal, tuteo. Directo, no robótico.
- Mencioná cuántas tareas hay sin agendar y cuál es la más urgente si tiene deadline.
- Si hay tareas de universidad, mencionalas con la materia.
- Mencioná los eventos importantes del día si los hay.
- No empieces con "Buenos días" literalmente, sé más natural.
- Respondé solo el mensaje."""

_QUERY_SYSTEM = """Sos el asistente de horario de un estudiante universitario respondiendo la pregunta sobre qué tiene pendiente.

Reglas:
- Máximo 4-5 oraciones.
- Tono informal, tuteo.
- Listá las tareas y eventos de forma clara pero conversacional.
- Si hay tareas urgentes o con deadline próximo, marcalas.
- Respondé solo el mensaje, sin formato markdown ni bullets."""

_WEEKLY_SYSTEM = """Sos el asistente de horario de un estudiante universitario generando el resumen semanal.

Reglas:
- Máximo 5-6 oraciones.
- Tono informal, tuteo.
- Mencioná cuántas tareas completaste, cuántas moviste, y si las estimaciones fueron precisas.
- Si hay patrones notables (siempre tardás más en cierta materia, etc.), mencionalo brevemente.
- Terminá con algo accionable para la semana que empieza.
- Respondé solo el mensaje."""


def _get_stale_tasks(days: int = _STALE_DAYS) -> list[dict]:
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    return [
        t for t in tasks.load_tasks()
        if t.get("status") in ("captured", "ready_to_schedule", "deferred")
        and datetime.fromisoformat(t["updatedAt"].replace("Z", "+00:00")) < threshold
    ]


def _get_unscheduled_tasks() -> list[dict]:
    return [
        t for t in tasks.load_tasks()
        if t.get("status") in ("captured", "ready_to_schedule")
    ]


def _get_completed_this_week() -> list[dict]:
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    return [
        t for t in tasks.load_tasks()
        if t.get("status") == "completed"
        and t.get("outcome", {}).get("completedAt")
        and datetime.fromisoformat(
            t["outcome"]["completedAt"].replace("Z", "+00:00")
        ) > week_ago
    ]


def _estimate_accuracy_summary(completed: list[dict]) -> dict:
    ratios = []
    for t in completed:
        actual = t.get("outcome", {}).get("actualDurationMin")
        est = t.get("estimate", {})
        low, high = est.get("lowMin"), est.get("highMin")
        if actual and low and high:
            ratios.append(actual / ((low + high) / 2))
    if not ratios:
        return {}
    avg = sum(ratios) / len(ratios)
    return {"avgRatio": round(avg, 2), "sampleSize": len(ratios)}


def build_daily_message() -> str:
    """Genera el mensaje proactivo diario/semanal."""
    now = datetime.now(timezone.utc).astimezone()
    unscheduled = _get_unscheduled_tasks()
    stale = _get_stale_tasks()

    calendar_today = []
    try:
        all_events = get_events(days_ahead=1)
        today_str = now.date().isoformat()
        calendar_today = [
            e for e in all_events
            if e.get("start", "").startswith(today_str)
        ]
    except (CalendarAuthError, Exception):
        pass

    ctx = json.dumps({
        "dayOfWeek": now.strftime("%A"),
        "date": now.date().isoformat(),
        "unscheduledTasks": [
            {
                "title": t.get("normalizedTitle"),
                "domain": t.get("domain"),
                "course": t.get("course"),
                "deadline": t.get("deadline"),
            }
            for t in unscheduled[:5]
        ],
        "staleTasks": [
            {"title": t.get("normalizedTitle"), "daysSinceUpdate": _STALE_DAYS}
            for t in stale[:3]
        ],
        "todayEvents": [
            {"summary": e.get("summary"), "start": e.get("start")}
            for e in calendar_today[:5]
        ],
    }, ensure_ascii=False)

    return ai_client.complete(
        role="conversador",
        system_prompt=_DAILY_SYSTEM,
        user_message=ctx,
    )


def build_query_response(scope: str = "today") -> str:
    """Responde 'qué tengo hoy/esta semana'."""
    now = datetime.now(timezone.utc).astimezone()
    days = 1 if scope == "today" else 7

    active = [
        t for t in tasks.load_tasks()
        if t.get("status") in ("captured", "scheduled", "ready_to_schedule", "in_progress")
    ]

    calendar_events = []
    try:
        calendar_events = get_events(days_ahead=days)
        today_str = now.date().isoformat()
        if scope == "today":
            calendar_events = [e for e in calendar_events if e.get("start", "").startswith(today_str)]
    except (CalendarAuthError, Exception):
        pass

    ctx = json.dumps({
        "scope": scope,
        "date": now.date().isoformat(),
        "activeTasks": [
            {
                "title": t.get("normalizedTitle"),
                "status": t.get("status"),
                "domain": t.get("domain"),
                "course": t.get("course"),
                "deadline": t.get("deadline"),
                "scheduledStart": t.get("calendar", {}).get("scheduledStart"),
            }
            for t in active[:8]
        ],
        "calendarEvents": [
            {"summary": e.get("summary"), "start": e.get("start")}
            for e in calendar_events[:8]
        ],
    }, ensure_ascii=False)

    return ai_client.complete(
        role="conversador",
        system_prompt=_QUERY_SYSTEM,
        user_message=ctx,
    )


def build_weekly_summary() -> str:
    """Genera el resumen semanal."""
    completed = _get_completed_this_week()
    deferred = [t for t in tasks.load_tasks() if t.get("status") == "deferred"]
    accuracy = _estimate_accuracy_summary(completed)

    ctx = json.dumps({
        "completedThisWeek": len(completed),
        "completedTitles": [t.get("normalizedTitle") for t in completed[:5]],
        "deferredCount": len(deferred),
        "accuracy": accuracy,
        "unscheduledCount": len(_get_unscheduled_tasks()),
    }, ensure_ascii=False)

    return ai_client.complete(
        role="conversador",
        system_prompt=_WEEKLY_SYSTEM,
        user_message=ctx,
    )
