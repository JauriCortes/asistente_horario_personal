import json
import uuid
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from core.ai_client import ai_client
from core.scheduler import schedule_task

_INTENT_SYSTEM = """Analizá la respuesta del usuario en el contexto de una conversación donde se le ofrecieron bloques horarios para agendar una tarea. Devolvé SOLO JSON:

{
  "intent": "confirm",
  "selected_rank": 1,
  "preference": null
}

## Valores posibles para intent

- "confirm": el usuario acepta un bloque específico (menciona un número, día u hora que coincide con alguna opción)
- "alternatives": pide ver otras opciones con alguna preferencia ("Y el domingo?", "¿hay algo por la tarde?", "otro día")
- "reject": rechaza sin dar preferencia ("ese no", "ninguna", "no me sirve ninguna")
- "defer": quiere dejarlo para después ("más tarde", "lo veo después", "no por ahora", "dejalo")
- "new_task": el mensaje es claramente una tarea nueva, no una respuesta a las opciones

## Campos adicionales

- selected_rank: número de la opción elegida (1, 2...) si intent="confirm", sino null
- preference: descripción libre de la preferencia si intent="alternatives" (ej: "domingo", "tarde", "semana que viene"), sino null"""


_SEARCH_ALT_SYSTEM = """Sos el asistente de horario. El usuario rechazó las opciones y pidió alternativas con una preferencia. Explicale brevemente que estás buscando nuevos bloques y qué encontraste. Sé natural e informal."""

_SCHEDULED_SYSTEM = """Sos el asistente de horario de un estudiante universitario. Acabás de agendar una tarea en Google Calendar. Confirmá de forma breve y natural.

Reglas:
- 1-2 oraciones. Informal, tuteo.
- Mencioná el día y la hora de forma legible.
- No uses frases de chatbot. Respondé solo el mensaje."""

_REJECTED_SYSTEM = """Sos el asistente de horario. El usuario rechazó todas las opciones sin dar una preferencia. Preguntale brevemente qué prefiere: buscar otro momento, dejarlo para después, o cancelar la tarea. Máximo 1 oración, informal."""


def _evt_id() -> str:
    return f"evt_{uuid.uuid4().hex[:8]}"


def _format_slot(slot: dict, rank: int) -> str:
    start = slot.get("start", "")
    try:
        dt = datetime.fromisoformat(start)
        dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        dia = dias[dt.weekday()]
        hora = dt.strftime("%-I:%M%p").lower()
        return f"Opción {rank}: {dia} {dt.day} a las {hora}"
    except Exception:
        return f"Opción {rank}: {start}"


def _classify_intent(user_text: str, suggestions: list[dict]) -> dict:
    slot_descriptions = "\n".join(
        _format_slot(s, s.get("rank", i + 1)) for i, s in enumerate(suggestions)
    )
    user_msg = f"Opciones ofrecidas:\n{slot_descriptions}\n\nRespuesta del usuario: {user_text!r}"
    raw = ai_client.complete(
        role="interpreter",
        system_prompt=_INTENT_SYSTEM,
        user_message=user_msg,
        json_mode=True,
    )
    try:
        return json.loads(raw)
    except Exception:
        return {"intent": "new_task", "selected_rank": None, "preference": None}


async def handle_schedule_response(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """
    Maneja la respuesta del usuario a una sugerencia de bloques.
    Devuelve True si lo manejó, False si es una tarea nueva.
    """
    pending = context.user_data.get("pending_schedule")
    if not pending:
        return False

    text = update.message.text.strip()
    suggestions = pending.get("suggestions", [])
    task = pending["task"]

    classified = _classify_intent(text, suggestions)
    intent = classified.get("intent", "new_task")

    # ── Nueva tarea → dejar pasar al flujo de captura ──────────
    if intent == "new_task":
        del context.user_data["pending_schedule"]
        return False

    # ── Diferir ─────────────────────────────────────────────────
    if intent == "defer":
        del context.user_data["pending_schedule"]
        from storage import history, tasks
        now = datetime.now().astimezone().isoformat()
        tasks.update_task(task["id"], {"status": "deferred", "updatedAt": now})
        history.append_event({
            "id": _evt_id(), "taskId": task["id"], "timestamp": now,
            "type": "task_deferred", "data": {},
        })
        await update.message.reply_text(
            f"Dale, dejo \"{task.get('normalizedTitle')}\" para después. "
            "Avisame cuando quieras retomarlo."
        )
        return True

    # ── Rechazó sin preferencia → preguntamos ───────────────────
    if intent == "reject":
        reply = ai_client.complete(
            role="conversador",
            system_prompt=_REJECTED_SYSTEM,
            user_message=json.dumps({"task": task.get("normalizedTitle")}),
        )
        await update.message.reply_text(reply)
        return True

    # ── Pide alternativas ────────────────────────────────────────
    if intent == "alternatives":
        await update.message.chat.send_action("typing")
        preference = classified.get("preference", "")
        try:
            from integrations.gcal import CalendarAuthError, get_events
            from core.capacity import evaluate
            events = get_events(days_ahead=14)
            new_capacity = evaluate(task, events)
            new_suggestions = new_capacity.get("suggestions", [])[:2]

            if not new_suggestions:
                await update.message.reply_text(
                    "No encontré otros huecos buenos en los próximos 14 días. "
                    "¿Lo dejamos para después?"
                )
                return True

            context.user_data["pending_schedule"]["suggestions"] = new_suggestions
            slots_text = " o ".join(
                _format_slot(s, s.get("rank", i + 1))
                for i, s in enumerate(new_suggestions)
            )
            pref_note = f" (buscando: {preference})" if preference else ""
            await update.message.reply_text(
                f"Mirando más opciones{pref_note}: {slots_text}. ¿Cuál te viene mejor?"
            )
        except Exception as e:
            await update.message.reply_text(
                f"No pude buscar nuevas opciones ahora ({e}). ¿Lo agendamos después?"
            )
        return True

    # ── Confirmar ────────────────────────────────────────────────
    if intent == "confirm":
        selected_rank = classified.get("selected_rank")
        slot = next(
            (s for s in suggestions if s.get("rank") == selected_rank),
            suggestions[0] if suggestions else None,
        )
        if not slot:
            await update.message.reply_text("No encontré esa opción. ¿Cuál preferís?")
            return True

        await update.message.chat.send_action("typing")
        try:
            schedule_task(task["id"], slot)
        except Exception as e:
            await update.message.reply_text(f"No pude crear el evento: {e}")
            del context.user_data["pending_schedule"]
            return True

        del context.user_data["pending_schedule"]
        slot_ctx = json.dumps({
            "task": task.get("normalizedTitle"),
            "start": slot.get("start"),
            "end": slot.get("end"),
        }, ensure_ascii=False)
        reply = ai_client.complete(
            role="conversador",
            system_prompt=_SCHEDULED_SYSTEM,
            user_message=slot_ctx,
        )
        await update.message.reply_text(reply)
        return True

    # Fallback: no entendimos, pedimos aclaración
    slots_text = " o ".join(
        _format_slot(s, s.get("rank", i + 1)) for i, s in enumerate(suggestions)
    )
    await update.message.reply_text(
        f"No entendí bien. Tenés: {slots_text}. "
        "¿Cuál te queda mejor, querés buscar otro momento, o lo dejamos para después?"
    )
    return True
