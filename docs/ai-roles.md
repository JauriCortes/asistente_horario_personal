# ai-roles.md

## Propósito

Este documento define los roles de inteligencia artificial del sistema como si fueran personas reales contratadas para funciones específicas. Cada rol tiene una responsabilidad clara, un contrato de entrada y salida, y sus propias historias de usuario que describen lo que necesita del sistema para hacer bien su trabajo.

El objetivo de este enfoque es diseñar con claridad las interfaces entre componentes antes de implementarlos, y pensar en los modelos de IA no como herramientas intercambiables sino como colaboradores con roles, necesidades y limitaciones concretas.

El sistema es **model-agnostic**: qué modelo concreto ocupa cada rol se define en configuración externa, no en código. Las llamadas a IA pasan siempre por `core/ai_client.py`, que traduce el rol a proveedor/modelo según esa configuración.

---

## Equipo de IA

| Rol | Perfil requerido | Responsabilidad principal |
|---|---|---|
| El Intérprete | Rápido, salida estructurada (JSON) | Convierte texto libre en objetos de tarea estructurados |
| El Estimador | Rápido, salida estructurada (JSON) | Genera rangos de duración con niveles de confianza |
| El Evaluador de Agenda | Razonamiento complejo, contexto largo | Analiza el calendario real y sugiere bloques horarios |
| El Conversador | Lenguaje natural fluido, multi-turn | Gestiona el flujo de diálogo con el usuario en Telegram |
| El Motor de Aprendizaje | Rápido, salida estructurada (JSON) | Deriva patrones y actualiza multiplicadores a partir de cierres |

El perfil de cada rol orienta qué tipo de modelo asignarle en la configuración, pero no impone un proveedor ni una familia de modelos específica.

---

## Rol 1 — El Intérprete

**Perfil requerido:** rápido, salida JSON estructurada
**Componente:** `core/interpreter.py`

### Responsabilidad

Recibe el texto crudo que el usuario envió por Telegram y lo convierte en un objeto de tarea estructurado. Decide qué tipo de entrada es, qué tan clara está, y extrae todos los atributos que puede inferir con confianza razonable.

### Contrato de entrada

```json
{
  "inputText": "hacer ejercicios del taller de discretas para el lunes",
  "userId": "...",
  "timestamp": "2026-04-25T10:00:00-05:00",
  "learningContext": {
    "domainMultipliers": {},
    "courseMultipliers": {},
    "patterns": []
  }
}
```

### Contrato de salida

```json
{
  "type": "task",
  "normalizedTitle": "Hacer ejercicios del taller de Matemáticas Discretas II",
  "clarity": "high",
  "domain": "university",
  "course": "matematicas_discretas_ii",
  "workType": "problem_solving",
  "modality": "deep_focus",
  "energy": "high",
  "dependsOnExternal": false,
  "deadline": "2026-04-28",
  "deadlineConfidence": "inferred",
  "needsClarification": false,
  "clarificationQuestion": null,
  "inferenceNotes": "El usuario menciona 'el lunes', se interpreta como deadline relativo."
}
```

### Historias de usuario del Intérprete

**HU-INT-01**
Como Intérprete, quiero recibir el texto original completo sin preprocesamiento, para no perder señales lingüísticas que me ayuden a inferir tipo, dominio o urgencia.

**HU-INT-02**
Como Intérprete, quiero recibir los patrones actuales de `task-learning.json` (dominios frecuentes, materias activas, tipos de trabajo comunes), para contextualizar mis inferencias con la realidad del usuario y no hacer suposiciones genéricas.

**HU-INT-03**
Como Intérprete, quiero poder devolver `needsClarification: true` con una pregunta específica cuando la entrada sea demasiado ambigua, para no inventar información que podría distorsionar el resto del pipeline.

**HU-INT-04**
Como Intérprete, quiero tener acceso a los valores válidos para cada campo (`domain`, `course`, `workType`, `modality`) en forma de vocabulario controlado, para devolver valores compatibles con el schema y no crear variantes inconsistentes.

**HU-INT-05**
Como Intérprete, quiero poder expresar cuándo una entrada parece ser un proyecto y no una tarea, para que el sistema avise al usuario antes de intentar estimarla o agendarla como si fuera una acción simple.

**HU-INT-06**
Como Intérprete, quiero que mis inferencias sean trazables mediante el campo `inferenceNotes`, para que el sistema pueda registrar en el historial cómo llegué a esa interpretación y sea auditable si algo sale mal.

---

## Rol 2 — El Estimador

**Perfil requerido:** rápido, salida JSON estructurada
**Componente:** `core/estimator.py`

### Responsabilidad

Recibe un objeto de tarea ya clasificado y genera una estimación de duración en forma de rango (mínimo/máximo en minutos) con nivel de confianza y base de la estimación. Usa los multiplicadores de aprendizaje cuando están disponibles.

### Contrato de entrada

```json
{
  "task": {
    "normalizedTitle": "Hacer ejercicios del taller de Matemáticas Discretas II",
    "type": "task",
    "domain": "university",
    "course": "matematicas_discretas_ii",
    "workType": "problem_solving",
    "modality": "deep_focus",
    "energy": "high"
  },
  "learningContext": {
    "domainMultipliers": { "university": 1.2 },
    "courseMultipliers": { "matematicas_discretas_ii": 1.4 },
    "workTypeMultipliers": { "problem_solving": 1.4 },
    "patterns": [
      {
        "title": "Las tareas de discretas tipo problem solving suelen expandirse",
        "confidence": "medium"
      }
    ]
  }
}
```

### Contrato de salida

```json
{
  "lowMin": 75,
  "highMin": 120,
  "confidence": "medium",
  "basis": "learning_adjusted",
  "appliedMultipliers": {
    "course": 1.4,
    "workType": 1.4
  },
  "expansionRisk": "high",
  "notes": "Tarea de resolución de problemas en Matemáticas Discretas con historial de expansión. Se aplican multiplicadores de materia y tipo de trabajo."
}
```

### Historias de usuario del Estimador

**HU-EST-01**
Como Estimador, quiero recibir el objeto de tarea ya clasificado con todos sus atributos (domain, course, workType, modality, energy), para basar mi estimación en la naturaleza real del trabajo y no solo en el título.

**HU-EST-02**
Como Estimador, quiero recibir los multiplicadores de `task-learning.json` organizados por domain, course y workType, para ajustar mi estimación base con el historial real del usuario y no usar promedios genéricos.

**HU-EST-03**
Como Estimador, quiero poder indicar un nivel de confianza diferenciado (`high`, `medium`, `low`) y explicar la base de la estimación (`initial_inference`, `learning_adjusted`, `pattern_based`), para que el usuario y el sistema sepan cuánto confiar en el número.

**HU-EST-04**
Como Estimador, quiero poder señalar riesgo de expansión (`expansionRisk`) cuando los patrones de aprendizaje indiquen que ese tipo de tarea suele tomar más de lo estimado, para que el Evaluador de Agenda considere un margen adicional al buscar bloques.

**HU-EST-05**
Como Estimador, quiero que cuando no haya suficientes datos de aprendizaje para un contexto, pueda igualmente dar una estimación razonada desde primeros principios, sin bloquear el pipeline por falta de historial.

**HU-EST-06**
Como Estimador, quiero poder devolver una estimación distinta si el usuario me dice que la tarea tiene un deadline próximo, para que la urgencia informe el rango y no solo el tipo de trabajo.

---

## Rol 3 — El Evaluador de Agenda

**Perfil requerido:** razonamiento complejo, contexto largo
**Componente:** `core/capacity.py`

### Responsabilidad

Recibe la tarea con su estimación y el estado actual del Google Calendar del usuario, y determina qué bloques horarios son razonables para agendar esa tarea considerando disponibilidad real, calidad del bloque, tipo de trabajo y energía requerida.

### Contrato de entrada

```json
{
  "task": {
    "normalizedTitle": "Hacer ejercicios del taller de Matemáticas Discretas II",
    "modality": "deep_focus",
    "energy": "high",
    "estimate": { "lowMin": 75, "highMin": 120, "expansionRisk": "high" },
    "deadline": "2026-04-28"
  },
  "calendarSnapshot": {
    "lookaheadDays": 5,
    "existingEvents": [
      {
        "title": "Clase Matemáticas Discretas II",
        "start": "2026-04-26T08:00:00-05:00",
        "end": "2026-04-26T10:00:00-05:00"
      }
    ],
    "workingHours": { "start": "07:00", "end": "22:00" }
  },
  "learningContext": {
    "timeWindowPreferences": {
      "problem_solving": ["08:00-11:00"],
      "deep_focus": ["08:00-12:00"]
    },
    "modalityAdjustments": {
      "deep_focus_between_classes": 1.4
    }
  }
}
```

### Contrato de salida

```json
{
  "suggestions": [
    {
      "rank": 1,
      "start": "2026-04-26T14:00:00-05:00",
      "end": "2026-04-26T15:45:00-05:00",
      "durationMin": 105,
      "quality": "good",
      "rationale": "Bloque continuo de 3 horas después de clases. Coincide con ventana preferida para foco profundo. Sin compromisos fijos cercanos."
    },
    {
      "rank": 2,
      "start": "2026-04-27T09:00:00-05:00",
      "end": "2026-04-27T10:45:00-05:00",
      "durationMin": 105,
      "quality": "acceptable",
      "rationale": "Mañana disponible, dentro de ventana horaria preferida, aunque hay un evento posterior a las 11:00 que podría generar presión de tiempo."
    }
  ],
  "warnings": [
    "La tarea tiene riesgo de expansión alto. Se recomiendan bloques con margen posterior."
  ]
}
```

### Historias de usuario del Evaluador de Agenda

**HU-EVAL-01**
Como Evaluador de Agenda, quiero recibir un snapshot real del calendario del usuario con los eventos de los próximos días, para no sugerir bloques que ya están ocupados o que queden fragmentados entre compromisos.

**HU-EVAL-02**
Como Evaluador de Agenda, quiero conocer la modalidad y el nivel de energía requeridos por la tarea, para descartar bloques de tiempo que no son adecuados para ese tipo de trabajo aunque estén formalmente libres.

**HU-EVAL-03**
Como Evaluador de Agenda, quiero tener acceso a las preferencias horarias aprendidas (`timeWindowPreferences`) del usuario por tipo de trabajo, para priorizar franjas donde históricamente ese trabajo sale mejor.

**HU-EVAL-04**
Como Evaluador de Agenda, quiero recibir el rango de estimación completo incluyendo el `expansionRisk`, para reservar bloques con margen suficiente y no ajustar exactamente al mínimo estimado.

**HU-EVAL-05**
Como Evaluador de Agenda, quiero poder expresar la calidad de cada bloque sugerido (good, acceptable, poor) con una razón explícita, para que el usuario tome una decisión informada y no solo vea horarios.

**HU-EVAL-06**
Como Evaluador de Agenda, quiero poder indicar advertencias cuando ningún bloque disponible sea realmente bueno antes del deadline, para que el sistema alerte al usuario sobre riesgo de no completar a tiempo.

**HU-EVAL-07**
Como Evaluador de Agenda, quiero que si el deadline es inminente y no hay bloques de calidad alta disponibles, pueda sugerir bloques de menor calidad con advertencia explícita antes que no sugerir nada.

---

## Rol 4 — El Conversador

**Perfil requerido:** lenguaje natural fluido, manejo de contexto conversacional
**Componente:** `handlers/` (todos)

### Responsabilidad

Gestiona el flujo de diálogo con el usuario en Telegram. Decide cuándo confirmar, cuándo preguntar, cuándo presentar opciones y cómo formular cada mensaje de forma que sea natural, breve y útil. Es la voz del sistema hacia el usuario.

### Contrato de entrada

```json
{
  "conversationStage": "schedule_suggestion",
  "userId": "...",
  "task": { "...": "objeto tarea completo" },
  "suggestions": [ "...lista de bloques del Evaluador..." ],
  "pendingQuestion": null,
  "userLastMessage": "sí, agéndala"
}
```

### Contrato de salida

```json
{
  "messageToUser": "Listo. Agendé 'Ejercicios del taller de Discretas' el sábado 26 de abril de 2:00 pm a 3:45 pm. ¿Algo más?",
  "nextStage": "idle",
  "actionRequired": {
    "type": "create_calendar_event",
    "data": { "...": "datos del bloque confirmado" }
  }
}
```

### Historias de usuario del Conversador

**HU-CONV-01**
Como Conversador, quiero tener acceso al estado completo de la conversación en curso (etapa, tarea, sugerencias pendientes, última respuesta del usuario), para no perder el hilo y no repetir preguntas que ya fueron respondidas.

**HU-CONV-02**
Como Conversador, quiero saber en qué etapa del pipeline está la interacción actual (captura, aclaración, confirmación de estimación, elección de bloque, confirmación de agendado, cierre), para formular el mensaje correcto en cada momento.

**HU-CONV-03**
Como Conversador, quiero poder recibir resultados del Intérprete, el Estimador y el Evaluador de Agenda como contexto, para traducirlos al usuario en lenguaje natural sin que el usuario tenga que entender la estructura interna.

**HU-CONV-04**
Como Conversador, quiero poder manejar respuestas ambiguas del usuario ("sí", "no sé", "más tarde", "ese no") y mapearlas a intenciones concretas, para no bloquear el flujo por falta de estructura en las respuestas.

**HU-CONV-05**
Como Conversador, quiero poder formular mensajes cortos para confirmaciones simples y mensajes más elaborados cuando el usuario necesita elegir entre opciones, para no abrumar con texto en cada interacción.

**HU-CONV-06**
Como Conversador, quiero poder salir del flujo actual si el usuario envía una captura nueva en medio de otra interacción, para no forzar completar un flujo anterior si el usuario ya cambió de atención.

**HU-CONV-07**
Como Conversador, quiero poder pedir la duración real cuando el usuario marca una tarea como completada sin darla, con un mensaje que sea natural y no parezca un formulario obligatorio.

---

## Rol 5 — El Motor de Aprendizaje

**Perfil requerido:** rápido, salida JSON estructurada
**Componente:** `storage/learning.py`

### Responsabilidad

Se activa cuando una tarea se cierra con las 4 señales de aprendizaje disponibles: duración real, dificultad percibida, postergaciones y cumplimiento del bloque. Analiza estas señales cruzadas con los atributos de la tarea (domain, course, workType, modality, energy, hora, día) y actualiza los 6 grupos de patrones en `task-learning.json`.

### Contrato de entrada

```json
{
  "closedTask": {
    "id": "task_001",
    "domain": "university",
    "course": "matematicas_discretas_ii",
    "workType": "problem_solving",
    "modality": "deep_focus",
    "energy": "high",
    "clarity": "high",
    "estimate": { "lowMin": 75, "highMin": 120, "confidence": "medium" },
    "calendar": {
      "scheduledStart": "2026-04-19T10:00:00-05:00",
      "scheduledEnd": "2026-04-19T11:30:00-05:00"
    },
    "outcome": {
      "actualDurationMin": 140,
      "completedAt": "2026-04-19T12:20:00-05:00",
      "perceivedDifficulty": "harder",
      "deferralCount": 2,
      "blockCompliance": "same_day_late"
    }
  },
  "currentLearning": {
    "estimacionAccuracy": {
      "courseMultipliers": { "matematicas_discretas_ii": 1.4 }
    },
    "frictionPatterns": {
      "deferralRateByWorkType": { "problem_solving": 0.35 }
    },
    "patterns": []
  },
  "historicalContext": {
    "recentClosedTasksForThisCourse": 6,
    "recentClosedTasksForThisWorkType": 14
  }
}
```

### Contrato de salida

```json
{
  "updatedSections": {
    "estimacionAccuracy": {
      "courseMultipliers": { "matematicas_discretas_ii": 1.46 },
      "timeOfDayEffect": { "10:00-12:00": 1.12 }
    },
    "frictionPatterns": {
      "deferralRateByWorkType": { "problem_solving": 0.38 }
    },
    "blockQuality": {
      "complianceRateByTimeWindow": { "10:00-12:00": 0.55 }
    },
    "cognitiveLoad": {
      "perceivedDifficultyBiasByCourse": {
        "matematicas_discretas_ii": { "harderRate": 0.72, "sampleSize": 7 }
      }
    }
  },
  "newPatterns": [
    {
      "id": "pattern_007",
      "category": "estimacionAccuracy",
      "title": "Las tareas de problem_solving en Discretas superan el límite alto estimado y se perciben más difíciles",
      "confidence": "medium",
      "evidenceCount": 7,
      "firstObservedAt": "2026-04-19T12:20:00-05:00"
    }
  ],
  "summary": "Multiplicador de Discretas ajustado de 1.4 a 1.46. Tarea tomó 17% más del límite alto. Percibida como 'harder' (72% de las veces en esta materia). 2 postergaciones previas y cumplimiento fuera de bloque: señal de fricción sostenida en problem_solving."
}
```

### Historias de usuario del Motor de Aprendizaje

**HU-LEARN-01**
Como Motor de Aprendizaje, quiero recibir las 4 señales de cierre completas (duración real, dificultad percibida, postergaciones, cumplimiento del bloque) junto con todos los atributos de la tarea, para cruzarlos y actualizar los 6 grupos de patrones con contexto real.

**HU-LEARN-02**
Como Motor de Aprendizaje, quiero poder actualizar cada grupo de patrones de forma independiente, para que un ajuste en `frictionPatterns` no afecte lo aprendido en `estimacionAccuracy`.

**HU-LEARN-03**
Como Motor de Aprendizaje, quiero tener acceso al historial reciente de tareas similares cerradas, para determinar si un desvío es aislado o una señal sostenida antes de mover un multiplicador.

**HU-LEARN-04**
Como Motor de Aprendizaje, quiero poder detectar y nombrar patrones compuestos cuando varias señales convergen (ej: duración extendida + percibida difícil + múltiples postergaciones), para que el sistema distinga entre mala estimación y bloqueo real.

**HU-LEARN-05**
Como Motor de Aprendizaje, quiero actualizar las señales predictivas (tasa de cancelación post-postergación temprana, efecto de proximidad al deadline) para que el sistema pueda advertir antes de que ocurran estos patrones.

**HU-LEARN-06**
Como Motor de Aprendizaje, quiero poder indicar cuando un patrón alcanza suficiente estabilidad para sugerir revisión de `task-philosophy.md`, para que el conocimiento acumulado pueda volverse parte del criterio rector del sistema.

**HU-LEARN-07**
Como Motor de Aprendizaje, quiero producir un resumen legible de cada actualización que mencione qué señales fueron relevantes y por qué, para que el informe semanal del usuario explique el aprendizaje sin jerga técnica.

**HU-LEARN-08**
Como Motor de Aprendizaje, quiero poder operar con señales parciales (ej: sin dificultad percibida), actualizando solo los grupos de patrones para los que hay datos suficientes, para no bloquear el aprendizaje cuando falta alguna señal.

---

## Principios de diseño del equipo de IA

### Separación de responsabilidades
Cada rol tiene una función específica y no debe hacer el trabajo de otro. El Intérprete no estima. El Estimador no agenda. El Conversador no aprende.

### Contratos explícitos
Cada rol recibe exactamente lo que necesita para operar y devuelve exactamente lo que el siguiente paso necesita. Nada más.

### Modelos correctos para cada trabajo
Operaciones rápidas y de salida estructurada van a modelos ligeros y veloces. Razonamiento sobre contexto complejo, calendarios y conversación natural van a modelos con mayor capacidad. La asignación concreta vive en la configuración, no en el código.

### Trazabilidad por diseño
Todo rol debe poder explicar su decisión. Las notas de inferencia, bases de estimación, rationales de bloques y resúmenes de aprendizaje no son opcionales: son parte del contrato de salida.

### El humano tiene la última palabra
Ningún rol toma decisiones definitivas. El Evaluador sugiere, no agenda. El Motor ajusta, no impone. El Conversador propone, no actúa sin confirmación.
