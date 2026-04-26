import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.ai_client import ai_client

_LEARNING_FILE = Path(__file__).parent.parent / "data" / "task-learning.json"

_SYSTEM_PROMPT = """Sos el Intérprete del sistema de asistente de horario personal de un estudiante universitario. Tu única función es convertir texto libre en un objeto JSON estructurado.

## Vocabulario controlado — usá EXCLUSIVAMENTE estos valores

**type:** task | project | idea | note | reminder

**clarity:** low | medium | high

**domain:** university | work_content_ai | gym | personal_admin | personal_life

**course** (solo si domain=university):
  sistemas_informacion | matematicas_discretas_ii | ingenieria_software_ii | teoria_informacion

**workType:** class_assignment | study_session | exam_prep | project_work | reading | problem_solving | content_creation | content_planning | content_editing | admin | training | recovery | errand

**modality:** deep_focus | light_focus | coordination | physical | passive_review

**energy:** low | medium | high

**deadlineConfidence:** explicit | inferred | null

## Reglas

1. Si no podés inferir un campo con confianza razonable, poné null.
2. Si el texto es muy ambiguo para actuar sobre él, poné needsClarification: true y formulá una clarificationQuestion específica y breve.
3. Si parece un proyecto (múltiples acciones, no accionable directamente), poné type: "project".
4. El campo inferenceNotes debe explicar brevemente tu razonamiento para los campos que inferiste.
5. Respondé ÚNICAMENTE con el objeto JSON, sin texto adicional, sin markdown.

## Schema de salida

{
  "type": "task",
  "normalizedTitle": "Título claro y normalizado en español",
  "clarity": "high",
  "domain": null,
  "course": null,
  "workType": null,
  "modality": null,
  "energy": null,
  "dependsOnExternal": false,
  "deadline": null,
  "deadlineConfidence": null,
  "needsClarification": false,
  "clarificationQuestion": null,
  "inferenceNotes": "Breve descripción del razonamiento"
}"""


def _load_learning_context() -> dict:
    try:
        with open(_LEARNING_FILE, encoding="utf-8") as f:
            data = json.load(f)
        accuracy = data.get("estimacionAccuracy", {})
        return {
            "domainMultipliers": accuracy.get("domainMultipliers", {}),
            "courseMultipliers": accuracy.get("courseMultipliers", {}),
            "patterns": [p.get("title", "") for p in data.get("patterns", [])[:5]],
        }
    except Exception:
        return {"domainMultipliers": {}, "courseMultipliers": {}, "patterns": []}


def interpret(input_text: str, user_id: str = "default", timestamp: str | None = None) -> dict:
    """
    Convierte texto libre en un objeto de tarea estructurado.
    Devuelve el objeto de tarea completo listo para guardar en tasks.json.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).astimezone().isoformat()

    learning_context = _load_learning_context()

    user_message = json.dumps({
        "inputText": input_text,
        "userId": user_id,
        "timestamp": timestamp,
        "learningContext": learning_context,
    }, ensure_ascii=False)

    raw = ai_client.complete(
        role="interpreter",
        system_prompt=_SYSTEM_PROMPT,
        user_message=user_message,
        json_mode=True,
    )

    try:
        interpretation = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"El intérprete devolvió JSON inválido: {e}\nRespuesta: {raw!r}")

    task_id = f"task_{uuid.uuid4().hex[:8]}"

    task = {
        "id": task_id,
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "source": "telegram",
        "inputText": input_text,
        "normalizedTitle": interpretation.get("normalizedTitle", input_text),
        "type": interpretation.get("type", "task"),
        "status": "captured",
        "clarity": interpretation.get("clarity"),
        "domain": interpretation.get("domain"),
        "course": interpretation.get("course"),
        "workType": interpretation.get("workType"),
        "modality": interpretation.get("modality"),
        "energy": interpretation.get("energy"),
        "dependsOnExternal": interpretation.get("dependsOnExternal", False),
        "deadline": interpretation.get("deadline"),
        "estimate": {
            "lowMin": None,
            "highMin": None,
            "confidence": None,
            "basis": None,
        },
        "calendar": {
            "status": "not_scheduled",
            "eventId": None,
            "scheduledStart": None,
            "scheduledEnd": None,
        },
        "outcome": {
            "actualDurationMin": None,
            "completedAt": None,
            "result": None,
            "perceivedDifficulty": None,
            "deferralCount": None,
            "blockCompliance": None,
        },
        "notes": [],
        "tags": [],
        "_meta": {
            "needsClarification": interpretation.get("needsClarification", False),
            "clarificationQuestion": interpretation.get("clarificationQuestion"),
            "inferenceNotes": interpretation.get("inferenceNotes"),
            "deadlineConfidence": interpretation.get("deadlineConfidence"),
        },
    }

    return task
