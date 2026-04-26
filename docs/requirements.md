# requirements.md

## Propósito

Este documento recoge las historias de usuario, requisitos funcionales y requisitos no funcionales del asistente de horario desde la perspectiva del usuario humano. Define qué debe poder hacer el sistema y bajo qué condiciones debe hacerlo.

---

## Historias de usuario

### Captura

**HU-01**
Como usuario, quiero enviar una tarea por Telegram con texto libre y sin estructura fija, para capturar pendientes rápidamente sin interrumpir mi flujo.

**HU-02**
Como usuario, quiero que el sistema acepte cualquier tipo de entrada (tarea, idea, proyecto, recordatorio, nota) sin rechazarla por estar incompleta, para no perder nada en el momento de captura.

**HU-03**
Como usuario, quiero que el sistema me confirme brevemente lo que entendió de mi captura, para saber que fue registrada correctamente sin necesidad de revisar archivos.

---

### Aclaración y clasificación

**HU-04**
Como usuario, quiero que el sistema me haga preguntas de aclaración solo cuando realmente sean necesarias, para no sentir que lleno formularios cada vez que capturo algo.

**HU-05**
Como usuario, quiero que el sistema clasifique automáticamente mis tareas por dominio, materia y tipo de trabajo cuando pueda inferirlo del contexto, para no tener que categorizar todo manualmente.

**HU-06**
Como usuario, quiero que el sistema me avise cuando una captura parece ser un proyecto y no una tarea simple, para poder dividirla en acciones concretas antes de intentar agendarla.

---

### Estimación

**HU-07**
Como usuario, quiero recibir una estimación de tiempo para cada tarea con un rango (mínimo/máximo) y un nivel de confianza, para tomar mejores decisiones al planificar sin confiar en números falsos.

**HU-08**
Como usuario, quiero que las estimaciones mejoren con el tiempo a partir de mis duraciones reales, para que el sistema aprenda cómo trabajo yo específicamente.

**HU-09**
Como usuario, quiero poder corregir una estimación antes de confirmar el agendado, para mantener control sobre las decisiones de agenda.

---

### Agendado

**HU-10**
Como usuario, quiero que el sistema revise mi Google Calendar antes de sugerirme un horario, para que las sugerencias sean realistas y no ignoren mis compromisos existentes.

**HU-11**
Como usuario, quiero que el sistema distinga entre bloques de tiempo útiles y bloques cortos entre clases, para que no me sugiera hacer trabajo de foco profundo en huecos de 20 minutos.

**HU-12**
Como usuario, quiero recibir una sugerencia de bloque horario con día, hora y duración, y poder confirmarla, modificarla o rechazarla desde Telegram, para tener la decisión final sobre cuándo ocurre cada tarea.

**HU-13**
Como usuario, quiero que al confirmar un agendado se cree automáticamente el evento en Google Calendar, para no tener que hacerlo manualmente.

**HU-14**
Como usuario, quiero poder posponer, cancelar o reagendar una tarea desde Telegram, para mantener el sistema actualizado sin entrar a Google Calendar directamente.

---

### Ejecución y cierre

**HU-15**
Como usuario, quiero marcar una tarea como completada desde Telegram indicando cuánto tiempo tomó realmente, para que el sistema registre el resultado y aprenda de él.

**HU-16**
Como usuario, quiero que si no indico la duración real al completar una tarea, el sistema me la solicite de forma breve, para no perder esos datos de aprendizaje.

**HU-17**
Como usuario, quiero poder cancelar una tarea con una razón opcional, para que el sistema registre el patrón si me cancelo con frecuencia en cierto tipo de tareas.

---

### Revisión y seguimiento

**HU-18**
Como usuario, quiero que el sistema me recuerde de forma proactiva las tareas capturadas que llevan mucho tiempo sin avanzar, para no tener un backlog muerto que nunca reviso.

**HU-19**
Como usuario, quiero poder preguntarle al bot qué tengo pendiente hoy o esta semana, para tener un resumen rápido sin abrir Google Calendar.

**HU-20**
Como usuario, quiero recibir una revisión periódica (semanal) de lo que completé, lo que se movió y los patrones que el sistema detectó, para tener conciencia real de cómo estoy gestionando mi tiempo.

---

## Requisitos funcionales

### RF-01 — Captura por Telegram
El sistema debe recibir mensajes de texto libre del usuario a través de un bot de Telegram y procesarlos como nuevas capturas.

### RF-02 — Interpretación automática de capturas
El sistema debe determinar, a partir del texto libre, el tipo de entrada (tarea, proyecto, idea, nota, recordatorio), su nivel de claridad, dominio, materia si aplica, tipo de trabajo y modalidad de ejecución.

### RF-03 — Confirmación de captura
El sistema debe responder al usuario con una confirmación breve de lo que entendió, sin exigir validación explícita cuando la confianza de interpretación es alta.

### RF-04 — Aclaración conversacional
Cuando la claridad de una captura sea baja, el sistema debe iniciar un flujo de aclaración con preguntas mínimas y específicas hasta tener suficiente información para operar.

### RF-05 — Estimación por rangos
El sistema debe generar para cada tarea accionable un rango de duración estimada (mínimo/máximo en minutos) junto con un nivel de confianza y la base de la estimación.

### RF-06 — Uso de aprendizaje en estimaciones
El sistema debe consultar `task-learning.json` al estimar, aplicando multiplicadores por dominio, materia y tipo de trabajo cuando existan con suficiente evidencia.

### RF-07 — Consulta de capacidad real en Google Calendar
Antes de sugerir un bloque horario, el sistema debe leer los eventos existentes en Google Calendar del usuario para identificar compromisos fijos, huecos disponibles y su calidad según duración, energía requerida y fragmentación.

### RF-08 — Sugerencia de bloque horario
El sistema debe proponer al usuario una o más opciones de bloque horario con día, hora de inicio y duración estimada, justificando brevemente por qué ese momento es razonable.

### RF-09 — Confirmación y creación de evento en Google Calendar
Al confirmar un bloque, el sistema debe crear automáticamente un evento en Google Calendar con título, hora de inicio y hora de fin.

### RF-10 — Registro de estado en tasks.json
El sistema debe mantener actualizado el objeto de tarea en `tasks.json` en cada transición relevante del pipeline: captura, aclaración, estimación, agendado, reagendado, completado, cancelado, diferido.

### RF-11 — Registro histórico en task-history.json
Cada evento relevante en el ciclo de vida de una tarea debe generar un nuevo registro en `task-history.json` con timestamp, tipo de evento y datos del contexto.

### RF-12 — Cierre de tarea con las 4 señales de aprendizaje
Al marcar una tarea como completada, el sistema debe registrar en `tasks.json` las cuatro señales de aprendizaje: duración real (`actualDurationMin`), dificultad percibida (`perceivedDifficulty`), cantidad de postergaciones (`deferralCount`, derivado del historial), y cumplimiento del bloque (`blockCompliance`, derivado de scheduledStart vs completedAt). El sistema debe solicitar brevemente la duración real y la dificultad percibida si el usuario no las provee al cerrar.

### RF-13 — Actualización de los 6 grupos de patrones de aprendizaje
Tras el cierre de una tarea con las 4 señales completas, el sistema debe actualizar `task-learning.json` en los grupos de patrones que correspondan: precisión de estimación, fricción y procrastinación, calidad de bloques, carga cognitiva, patrones compuestos y señales predictivas. Los ajustes deben hacerse mediante promedio ponderado para no sobreajustar con eventos aislados.

### RF-18 — Derivación automática de postergaciones y cumplimiento
Al cerrar una tarea, el sistema debe calcular automáticamente `deferralCount` contando eventos `task_deferred` en el historial de esa tarea, y `blockCompliance` comparando `scheduledStart` del último evento `calendar_scheduled` con el `completedAt` real. El usuario no debe calcular ni reportar estos valores manualmente.

### RF-14 — Diferimiento y cancelación
El sistema debe permitir al usuario diferir o cancelar una tarea desde Telegram, actualizando su estado y registrando el evento en el historial.

### RF-15 — Consulta de agenda
El sistema debe responder a preguntas del tipo "¿qué tengo hoy?" o "¿qué tengo esta semana?" combinando datos de Google Calendar y `tasks.json`.

### RF-16 — Recordatorio proactivo de tareas estancadas
El sistema debe detectar tareas que llevan más de N días sin avanzar y enviar un recordatorio proactivo al usuario por Telegram.

### RF-17 — Resumen periódico
El sistema debe generar y enviar al usuario un resumen semanal con tareas completadas, tareas movidas, tasa de precisión de estimaciones y patrones detectados.

---

## Requisitos no funcionales

### RNF-01 — Tiempo de respuesta en captura
El sistema debe responder al mensaje de captura del usuario en menos de 4 segundos en condiciones normales de red.

### RNF-02 — Disponibilidad continua
El bot debe estar operativo de forma continua (24/7), tolerando reinicios limpios sin pérdida de estado gracias a la persistencia en archivos JSON.

### RNF-03 — Idioma
Toda comunicación con el usuario debe ser en español. La interpretación interna puede operar en el idioma más eficiente para el modelo, pero las respuestas al usuario deben ser siempre en español.

### RNF-04 — Eficiencia de costos de API
El sistema debe usar el modelo de menor costo suficiente para cada operación: modelos pequeños para clasificación y confirmación rápida, modelos más capaces solo para razonamiento complejo como evaluación de capacidad o detección de patrones.

### RNF-05 — Persistencia local
El estado del sistema debe vivir en archivos JSON locales. No se debe depender de una base de datos externa para el funcionamiento núcleo.

### RNF-06 — Tolerancia a fallos de Google Calendar
Si Google Calendar no está disponible temporalmente, el sistema debe poder capturar y clasificar tareas igualmente, postergando la evaluación de capacidad hasta que la conexión se restablezca.

### RNF-07 — Idempotencia en escritura de JSON
Las operaciones de escritura sobre los archivos JSON deben ser seguras ante reinicios inesperados, evitando corrupción de estado por escrituras parciales.

### RNF-08 — Extensibilidad
La arquitectura debe permitir incorporar nuevas fuentes de captura (voz, otros canales) o nuevos destinos de calendarización (Google Tasks) sin rediseñar el núcleo del sistema.

### RNF-09 — Trazabilidad
Toda decisión relevante del sistema (interpretación, estimación, sugerencia de bloque) debe quedar registrada en el historial de forma que sea auditable y comprensible sin necesidad de logs de depuración.
