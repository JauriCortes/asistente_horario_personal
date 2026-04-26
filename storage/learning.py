import json
import os
from datetime import datetime, timezone
from pathlib import Path

from core.ai_client import ai_client

_LEARNING_FILE = Path(__file__).parent.parent / "data" / "task-learning.json"
_ALPHA = 0.3  # EMA: 30% peso a la observación nueva


def _load() -> dict:
    with open(_LEARNING_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    tmp = _LEARNING_FILE.with_suffix(".tmp")
    data["lastUpdatedAt"] = datetime.now(timezone.utc).isoformat()
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _LEARNING_FILE)


def _ema(current: float, new_value: float) -> float:
    return round((1 - _ALPHA) * current + _ALPHA * new_value, 3)


def _compute_ratio(task: dict) -> float | None:
    """Ratio real/estimado. 1.0 = exacto, 1.4 = tardó 40% más."""
    actual = task.get("outcome", {}).get("actualDurationMin")
    est = task.get("estimate", {})
    low, high = est.get("lowMin"), est.get("highMin")
    if not actual or not low or not high:
        return None
    return round(actual / ((low + high) / 2), 3)


def _compute_updates(task: dict, data: dict) -> dict:
    """Calcula los nuevos valores de cada sección en Python puro."""
    updates = {}
    outcome = task.get("outcome", {})
    ratio = _compute_ratio(task)

    # ── estimacionAccuracy ─────────────────────────────────────
    if ratio:
        accuracy = data.get("estimacionAccuracy", {})
        dm = dict(accuracy.get("domainMultipliers", {}))
        cm = dict(accuracy.get("courseMultipliers", {}))
        wm = dict(accuracy.get("workTypeMultipliers", {}))

        if (domain := task.get("domain")):
            dm[domain] = _ema(dm.get(domain, 1.0), ratio)
        if (course := task.get("course")):
            cm[course] = _ema(cm.get(course, 1.0), ratio)
        if (wtype := task.get("workType")):
            wm[wtype] = _ema(wm.get(wtype, 1.0), ratio)

        updates["estimacionAccuracy"] = {
            **accuracy,
            "domainMultipliers": dm,
            "courseMultipliers": cm,
            "workTypeMultipliers": wm,
        }

    # ── frictionPatterns ───────────────────────────────────────
    if outcome.get("deferralCount", 0) > 0:
        friction = dict(data.get("frictionPatterns", {}))
        wt_rates = dict(friction.get("deferralRateByWorkType", {}))
        cl_rates = dict(friction.get("deferralRateByClarityLevel", {}))

        if (wtype := task.get("workType")):
            wt_rates[wtype] = _ema(wt_rates.get(wtype, 0.0), 1.0)
        if (clarity := task.get("clarity")):
            cl_rates[clarity] = _ema(cl_rates.get(clarity, 0.0), 1.0)

        updates["frictionPatterns"] = {
            **friction,
            "deferralRateByWorkType": wt_rates,
            "deferralRateByClarityLevel": cl_rates,
        }

    # ── cognitiveLoad ──────────────────────────────────────────
    difficulty = outcome.get("perceivedDifficulty")
    if difficulty and (course := task.get("course")):
        cog = dict(data.get("cognitiveLoad", {}))
        bias = dict(cog.get("perceivedDifficultyBiasByCourse", {}))
        entry = bias.get(course, {"harderRate": 0.0, "sampleSize": 0})
        n = entry["sampleSize"] + 1
        is_harder = 1.0 if difficulty == "harder" else 0.0
        bias[course] = {
            "harderRate": round(((entry["harderRate"] * entry["sampleSize"]) + is_harder) / n, 3),
            "sampleSize": n,
        }
        updates["cognitiveLoad"] = {**cog, "perceivedDifficultyBiasByCourse": bias}

    # ── blockQuality ───────────────────────────────────────────
    compliance = outcome.get("blockCompliance")
    if compliance and compliance != "unscheduled":
        sched_start = task.get("calendar", {}).get("scheduledStart", "")
        bq = dict(data.get("blockQuality", {}))
        is_on = 1.0 if compliance == "on_schedule" else 0.0
        try:
            dt = datetime.fromisoformat(sched_start)
            dow = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][dt.weekday()]
            cr_dow = dict(bq.get("complianceRateByDayOfWeek", {}))
            cr_dow[dow] = _ema(cr_dow.get(dow, 0.5), is_on)
            bq["complianceRateByDayOfWeek"] = cr_dow
        except Exception:
            pass
        updates["blockQuality"] = bq

    # ── stats globales ─────────────────────────────────────────
    stats = dict(data.get("stats", {}))
    stats["completedTasks"] = stats.get("completedTasks", 0) + 1
    stats["totalDeferrals"] = stats.get("totalDeferrals", 0) + (outcome.get("deferralCount") or 0)
    updates["stats"] = stats

    return updates


_FEEDBACK_SYSTEM = """Sos el asistente de horario de un estudiante universitario. Acabás de cerrar una tarea y actualizar el aprendizaje del sistema. Generá un mensaje breve y natural que le diga al usuario lo que aprendiste.

Reglas:
- 1-2 oraciones máximo.
- Tono informal, tuteo.
- Si tardó más del estimado (ratio > 1.1): mencionalo y decí que lo ajustás para la próxima.
- Si tardó menos (ratio < 0.9): mencioná que fue más rápido.
- Si la dificultad fue "harder": mencionalo brevemente.
- Si es de universidad, mencioná la materia.
- No uses frases de chatbot ni empieces con "Perfecto" o "De acuerdo".
- Respondé solo el mensaje."""


def update_learning(task: dict) -> str:
    """
    Actualiza task-learning.json con los patrones de la tarea cerrada.
    Devuelve el mensaje de feedback para el usuario.
    """
    data = _load()
    updates = _compute_updates(task, data)

    for section, value in updates.items():
        data[section] = value
    _save(data)

    ratio = _compute_ratio(task)
    outcome = task.get("outcome", {})

    feedback_ctx = json.dumps({
        "task": task.get("normalizedTitle"),
        "course": task.get("course"),
        "domain": task.get("domain"),
        "estimateMin": task.get("estimate", {}).get("lowMin"),
        "estimateMax": task.get("estimate", {}).get("highMin"),
        "actualDurationMin": outcome.get("actualDurationMin"),
        "ratio": ratio,
        "perceivedDifficulty": outcome.get("perceivedDifficulty"),
        "deferralCount": outcome.get("deferralCount", 0),
        "blockCompliance": outcome.get("blockCompliance"),
    }, ensure_ascii=False)

    return ai_client.complete(
        role="conversador",
        system_prompt=_FEEDBACK_SYSTEM,
        user_message=feedback_ctx,
    )
