# task-schema.md

## Propósito

Este documento define la estructura inicial de los archivos JSON del sistema de tareas. Su objetivo es dar consistencia a la implementación sin cerrar demasiado pronto decisiones que todavía pueden evolucionar.

La versión inicial debe priorizar:
- claridad
- facilidad de lectura y escritura
- flexibilidad para iterar
- compatibilidad con el flujo definido en `task-architecture.md`

## Convenciones generales

### Fechas y horas
- usar formato ISO 8601
- incluir zona horaria cuando aplique
- ejemplo: `2026-04-19T03:00:00-05:00`

### IDs
- cada tarea debe tener un `id` único
- cada evento histórico debe tener un `id` único
- los IDs pueden ser UUIDs o strings legibles con prefijo, mientras sean únicos

### Versionado
Cada archivo puede incluir un campo de versión de schema para facilitar migraciones futuras.

---

## 1. `data/tasks.json`

### Propósito
Representa el estado actual de las tareas activas dentro del sistema.

### Estructura sugerida

```json
{
  "schemaVersion": 1,
  "tasks": []
}
```

### Objeto de tarea

```json
{
  "id": "task_001",
  "createdAt": "2026-04-19T03:00:00-05:00",
  "updatedAt": "2026-04-19T03:10:00-05:00",
  "source": "telegram",
  "inputText": "hacer ejercicios del taller de discretas",
  "normalizedTitle": "Hacer ejercicios del taller de Matemáticas Discretas II",
  "type": "task",
  "status": "captured",
  "clarity": "high",
  "domain": "university",
  "course": "matematicas_discretas_ii",
  "workType": "problem_solving",
  "modality": "deep_focus",
  "energy": "high",
  "dependsOnExternal": false,
  "estimate": {
    "lowMin": 60,
    "highMin": 90,
    "confidence": "medium",
    "basis": "initial_inference"
  },
  "calendar": {
    "status": "not_scheduled",
    "eventId": null,
    "scheduledStart": null,
    "scheduledEnd": null
  },
  "outcome": {
    "actualDurationMin": null,
    "completedAt": null,
    "result": null,
    "perceivedDifficulty": null,
    "deferralCount": null,
    "blockCompliance": null
  },
  "notes": [],
  "tags": ["universidad", "discretas", "taller"]
}
```

### Campos clave

- `id`: identificador único
- `inputText`: texto original capturado
- `normalizedTitle`: versión más clara o estandarizada
- `type`: tipo de entrada
- `status`: estado actual en el pipeline
- `clarity`: qué tan clara está la tarea
- `domain`: área principal de vida o trabajo
- `course`: materia, si aplica
- `workType`: tipo de esfuerzo
- `modality`: forma de ejecución
- `energy`: energía requerida
- `dependsOnExternal`: si depende de terceros
- `estimate`: estimación actual vigente
- `calendar`: estado de calendarización
- `outcome`: resultado final con las 4 señales de aprendizaje
- `notes`: observaciones breves
- `tags`: etiquetas libres

### Valores sugeridos para `type`

- `task`
- `project`
- `idea`
- `note`
- `reminder`

### Valores sugeridos para `status`

- `captured`
- `clarifying`
- `ready_to_schedule`
- `scheduled`
- `in_progress`
- `completed`
- `cancelled`
- `deferred`
- `blocked`
- `incubated`

### Valores sugeridos para `clarity`

- `low`
- `medium`
- `high`

### Valores sugeridos para `energy`

- `low`
- `medium`
- `high`

---

## Campos de categorización

### `domain`
Representa el frente principal al que pertenece la tarea.

Valores iniciales sugeridos:
- `university`
- `work_content_ai`
- `gym`
- `personal_admin`
- `personal_life`

### `course`
Se usa solo cuando `domain = university`.

Valores iniciales sugeridos:
- `sistemas_informacion`
- `matematicas_discretas_ii`
- `ingenieria_software_ii`
- `teoria_informacion`

### `workType`
Representa qué tipo de trabajo se está haciendo.

Valores iniciales sugeridos:
- `class_assignment`
- `study_session`
- `exam_prep`
- `project_work`
- `reading`
- `problem_solving`
- `content_creation`
- `content_planning`
- `content_editing`
- `admin`
- `training`
- `recovery`
- `errand`

### `modality`
Representa cómo se ejecuta la tarea en la práctica.

Valores iniciales sugeridos:
- `deep_focus`
- `light_focus`
- `coordination`
- `physical`
- `passive_review`

---

## 2. `data/task-history.json`

### Propósito
Guardar la secuencia histórica de eventos relevantes asociados a las tareas.

### Estructura sugerida

```json
{
  "schemaVersion": 1,
  "events": []
}
```

### Objeto de evento

```json
{
  "id": "evt_001",
  "taskId": "task_001",
  "timestamp": "2026-04-19T03:00:00-05:00",
  "type": "task_created",
  "data": {
    "source": "telegram",
    "inputText": "hacer ejercicios del taller de discretas"
  }
}
```

### Campos clave

- `id`: identificador único del evento
- `taskId`: tarea asociada
- `timestamp`: momento del evento
- `type`: tipo de evento
- `data`: payload variable según el evento

### Tipos sugeridos de evento

- `task_created`
- `task_clarified`
- `estimate_generated`
- `estimate_revised`
- `capacity_evaluated`
- `calendar_suggested`
- `calendar_scheduled`
- `calendar_rescheduled`
- `calendar_cancelled`
- `task_started`
- `task_completed`
- `task_cancelled`
- `task_deferred`
- `task_blocked`
- `split_into_subtasks`
- `actual_duration_recorded`
- `perceived_difficulty_recorded`
- `block_compliance_recorded`

### Ejemplo de evento de estimación

```json
{
  "id": "evt_002",
  "taskId": "task_001",
  "timestamp": "2026-04-19T03:03:00-05:00",
  "type": "estimate_generated",
  "data": {
    "lowMin": 60,
    "highMin": 90,
    "confidence": "medium",
    "basis": "initial_inference",
    "domain": "university",
    "course": "matematicas_discretas_ii",
    "workType": "problem_solving"
  }
}
```

### Ejemplo de cierre de tarea con señales de aprendizaje

```json
{
  "id": "evt_004",
  "taskId": "task_001",
  "timestamp": "2026-04-19T12:00:00-05:00",
  "type": "task_completed",
  "data": {
    "actualDurationMin": 140,
    "perceivedDifficulty": "harder",
    "deferralCount": 2,
    "blockCompliance": "on_schedule"
  }
}
```

### Valores para `perceivedDifficulty`

- `as_expected` — fue como esperaba
- `harder` — más difícil de lo esperado
- `easier` — más fácil de lo esperado

### Valores para `blockCompliance`

- `on_schedule` — se hizo en el bloque agendado
- `same_day_late` — se hizo el mismo día pero después del bloque
- `different_day` — se completó en un día distinto al agendado
- `unscheduled` — se completó sin haber tenido un bloque agendado

---

### Ejemplo de evento de calendarización

```json
{
  "id": "evt_003",
  "taskId": "task_001",
  "timestamp": "2026-04-19T03:05:00-05:00",
  "type": "calendar_scheduled",
  "data": {
    "eventId": "google_cal_abc123",
    "scheduledStart": "2026-04-19T10:00:00-05:00",
    "scheduledEnd": "2026-04-19T11:30:00-05:00"
  }
}
```

---

## 3. `data/task-learning.json`

### Propósito
Guardar los 28 patrones derivados de las 4 señales de cierre (duración real, dificultad percibida, postergaciones, cumplimiento del bloque), cruzadas con los atributos de cada tarea. Estos patrones informan estimaciones futuras y decisiones de agenda.

### Las 4 señales de cierre

| Señal | Campo en `outcome` | Cómo se captura |
|---|---|---|
| Duración real | `actualDurationMin` | El usuario la reporta al cerrar |
| Dificultad percibida | `perceivedDifficulty` | Una pregunta al cierre (as_expected / harder / easier) |
| Postergaciones | `deferralCount` | Derivado automáticamente del historial |
| Cumplimiento del bloque | `blockCompliance` | Derivado de scheduledStart vs completedAt |

### Estructura completa

```json
{
  "schemaVersion": 2,
  "lastUpdatedAt": null,

  "estimacionAccuracy": {
    "domainMultipliers": {},
    "courseMultipliers": {},
    "workTypeMultipliers": {},
    "confidenceCalibration": {},
    "timeOfDayEffect": {},
    "energyLevelEffect": {}
  },

  "frictionPatterns": {
    "deferralRateByWorkType": {},
    "deferralRateByClarityLevel": {},
    "cancellationRateByDomain": {},
    "perpetualPendingThreshold": 3
  },

  "blockQuality": {
    "complianceRateByTimeWindow": {},
    "complianceRateByDayOfWeek": {},
    "fragmentationPenalty": {},
    "avgStartDelayByContext": {}
  },

  "cognitiveLoad": {
    "perceivedDifficultyBiasByDomain": {},
    "perceivedDifficultyBiasByCourse": {},
    "durationDifficultyMismatch": {},
    "difficultyTrendByCourse": {}
  },

  "compositePatterns": {
    "optimalConditions": {},
    "riskClusters": []
  },

  "predictiveSignals": {
    "earlyDeferralCancellationRate": null,
    "lowClarityDeferralRate": null,
    "deadlineProximityComplianceEffect": {}
  },

  "timeWindowPreferences": {},

  "patterns": [],

  "stats": {
    "completedTasks": 0,
    "averageEstimateAccuracy": null,
    "averageBlockCompliance": null,
    "last30DaysCompleted": 0,
    "totalDeferrals": 0
  }
}
```

### Descripción de secciones

#### `estimacionAccuracy` — 6 patrones de precisión de estimación
Aprende cuánto se desvían las estimaciones de la realidad según el contexto.

```json
"domainMultipliers": { "university": 1.2, "gym": 1.0 },
"courseMultipliers": { "matematicas_discretas_ii": 1.4 },
"workTypeMultipliers": { "problem_solving": 1.4, "exam_prep": 1.5 },
"confidenceCalibration": {
  "medium": { "avgAccuracy": 0.72, "sampleSize": 18 }
},
"timeOfDayEffect": {
  "08:00-11:00": 0.95,
  "14:00-17:00": 1.15
},
"energyLevelEffect": {
  "high_task_in_low_energy_slot": 1.3
}
```

#### `frictionPatterns` — 5 patrones de fricción y procrastinación
Aprende qué tipos de tarea generan resistencia antes de hacerse.

```json
"deferralRateByWorkType": { "exam_prep": 0.6, "admin": 0.2 },
"deferralRateByClarityLevel": { "low": 0.75, "medium": 0.35, "high": 0.12 },
"cancellationRateByDomain": { "personal_admin": 0.18, "university": 0.08 },
"perpetualPendingThreshold": 3
```

#### `blockQuality` — 5 patrones de calidad de bloques
Aprende cuándo y dónde se cumplen mejor los bloques agendados.

```json
"complianceRateByTimeWindow": {
  "08:00-11:00": 0.82, "14:00-17:00": 0.61
},
"complianceRateByDayOfWeek": {
  "monday": 0.75, "saturday": 0.68, "friday": 0.45
},
"fragmentationPenalty": {
  "event_within_30min_after": 1.2
},
"avgStartDelayByContext": {
  "after_class": 18,
  "fresh_morning": 5
}
```

#### `cognitiveLoad` — 4 patrones de carga cognitiva
Aprende cuándo las tareas se sienten más difíciles de lo que el tiempo indica.

```json
"perceivedDifficultyBiasByDomain": {
  "university": "harder_than_expected"
},
"perceivedDifficultyBiasByCourse": {
  "matematicas_discretas_ii": { "harderRate": 0.65, "sampleSize": 11 }
},
"durationDifficultyMismatch": {
  "on_time_but_felt_harder": { "rate": 0.3, "implication": "high_cognitive_load" }
},
"difficultyTrendByCourse": {
  "matematicas_discretas_ii": "increasing"
}
```

#### `compositePatterns` — 4 patrones compuestos y alertas
Combinaciones de señales que indican condiciones óptimas o de riesgo.

```json
"optimalConditions": {
  "problem_solving": {
    "timeWindow": "08:00-11:00",
    "dayOfWeek": "tuesday",
    "precedingActivity": "gym",
    "avgAccuracy": 0.91
  }
},
"riskClusters": [
  {
    "id": "cluster_001",
    "description": "Tarea larga + percibida difícil + pospuesta 2+ veces",
    "implication": "bloqueo real, no mala estimación",
    "evidenceCount": 4
  }
]
```

#### `predictiveSignals` — 4 señales predictivas
Señales tempranas que predicen el comportamiento de la tarea antes de completarla.

```json
"earlyDeferralCancellationRate": 0.45,
"lowClarityDeferralRate": 0.72,
"deadlineProximityComplianceEffect": {
  "within_2_days": { "complianceRate": 0.88, "expansionRate": 1.25 }
}
```

#### `patterns`
Hallazgos semi-estructurados con evidencia suficiente para ser nombrados.

```json
[
  {
    "id": "pattern_001",
    "category": "estimacionAccuracy",
    "title": "Las tareas de Discretas tipo problem_solving superan consistentemente el límite alto estimado",
    "confidence": "medium",
    "evidenceCount": 7,
    "firstObservedAt": "2026-04-19T03:00:00-05:00"
  }
]
```

#### `stats`
Métricas globales del sistema.

```json
{
  "completedTasks": 24,
  "averageEstimateAccuracy": 0.72,
  "averageBlockCompliance": 0.68,
  "last30DaysCompleted": 11,
  "totalDeferrals": 38
}
```

---

## Reglas mínimas de consistencia

### 1. Toda tarea en `tasks.json` debe tener `id`
Sin excepción.

### 2. Toda tarea debe tener `domain`
Es uno de los ejes principales de clasificación del sistema.

### 3. Si `domain = university`, la tarea debería tener `course`
Salvo que todavía esté demasiado ambigua al momento de captura.

### 4. Toda tarea debería tener `workType` cuando ya esté lista para estimarse o calendarizarse
Puede faltar en captura temprana, pero no debería faltar en una tarea madura del pipeline.

### 5. Todo evento en `task-history.json` debe apuntar a una tarea válida
Si no existe la tarea, el evento no debe registrarse o debe tratarse explícitamente como excepción.

### 6. `tasks.json` guarda el presente, no toda la historia
No debe crecer indefinidamente con detalle histórico redundante.

### 7. `task-learning.json` solo guarda conocimiento derivado
No debe duplicar tareas ni eventos completos.

### 8. Si una tarea está `scheduled`, su bloque de calendario debe estar reflejado en `calendar`
Al menos con `status`, `scheduledStart`, `scheduledEnd` y, si existe, `eventId`.

---

## Decisiones abiertas

Estas decisiones se dejan abiertas para versiones futuras:

- formato exacto de IDs
- manejo de subtareas
- archivo único de history vs partición por mes
- estrategia de archivo para tareas completadas
- sincronización bidireccional o unidireccional con Google Calendar
- campos más finos para dependencia, fricción o prioridad
- reglas de inferencia automática para `domain`, `course`, `workType` y `modality`

## Criterio de diseño para v1

La v1 del schema debe ser:
- suficientemente estructurada para operar
- suficientemente simple para editar a mano si hace falta
- suficientemente flexible para cambiar sin romper todo
- suficientemente cercana a la vida real del usuario como para aprender patrones útiles
