"""
Hito 1 — test de smoke para ai_client.
Verifica conectividad con cada rol. Los prompts aquí son mínimos a propósito:
los prompts reales con el schema completo vivirán en cada módulo (interpreter.py, etc.).

Uso: python scripts/test_ai_client.py [rol]
     python scripts/test_ai_client.py          # prueba todos los roles
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ai_client import ai_client

ROLES = ["interpreter", "estimator", "evaluator", "conversador", "learning"]

SMOKE_PROMPT = {
    "interpreter": (
        (
            "Eres un clasificador de tareas. "
            "Dado un texto libre, devuelve SOLO un JSON con estos campos: "
            '{"type": "task|project|idea|note|reminder", "clarity": "low|medium|high", "domain": "university|personal_admin|personal_life|gym|work_content_ai"}. '
            "Sin texto adicional, solo el JSON."
        ),
        "hacer ejercicios del taller de discretas",
    ),
    "estimator": (
        (
            "Eres un estimador de tiempo. "
            "Dado el tipo de tarea, devuelve SOLO un JSON con: "
            '{"lowMin": número, "highMin": número, "confidence": "low|medium|high"}. '
            "Sin texto adicional, solo el JSON."
        ),
        "Tarea: ejercicios de resolución de problemas, materia universitaria de matemáticas.",
    ),
    "evaluator": (
        "Eres un evaluador de bloques de agenda. Analiza si un hueco de tiempo es adecuado para una tarea.",
        "Hueco disponible: sábado 2pm–6pm (4 horas continuas). Tarea: foco profundo, 90 minutos. ¿Es un buen bloque?",
    ),
    "conversador": (
        (
            "Eres un asistente de productividad por Telegram. "
            "Sos directo, conversacional y breve. Nunca usás lenguaje robótico."
        ),
        "El usuario acaba de capturar la tarea 'ejercicios del taller de discretas'. Confirmale que quedó registrada.",
    ),
    "learning": (
        (
            "Eres un motor de aprendizaje de estimaciones. "
            "Dado el estimado y el real, devuelve SOLO un JSON con: "
            '{"newMultiplier": número, "adjustment": número, "note": "string breve"}. '
            "Sin texto adicional, solo el JSON."
        ),
        "Estimado: 60 min. Real: 90 min. Multiplicador actual: 1.0.",
    ),
}


def test_role(role: str):
    system, message = SMOKE_PROMPT[role]
    print(f"\n{'═' * 55}")
    print(f"  ROL: {role}")
    print(f"{'═' * 55}")
    print(f"[SYSTEM PROMPT]\n{system}")
    print(f"\n[USER MESSAGE]\n{message}")
    print(f"{'─' * 55}")
    try:
        response = ai_client.complete(role=role, system_prompt=system, user_message=message)
        print(f"[RESPUESTA]\n{response}")
    except Exception as e:
        print(f"[ERROR] {e}")


if __name__ == "__main__":
    roles_to_test = sys.argv[1:] if len(sys.argv) > 1 else ROLES
    for role in roles_to_test:
        if role not in ROLES:
            print(f"Rol desconocido: '{role}'. Roles disponibles: {', '.join(ROLES)}")
            sys.exit(1)
        test_role(role)
    print(f"\n{'═' * 55}")
    print("  Test completado.")
    print(f"{'═' * 55}")
