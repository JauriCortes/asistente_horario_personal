import json
import uuid
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from core.ai_client import ai_client
from storage import history, tasks
from storage import learning as learning_store

_COMPLETION_KEYWORDS = [
    "listo", "terminé", "completé", "tardé", "me tomó", "ya terminé",
    "acabé", "terminado", "hice", "lo hice", "lo terminé",
]

_DIFFICULTY_MAP = {
    "más difícil": "harder", "mas dificil": "harder", "difícil": "harder",
    "dificil": "harder", "complicado": "harder", "duro": "harder",
    "más fácil": "easier", "mas facil": "easier", "fácil": "easier",
    "facil": "easier", "sencillo": "easier", "rápido": "easier", "rapido": "easier",
    "normal": "as_expected", "como esperaba": "as_expected", "igual": "as_expected",
    "lo esperado": "as_expected",
}

_DETECT_SYSTEM = """Analizá si el mensaje del usuario indica que terminó una tarea. Devolvé SOLO JSON:

{
  "is_completion": true,
  "durationMin": 150
}

- is_completion: true si dice que terminó algo ("listo", "terminé", "completé", "hice", "ya acabé", "tardé X")
- durationMin: duración en minutos si la menciona ("2 horas"=120, "hora y media"=90, "45 min"=45). null si no dice."""


def looks_like_completion(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in _COMPLETION_KEYWORDS)


def detect_completion(text: str) -> dict:
    raw = ai_client.complete(
        role="interpreter",
        system_prompt=_DETECT_SYSTEM,
        user_message=text,
        json_mode=True,
    )
    try:
        return json.loads(raw)
    except Exception:
        return {"is_completion": False, "durationMin": None}


def _evt_id() -> str:
    return f"evt_{uuid.uuid4().hex[:8]}"


def _parse_difficulty(text: str) -> str | None:
    text_lower = text.lower().strip()
    for key, val in _DIFFICULTY_MAP.items():
        if key in text_lower:
            return val
    return None


def _derive_block_compliance(task: dict, completed_at: str) -> str:
    sched_start = task.get("calendar", {}).get("scheduledStart")
    if not sched_start:
        return "unscheduled"
    try:
        sched = datetime.fromisoformat(sched_start)
        done = datetime.fromisoformat(completed_at)
        delta = (done.date() - sched.date()).days
        if delta == 0:
            sched_end = datetime.fromisoformat(task["calendar"]["scheduledEnd"])
            return "on_schedule" if done <= sched_end else "same_day_late"
        return "different_day"
    except Exception:
        return "unscheduled"


def _best_active_task() -> dict | None:
    active = [
        t for t in tasks.load_tasks()
        if t.get("status") in ("scheduled", "in_progress", "captured")
    ]
    if not active:
        return None
    return sorted(active, key=lambda t: t.get("updatedAt", ""), reverse=True)[0]


async def _finalize_task(
    task_id: str,
    actual_duration: int,
    difficulty: str,
    update: Update,
) -> None:
    task = tasks.get_task(task_id)
    if not task:
        await update.message.reply_text("No encontré esa tarea.")
        return

    now = datetime.now(timezone.utc).astimezone().isoformat()
    deferral_count = history.count_events_by_type(task_id, "task_deferred")
    block_compliance = _derive_block_compliance(task, now)

    outcome = {
        "actualDurationMin": actual_duration,
        "completedAt": now,
        "result": "completed",
        "perceivedDifficulty": difficulty,
        "deferralCount": deferral_count,
        "blockCompliance": block_compliance,
    }

    tasks.update_task(task_id, {
        "status": "completed",
        "updatedAt": now,
        "outcome": outcome,
    })

    history.append_event({
        "id": _evt_id(),
        "taskId": task_id,
        "timestamp": now,
        "type": "task_completed",
        "data": outcome,
    })

    closed_task = {**task, "outcome": outcome}
    feedback = learning_store.update_learning(closed_task)
    await update.message.reply_text(feedback)


async def handle_difficulty_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    pending = context.user_data.pop("pending_difficulty")
    difficulty = _parse_difficulty(text) or "as_expected"
    await _finalize_task(
        pending["task_id"], pending["actualDurationMin"], difficulty, update
    )


async def handle_completion_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    pending = context.user_data["pending_completion"]

    try:
        duration = int("".join(c for c in text if c.isdigit()))
    except ValueError:
        await update.message.reply_text("No entendí el tiempo. ¿Cuántos minutos tardaste?")
        return

    del context.user_data["pending_completion"]
    context.user_data["pending_difficulty"] = {
        "task_id": pending["task_id"],
        "actualDurationMin": duration,
    }
    task = tasks.get_task(pending["task_id"])
    title = task.get("normalizedTitle", "la tarea") if task else "la tarea"
    await update.message.reply_text(
        f"Anotado: {duration} minutos para \"{title}\". "
        "¿Cómo te resultó? (más difícil / como esperaba / más fácil)"
    )


async def handle_natural_completion(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    detected: dict,
) -> None:
    task = _best_active_task()
    if not task:
        await update.message.reply_text("No encontré tareas activas para cerrar.")
        return

    duration = detected.get("durationMin")
    text = update.message.text.strip()
    difficulty = _parse_difficulty(text)

    if duration and difficulty:
        await _finalize_task(task["id"], duration, difficulty, update)
    elif duration:
        context.user_data["pending_difficulty"] = {
            "task_id": task["id"],
            "actualDurationMin": duration,
        }
        await update.message.reply_text(
            f"Anotado: {duration} minutos para \"{task.get('normalizedTitle')}\". "
            "¿Cómo te resultó? (más difícil / como esperaba / más fácil)"
        )
    else:
        context.user_data["pending_completion"] = {"task_id": task["id"]}
        await update.message.reply_text(
            f"¿Cuánto tardaste con \"{task.get('normalizedTitle')}\"? (en minutos)"
        )


async def handle_done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    duration = None
    if args:
        try:
            duration = int(args[0])
        except ValueError:
            pass

    task = _best_active_task()
    if not task:
        await update.message.reply_text("No tenés tareas activas para cerrar.")
        return

    title = task.get("normalizedTitle", "la tarea")

    if duration:
        context.user_data["pending_difficulty"] = {
            "task_id": task["id"],
            "actualDurationMin": duration,
        }
        await update.message.reply_text(
            f"Anotado: {duration} minutos para \"{title}\". "
            "¿Cómo te resultó? (más difícil / como esperaba / más fácil)"
        )
    else:
        context.user_data["pending_completion"] = {"task_id": task["id"]}
        await update.message.reply_text(f"¿Cuánto tardaste con \"{title}\"? (en minutos)")


async def handle_cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    task = _best_active_task()
    if not task:
        await update.message.reply_text("No tenés tareas activas para cancelar.")
        return

    now = datetime.now(timezone.utc).astimezone().isoformat()
    reason = " ".join(context.args) if context.args else None

    tasks.update_task(task["id"], {"status": "cancelled", "updatedAt": now})
    history.append_event({
        "id": _evt_id(),
        "taskId": task["id"],
        "timestamp": now,
        "type": "task_cancelled",
        "data": {"reason": reason},
    })
    title = task.get("normalizedTitle", "la tarea")
    await update.message.reply_text(f"Cancelé \"{title}\". Quedó registrado.")


async def handle_defer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    task = _best_active_task()
    if not task:
        await update.message.reply_text("No tenés tareas activas para diferir.")
        return

    now = datetime.now(timezone.utc).astimezone().isoformat()
    tasks.update_task(task["id"], {"status": "deferred", "updatedAt": now})
    history.append_event({
        "id": _evt_id(),
        "taskId": task["id"],
        "timestamp": now,
        "type": "task_deferred",
        "data": {},
    })
    title = task.get("normalizedTitle", "la tarea")
    await update.message.reply_text(f"Diferí \"{title}\". La retomo cuando me avises.")
