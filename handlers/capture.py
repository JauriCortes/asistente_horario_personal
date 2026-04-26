import json
import uuid
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from core.ai_client import ai_client
from core.capacity import evaluate
from core.estimator import estimate
from core.interpreter import interpret
from integrations.gcal import CalendarAuthError, get_events
from storage import history, tasks

_CONFIRMATION_SYSTEM = """Sos el asistente de horario de un estudiante universitario que usa Telegram. Acabás de registrar, estimar y buscar bloques disponibles para una tarea nueva. Presentá todo en un mensaje breve y natural.

Reglas:
- Máximo 3-4 oraciones cortas.
- Tono informal, tuteo. Como un compañero, no un chatbot corporativo.
- No empieces con "De acuerdo", "Perfecto", "Claro" ni fórmulas de asistente.
- Si es de universidad, mencioná la materia de forma natural.
- Incluí el rango estimado de forma natural (ej: "calculo unos 90-120 minutos").
- Si hay expansionRisk "high", avisalo brevemente.
- Presentá las 2 mejores opciones con día/hora legible. No menciones "rank" ni "quality".
- Terminá con una pregunta sobre cuál les queda mejor.
- Respondé solo el mensaje, sin formato."""

_NO_CALENDAR_SYSTEM = """Sos el asistente de horario de un estudiante universitario. Registraste y estimaste una tarea nueva pero el calendario no está disponible.

- Máximo 2 oraciones. Informal, tuteo.
- Confirmá la tarea y la estimación naturalmente.
- Mencioná que después buscamos un bloque.
- Respondé solo el mensaje."""

_CLARIFICATION_FOLLOWUP_SYSTEM = """Sos el asistente de horario. El usuario respondió una pregunta de aclaración sobre una tarea. Ahora tenés el texto aclarado. Confirmá brevemente lo que entendiste y continuá el flujo normal (mencioná estimación y opciones de horario si las hay). Informal, tuteo, máximo 3 oraciones."""


def _evt_id() -> str:
    return f"evt_{uuid.uuid4().hex[:8]}"


_QUERY_KEYWORDS = ["qué tengo", "que tengo", "qué hay", "que hay", "pendientes", "agenda de", "qué tareas", "que tareas"]
_COMPLETION_KEYWORDS = ["listo", "terminé", "completé", "tardé", "me tomó", "ya terminé", "acabé", "terminado", "lo hice", "lo terminé"]


async def _run_capture_pipeline(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    user_id: str,
) -> None:
    """Ejecuta el pipeline completo: interpretar → estimar → evaluar → responder."""
    await update.message.chat.send_action("typing")

    task = interpret(text, user_id=user_id)
    meta = task.get("_meta", {})

    # Claridad baja → guardar borrador y preguntar
    if meta.get("needsClarification"):
        context.user_data["pending_clarification"] = {"draft_text": text}
        await update.message.reply_text(meta["clarificationQuestion"])
        return

    est = estimate(task)
    task["estimate"] = est
    task["updatedAt"] = datetime.now(timezone.utc).astimezone().isoformat()

    calendar_available = True
    capacity = None
    calendar_warning = None

    try:
        events = get_events(days_ahead=7)
        capacity = evaluate(task, events)
    except CalendarAuthError:
        calendar_available = False
        calendar_warning = "Token vencido. Corré: gws auth login"
    except Exception as e:
        calendar_available = False
        calendar_warning = str(e)

    tasks.add_task(task)
    history.append_event({
        "id": _evt_id(), "taskId": task["id"], "timestamp": task["createdAt"],
        "type": "task_created",
        "data": {"source": "telegram", "inputText": text,
                 "inferenceNotes": meta.get("inferenceNotes")},
    })
    history.append_event({
        "id": _evt_id(), "taskId": task["id"], "timestamp": task["updatedAt"],
        "type": "estimate_generated",
        "data": {
            "lowMin": est["lowMin"], "highMin": est["highMin"],
            "confidence": est["confidence"], "basis": est["basis"],
            "domain": task.get("domain"), "course": task.get("course"),
            "workType": task.get("workType"),
        },
    })

    if calendar_available and capacity:
        history.append_event({
            "id": _evt_id(), "taskId": task["id"],
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
            "type": "capacity_evaluated",
            "data": {"suggestionsCount": len(capacity["suggestions"]),
                     "warnings": capacity["warnings"]},
        })
        context.user_data["pending_schedule"] = {
            "task": task,
            "suggestions": capacity["suggestions"][:2],
        }

    if calendar_available and capacity:
        summary = json.dumps({
            "normalizedTitle": task.get("normalizedTitle"),
            "type": task.get("type"), "domain": task.get("domain"),
            "course": task.get("course"), "workType": task.get("workType"),
            "deadline": task.get("deadline"),
            "estimate": {"lowMin": est["lowMin"], "highMin": est["highMin"],
                         "confidence": est["confidence"], "expansionRisk": est["expansionRisk"]},
            "suggestions": capacity["suggestions"][:2],
            "warnings": capacity["warnings"],
        }, ensure_ascii=False)
        reply = ai_client.complete(role="conversador", system_prompt=_CONFIRMATION_SYSTEM,
                                   user_message=summary)
    else:
        summary = json.dumps({
            "normalizedTitle": task.get("normalizedTitle"),
            "domain": task.get("domain"), "course": task.get("course"),
            "estimate": {"lowMin": est["lowMin"], "highMin": est["highMin"]},
        }, ensure_ascii=False)
        reply = ai_client.complete(role="conversador", system_prompt=_NO_CALENDAR_SYSTEM,
                                   user_message=summary)

    await update.message.reply_text(reply)
    if calendar_warning:
        await update.message.reply_text(f"⚠️ {calendar_warning}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from handlers.review import (
        detect_completion, handle_completion_duration, handle_difficulty_response,
        handle_natural_completion, looks_like_completion,
    )
    from handlers.schedule import handle_schedule_response

    text = update.message.text.strip()
    user_id = str(update.effective_user.id)

    # ── 1. Respuesta de dificultad pendiente ──────────────────
    if context.user_data.get("pending_difficulty"):
        await handle_difficulty_response(update, context)
        return

    # ── 2. Respuesta de duración pendiente ────────────────────
    if context.user_data.get("pending_completion"):
        await handle_completion_duration(update, context)
        return

    # ── 3. Respuesta de aclaración pendiente ─────────────────
    if context.user_data.get("pending_clarification"):
        del context.user_data["pending_clarification"]
        # Caemos al routing normal: si es una query o pregunta, se maneja bien

    # ── 4. Confirmación/respuesta de bloque pendiente ─────────
    if context.user_data.get("pending_schedule"):
        handled = await handle_schedule_response(update, context)
        if handled:
            return
        # intent=new_task: seguimos al pipeline de captura

    # ── 5. Consultas de agenda ─────────────────────────────────
    text_lower = text.lower()
    if any(kw in text_lower for kw in _QUERY_KEYWORDS):
        from core.proactivity import build_query_response
        await update.message.chat.send_action("typing")
        scope = "week" if any(w in text_lower for w in ["semana", "week"]) else "today"
        await update.message.reply_text(build_query_response(scope))
        return

    # ── 6. Completación en lenguaje natural ───────────────────
    if looks_like_completion(text):
        detected = detect_completion(text)
        if detected.get("is_completion"):
            await handle_natural_completion(update, context, detected)
            return

    # ── 7. Pipeline de captura ────────────────────────────────
    # Antes de capturar, verificamos si suena a pregunta/chat general
    # (no contiene verbos de acción propios de una tarea)
    action_words = ["hacer", "estudiar", "terminar", "completar", "revisar", "entregar",
                    "preparar", "leer", "escribir", "ir", "comprar", "llamar", "mandar",
                    "ejercicio", "taller", "parcial", "tarea", "proyecto", "práctica"]
    question_words = ["cómo", "como", "qué", "que", "cuándo", "cuando", "cuánto",
                      "cuanto", "por qué", "por que", "cuál", "cual", "dónde", "donde",
                      "puedo", "puedes", "podés", "debería", "deberia", "debés",
                      "conviene", "recomendas", "sabés", "sabes", "tenés contexto",
                      "podría", "podrías"]

    has_question_marks = "¿" in text or "?" in text
    looks_like_task = any(w in text_lower for w in action_words)
    has_question_word = any(w in text_lower for w in question_words)
    looks_like_question = has_question_word and (has_question_marks or not looks_like_task)

    if looks_like_question or not looks_like_task:
        from core.chat import build_chat_response
        await update.message.chat.send_action("typing")
        await update.message.reply_text(build_chat_response(text))
        return

    await _run_capture_pipeline(update, context, text, user_id)
