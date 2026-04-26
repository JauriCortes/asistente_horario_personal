# task-architecture.md

## Propósito

Este documento define cómo se organiza el sistema de tareas a nivel operativo. Si `task-philosophy.md` explica los principios, este archivo explica cómo se conectan los componentes, qué responsabilidad tiene cada uno y cómo fluye una tarea desde su captura hasta su calendarización y aprendizaje posterior.

El objetivo es que el sistema sea comprensible, mantenible y extensible, sin mezclar en un solo lugar principios, estado actual, historial y aprendizaje.

## Idea central del sistema

El sistema existe para transformar capturas rápidas en decisiones temporales reales.

La secuencia general es:

**captura -> aclaración -> estimación -> evaluación de capacidad -> calendarización -> ejecución -> aprendizaje**

En esta arquitectura:

- `tasks.json` funciona como memoria interna del sistema
- Google Calendar funciona como superficie principal de ejecución temporal y como mapa de restricciones ya existentes
- `task-history.json` conserva la evolución de cada tarea
- `task-learning.json` guarda patrones derivados para mejorar decisiones futuras

El usuario no necesita consultar manualmente los archivos JSON. Esos archivos existen para sostener el criterio y la continuidad interna del sistema.

## Componentes del sistema

### 1. `docs/task-philosophy.md`
Documento rector de principios y criterios.

Su función es:
- definir cómo entendemos tareas, proyectos, estimaciones y agenda
- orientar decisiones de diseño
- registrar heurísticas conceptuales que no necesariamente viven como datos estructurados

No debe funcionar como dependencia operativa de lectura constante en cada interacción cotidiana. Su papel es guiar el sistema, no operar como base de datos.

### 2. `data/tasks.json`
Fuente de verdad del estado actual de las tareas capturadas.

Su función es:
- guardar entradas activas dentro del sistema
- reflejar su nivel de claridad actual
- registrar su estimación vigente
- indicar su estado dentro del pipeline hacia calendarización
- mantener vínculo con su representación externa si ya fue calendarizada

Este archivo no existe para ser una interfaz de uso humano diaria, sino como memoria operativa interna.

### 3. `data/task-history.json`
Registro histórico de eventos relevantes en el ciclo de vida de cada tarea.

Su función es:
- conservar la secuencia de cambios
- registrar creación, aclaración, cambio de estimación, evaluación de capacidad, calendarización, reagendado, división, cierre o cancelación
- permitir auditoría y aprendizaje posterior
- ofrecer contexto para entender desviaciones y patrones

No representa el estado actual, sino la evolución.

### 4. `data/task-learning.json`
Capa de aprendizaje derivado.

Su función es:
- guardar patrones agregados
- registrar multiplicadores, sesgos y niveles de confianza
- resumir señales útiles para estimaciones futuras
- almacenar reglas aprendidas a partir del historial observado

No debe contener logs crudos ni duplicar el historial completo.

### 5. Google Calendar
Sistema externo principal para la ejecución temporal y la evaluación de capacidad real.

Su función es:
- alojar bloques reales de tiempo
- representar tareas calendarizadas con fecha, hora y duración
- contener compromisos preexistentes como clases, citas y otros eventos fijos
- servir como mapa de disponibilidad, ocupación y fragmentación del tiempo

Google Calendar no solo recibe tareas calendarizadas. También condiciona qué decisiones temporales son razonables. El sistema debe leer el calendario existente antes de sugerir o asignar nuevos bloques.

### 6. Google Tasks
Sistema externo opcional, no nuclear en la primera versión.

Puede incorporarse más adelante para tareas accionables aún no calendarizadas, listas auxiliares o flujos livianos, pero no forma parte del núcleo de esta arquitectura inicial.

## Principio de separación de capas

El sistema se divide en cuatro capas:

- **filosofía**: principios y criterios
- **operación**: estado actual de las tareas capturadas
- **historia**: eventos pasados
- **aprendizaje**: patrones derivados

Y una superficie externa de ejecución y restricción:

- **calendarización/capacidad**: Google Calendar como lugar donde el trabajo adquiere forma temporal real y donde ya existen límites que deben respetarse

Cada capa responde preguntas distintas:

- filosofía: “¿cómo pensamos esto?”
- operación: “¿qué está pasando con esta tarea?”
- historia: “¿qué ha pasado con ella?”
- aprendizaje: “¿qué estamos aprendiendo?”
- calendarización/capacidad: “¿cuándo puede ocurrir esto en el mundo real?”

## Flujo general de una tarea

### 1. Captura
Una entrada llega desde Telegram u otra interfaz.

La entrada puede ser:
- tarea clara
- proyecto disfrazado de tarea
- idea
- recordatorio
- nota operativa

La captura debe aceptarse con baja fricción.

### 2. Interpretación inicial
El sistema intenta determinar:

- qué tipo de entrada es
- qué tan clara está
- si es estimable o no
- si requiere aclaración
- si conviene dividirla
- si puede avanzar hacia calendarización
- si debe esperar, incubarse o descartarse

### 3. Registro en `tasks.json`
Si la entrada pertenece al sistema activo, se crea o actualiza un objeto en `tasks.json`.

Ese objeto debe representar:
- el estado actual de la entrada
- la mejor interpretación vigente
- la estimación más reciente
- su relación con el pipeline hacia Calendar
- referencias externas si ya existen

### 4. Registro en `task-history.json`
Toda transición relevante genera un evento histórico.

Ejemplos:
- `task_created`
- `task_clarified`
- `estimate_generated`
- `estimate_revised`
- `capacity_evaluated`
- `calendar_suggested`
- `calendar_scheduled`
- `calendar_rescheduled`
- `split_into_subtasks`
- `completed`
- `cancelled`
- `deferred`
- `actual_duration_recorded`

### 5. Consulta de `task-learning.json`
Cuando el sistema necesite estimar mejor o recomendar un buen momento, puede consultar patrones previos como:

- multiplicadores por categoría
- sesgos por tipo de tarea
- franjas horarias favorables
- riesgo histórico de expansión
- confianza por contexto

### 6. Evaluación de capacidad real
Antes de calendarizar, el sistema debe revisar Google Calendar para identificar:

- bloques ya ocupados
- compromisos fijos
- huecos disponibles
- fragmentación del horario
- ventanas razonables según duración y tipo de tarea
- calidad del bloque disponible según energía, contexto y proximidad a otros eventos

No todo espacio libre es un buen espacio. Un hueco corto entre clases puede servir para una tarea administrativa, pero no necesariamente para una tarea de foco profundo.

### 7. Calendarización en Google Calendar
Cuando una tarea ya tiene suficiente claridad y existe una ventana razonable, el sistema busca convertirla en una decisión temporal concreta en Google Calendar.

Una tarea calendarizada debe idealmente conservar:
- referencia al evento externo
- bloque estimado
- momento sugerido o elegido
- estado de sincronización conceptual con el sistema interno

### 8. Ejecución y retroalimentación
Cuando la tarea se completa, se mueve, se cancela o toma más o menos de lo esperado:
- se actualiza `tasks.json`
- se agrega evento en `task-history.json`
- si hay datos útiles, se reflejan luego en `task-learning.json`

### 9. Actualización de aprendizaje
Periódicamente, o tras suficiente evidencia acumulada, el sistema actualiza `task-learning.json`.

Si de ese aprendizaje emerge una heurística estable o un cambio de criterio, también puede actualizarse `task-philosophy.md`.

## Meta por defecto de una tarea válida

La meta por defecto de una tarea válida y accionable es terminar convertida en una decisión de calendario.

Eso no significa que toda captura deba calendarizarse automáticamente. Algunas entradas pueden resultar ser:
- ideas
- proyectos demasiado amplios
- notas
- tareas bloqueadas
- entradas descartables

Pero toda tarea realmente accionable debería tender hacia una resolución temporal concreta, no quedarse indefinidamente como pendiente abstracto.

## Reglas de autoridad

Para evitar confusión, cada componente tiene autoridad sobre un tipo distinto de información.

- `task-philosophy.md`
  - autoridad sobre principios y criterios interpretativos

- `tasks.json`
  - autoridad sobre el estado actual y la posición de cada tarea en el pipeline

- `task-history.json`
  - autoridad sobre la secuencia de eventos y cambios

- `task-learning.json`
  - autoridad sobre patrones derivados y reglas ajustadas

- Google Calendar
  - autoridad sobre los bloques temporales reales ya calendarizados y sobre los compromisos existentes que limitan capacidad

## Reglas de consistencia

### 1. Captura no implica calendarización inmediata
Una entrada puede existir en el sistema antes de estar suficientemente clara para estimarse o calendarizarse.

### 2. Calendarización requiere claridad mínima
Para reservar tiempo real, la tarea debe tener suficiente definición como para justificar duración, momento y contexto.

### 3. Calendarización requiere revisar capacidad real
Ninguna recomendación de agenda debe ignorar los bloques ya existentes en Google Calendar.

### 4. El estado actual no debe depender del historial para uso diario
Aunque la historia conserva la película completa, `tasks.json` debe permitir operar sin reconstruir todo desde eventos.

### 5. El aprendizaje orienta, no impone
Las reglas aprendidas deben mejorar sugerencias y estimaciones, pero no bloquear rígidamente decisiones humanas.

### 6. No todo aprendizaje merece cambiar la filosofía
Solo patrones relativamente estables o cambios reales de criterio deben subir a `task-philosophy.md`.

## Qué queda fuera por ahora

Este documento no define todavía:
- schema exacto de cada JSON
- formato técnico de IDs
- estrategia detallada de sincronización con Google Calendar
- comandos exactos de Telegram
- manejo de Google Tasks en una versión futura

Esos detalles pueden definirse después en `task-schema.md` o en implementación.

## Evolución

Este archivo debe actualizarse cuando:
- cambie el flujo entre captura y calendarización
- aparezcan nuevos componentes
- se redefina la autoridad de alguna capa
- el sistema incorpore Google Tasks u otros destinos
- cambie la estrategia de almacenamiento
