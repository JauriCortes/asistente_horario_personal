import json
from pathlib import Path

from core.ai_client import ai_client

_LEARNING_FILE = Path(__file__).parent.parent / "data" / "task-learning.json"

_SYSTEM_PROMPT = """Sos el Estimador del sistema de asistente de horario. Tu única función es generar un rango de duración estimada (mínimo/máximo en minutos) para una tarea ya clasificada.

## Cómo estimar

1. Usá workType, modality y energy como base para la estimación inicial.
2. Si hay multiplicadores en learningContext, multiplicalos sobre la estimación base.
   - Ejemplo: base 60min × courseMultiplier 1.4 → ajustá el rango a ~84min.
   - Si hay varios multiplicadores, aplicalos combinados (producto).
3. Si hay patrones relevantes en learningContext.patterns, consideralos para el expansionRisk y el rango.
4. Sin datos de aprendizaje, estimá desde primeros principios según el tipo de trabajo.

## Valores posibles

**confidence:** high | medium | low
- high: multiplicadores con evidencia sólida + patrones claros
- medium: algunos datos o inferencia razonada
- low: sin datos, estimación completamente genérica

**basis:** initial_inference | learning_adjusted | pattern_based
- initial_inference: sin datos de aprendizaje aplicados
- learning_adjusted: con multiplicadores aplicados
- pattern_based: guiado principalmente por patrones nombrados

**expansionRisk:** high | medium | low | null
- high: el tipo de tarea suele tomar más de lo estimado según historial
- medium: expansión posible
- low: tarea predecible
- null: sin suficientes datos para determinar

## Schema de salida

{
  "lowMin": 45,
  "highMin": 90,
  "confidence": "medium",
  "basis": "initial_inference",
  "appliedMultipliers": {},
  "expansionRisk": null,
  "notes": "Breve explicación de la estimación en español"
}

Respondé ÚNICAMENTE con el objeto JSON, sin texto adicional, sin markdown."""


def _load_learning_context() -> dict:
    try:
        with open(_LEARNING_FILE, encoding="utf-8") as f:
            data = json.load(f)
        accuracy = data.get("estimacionAccuracy", {})
        return {
            "domainMultipliers": accuracy.get("domainMultipliers", {}),
            "courseMultipliers": accuracy.get("courseMultipliers", {}),
            "workTypeMultipliers": accuracy.get("workTypeMultipliers", {}),
            "patterns": [
                {"title": p.get("title", ""), "confidence": p.get("confidence", "")}
                for p in data.get("patterns", [])[:5]
            ],
        }
    except Exception:
        return {
            "domainMultipliers": {},
            "courseMultipliers": {},
            "workTypeMultipliers": {},
            "patterns": [],
        }


def estimate(task: dict) -> dict:
    """
    Genera un rango de duración estimada para una tarea ya clasificada.
    Devuelve el objeto de estimación listo para guardar en task.estimate.
    """
    learning_context = _load_learning_context()

    user_message = json.dumps({
        "task": {
            "normalizedTitle": task.get("normalizedTitle"),
            "type": task.get("type"),
            "domain": task.get("domain"),
            "course": task.get("course"),
            "workType": task.get("workType"),
            "modality": task.get("modality"),
            "energy": task.get("energy"),
            "deadline": task.get("deadline"),
        },
        "learningContext": learning_context,
    }, ensure_ascii=False)

    raw = ai_client.complete(
        role="estimator",
        system_prompt=_SYSTEM_PROMPT,
        user_message=user_message,
        json_mode=True,
    )

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"El estimador devolvió JSON inválido: {e}\nRespuesta: {raw!r}")

    return {
        "lowMin": result.get("lowMin"),
        "highMin": result.get("highMin"),
        "confidence": result.get("confidence"),
        "basis": result.get("basis", "initial_inference"),
        "appliedMultipliers": result.get("appliedMultipliers", {}),
        "expansionRisk": result.get("expansionRisk"),
        "notes": result.get("notes"),
    }
