import json
from datetime import datetime, timezone
from pathlib import Path

from core.ai_client import ai_client

_LEARNING_FILE = Path(__file__).parent.parent / "data" / "task-learning.json"

_SYSTEM_PROMPT = """Sos el Evaluador de Agenda del sistema de asistente de horario de un estudiante universitario. Recibís la tarea (con su estimación) y los eventos del calendario real del usuario, y debés sugerir 2 o 3 bloques horarios concretos donde agendarla.

## Cómo evaluar

1. Identificá los huecos libres dentro del horario de trabajo (07:00–22:00).
2. Descartá huecos menores a la estimación mínima (lowMin).
3. Priorizá bloques continuos y sin compromisos cercanos para tareas deep_focus.
4. Si hay expansionRisk alto, buscá bloques con al menos 20 min de margen después.
5. Considerá las ventanas horarias preferidas del learningContext si las hay.
6. Si hay deadline, filtrá bloques que sean anteriores a él.

## Calidad de bloque
- "good": continuo, buena duración, horario favorable para el tipo de trabajo
- "acceptable": disponible pero con alguna limitación (fragmentado, tarde, margen justo)
- "poor": técnicamente libre pero no recomendable

## Schema de salida

{
  "suggestions": [
    {
      "rank": 1,
      "start": "2026-04-26T14:00:00-05:00",
      "end": "2026-04-26T15:45:00-05:00",
      "durationMin": 105,
      "quality": "good",
      "rationale": "Bloque continuo de 3h después de clases, ideal para foco profundo."
    }
  ],
  "warnings": []
}

Respondé ÚNICAMENTE con el objeto JSON, sin texto adicional, sin markdown."""


def _load_learning_context() -> dict:
    try:
        with open(_LEARNING_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return {
            "timeWindowPreferences": data.get("timeWindowPreferences", {}),
            "blockQuality": {
                k: v for k, v in data.get("blockQuality", {}).items()
                if v  # omitir objetos vacíos
            },
        }
    except Exception:
        return {"timeWindowPreferences": {}, "blockQuality": {}}


def evaluate(task: dict, calendar_events: list[dict]) -> dict:
    """
    Analiza el calendario y devuelve sugerencias de bloques horarios para la tarea.
    """
    now = datetime.now(timezone.utc).astimezone()
    estimate = task.get("estimate", {})

    payload = {
        "now": now.isoformat(),
        "task": {
            "normalizedTitle": task.get("normalizedTitle"),
            "modality": task.get("modality"),
            "energy": task.get("energy"),
            "domain": task.get("domain"),
            "workType": task.get("workType"),
            "deadline": task.get("deadline"),
            "estimate": {
                "lowMin": estimate.get("lowMin"),
                "highMin": estimate.get("highMin"),
                "expansionRisk": estimate.get("expansionRisk"),
            },
        },
        "calendarSnapshot": {
            "lookaheadDays": 7,
            "workingHours": {"start": "07:00", "end": "22:00"},
            "existingEvents": calendar_events,
        },
        "learningContext": _load_learning_context(),
    }

    raw = ai_client.complete(
        role="evaluator",
        system_prompt=_SYSTEM_PROMPT,
        user_message=json.dumps(payload, ensure_ascii=False),
        json_mode=True,
    )

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"El evaluador devolvió JSON inválido: {e}\nRespuesta: {raw!r}")

    return {
        "suggestions": result.get("suggestions", []),
        "warnings": result.get("warnings", []),
    }
