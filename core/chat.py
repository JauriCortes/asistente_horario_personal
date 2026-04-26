import json
from pathlib import Path

from core.ai_client import ai_client
from storage import tasks

_LEARNING_FILE = Path(__file__).parent.parent / "data" / "task-learning.json"

_SYSTEM = """Sos el asistente de horario personal de un estudiante universitario. Tenés acceso al estado actual de su sistema: tareas, patrones de estimación y aprendizaje acumulado.

El usuario te hace una pregunta o comentario que no es directamente "capturar una tarea" ni "marcar algo como hecho". Respondé de forma útil y natural.

## Qué podés hacer bien
- Responder preguntas sobre sus tareas ("¿cuáles tengo sin agendar?", "¿qué tardé más en completar?")
- Dar recomendaciones basadas en sus patrones ("¿cuándo estudio mejor?")
- Responder preguntas generales de productividad, planificación, tecnología o lo que sea
- Razonar sobre qué conviene hacer primero

## Qué no hacés acá
- Capturar tareas nuevas (eso lo hace el flujo de captura automáticamente)
- Crear eventos en el calendario (para eso el usuario tiene que confirmar una sugerencia)

## Si la pregunta no tiene nada que ver con el sistema ni con productividad
Decile brevemente que para eso está mejor Claude.ai o Gemini, en 1 oración, sin drama.

## Tono
Informal, tuteo. Directo. Sin frases de chatbot."""


def _load_learning_summary() -> dict:
    try:
        data = json.loads(_LEARNING_FILE.read_text())
        acc = data.get("estimacionAccuracy", {})
        stats = data.get("stats", {})
        return {
            "courseMultipliers": acc.get("courseMultipliers", {}),
            "workTypeMultipliers": acc.get("workTypeMultipliers", {}),
            "completedTasks": stats.get("completedTasks", 0),
            "totalDeferrals": stats.get("totalDeferrals", 0),
            "patterns": [p.get("title") for p in data.get("patterns", [])[:3]],
        }
    except Exception:
        return {}


def build_chat_response(user_text: str) -> str:
    all_tasks = tasks.load_tasks()
    active = [t for t in all_tasks if t.get("status") not in ("completed", "cancelled")]
    completed = [t for t in all_tasks if t.get("status") == "completed"]

    context = json.dumps({
        "userMessage": user_text,
        "activeTasks": [
            {
                "title": t.get("normalizedTitle"),
                "status": t.get("status"),
                "domain": t.get("domain"),
                "course": t.get("course"),
                "workType": t.get("workType"),
                "deadline": t.get("deadline"),
                "scheduledStart": t.get("calendar", {}).get("scheduledStart"),
            }
            for t in active[:10]
        ],
        "recentlyCompleted": [
            {
                "title": t.get("normalizedTitle"),
                "course": t.get("course"),
                "actualMin": t.get("outcome", {}).get("actualDurationMin"),
                "estimateMin": f"{t.get('estimate', {}).get('lowMin')}-{t.get('estimate', {}).get('highMin')}",
                "difficulty": t.get("outcome", {}).get("perceivedDifficulty"),
            }
            for t in completed[-5:]
        ],
        "learning": _load_learning_summary(),
    }, ensure_ascii=False)

    return ai_client.complete(
        role="evaluator",
        system_prompt=_SYSTEM,
        user_message=context,
    )
