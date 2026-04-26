"""
Prueba del flujo de captura, interpretación y estimación (Hitos 2-4).

Uso:
  python scripts/test_capture.py "hacer ejercicios del taller de discretas"
  python scripts/test_capture.py "revisar correos" --dry-run
"""
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.estimator import estimate
from core.interpreter import interpret
from storage import history, tasks


def _event_id() -> str:
    return f"evt_{uuid.uuid4().hex[:8]}"


def run(input_text: str, dry_run: bool = False) -> None:
    print(f"\n{'='*60}")
    print(f"  CAPTURA: {input_text!r}")
    print(f"{'='*60}\n")

    print("[1/4] Interpretando...")
    task = interpret(input_text)
    meta = task.get("_meta", {})

    if meta.get("needsClarification"):
        print(f"  ⚠ Pide aclaración: {meta['clarificationQuestion']}")
        return

    print("[2/4] Estimando duración...")
    est = estimate(task)
    task["estimate"] = est

    print("[3/4] Resultado:\n")
    print(f"  Título:       {task.get('normalizedTitle')}")
    print(f"  Dominio:      {task.get('domain')}  |  Materia: {task.get('course')}")
    print(f"  Tipo trabajo: {task.get('workType')}  |  Modalidad: {task.get('modality')}")
    print(f"  Claridad:     {task.get('clarity')}  |  Energía: {task.get('energy')}")
    if task.get("deadline"):
        print(f"  Deadline:     {task['deadline']} ({meta.get('deadlineConfidence', '?')})")
    print(f"\n  Estimación:   {est['lowMin']}–{est['highMin']} min  "
          f"[confianza: {est['confidence']}  |  base: {est['basis']}]")
    if est.get("expansionRisk"):
        print(f"  Expansión:    riesgo {est['expansionRisk']}")
    if est.get("notes"):
        print(f"  Notas:        {est['notes']}")
    if meta.get("inferenceNotes"):
        print(f"\n  Inferencia:   {meta['inferenceNotes']}")

    if dry_run:
        print("\n[DRY RUN] No se escribió nada.")
        return

    print("\n[4/4] Guardando...")
    tasks.add_task(task)

    history.append_event({
        "id": _event_id(),
        "taskId": task["id"],
        "timestamp": task["createdAt"],
        "type": "task_created",
        "data": {"source": task["source"], "inputText": input_text,
                 "inferenceNotes": meta.get("inferenceNotes")},
    })
    history.append_event({
        "id": _event_id(),
        "taskId": task["id"],
        "timestamp": task["updatedAt"],
        "type": "estimate_generated",
        "data": {
            "lowMin": est["lowMin"], "highMin": est["highMin"],
            "confidence": est["confidence"], "basis": est["basis"],
            "domain": task.get("domain"), "course": task.get("course"),
            "workType": task.get("workType"),
        },
    })

    print(f"  Tarea guardada → id: {task['id']}")
    print()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]

    if not args:
        print("Uso: python scripts/test_capture.py \"texto de la tarea\" [--dry-run]")
        sys.exit(1)

    run(input_text=args[0], dry_run="--dry-run" in flags)
