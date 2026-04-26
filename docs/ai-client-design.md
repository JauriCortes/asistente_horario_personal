# ai-client-design.md

## Propósito

Este documento define el diseño del cliente centralizado de IA (`core/ai_client.py`). Todo componente del sistema que necesite llamar a un modelo de lenguaje debe hacerlo exclusivamente a través de este módulo.

---

## Principio central

**Una sola puerta de entrada para todas las llamadas a IA.**

Ningún handler, ningún módulo de core ni ningún módulo de storage llama directamente a una API de LLM. Todos importan `ai_client` y usan su interfaz. Eso significa que cambiar de proveedor, de modelo o de estrategia de llamada es un cambio en un solo lugar.

---

## Arquitectura

```
bot.py
handlers/
core/
  interpreter.py  ──┐
  estimator.py    ──┤
  capacity.py     ──┼──► core/ai_client.py ──► proveedor A (Ollama, OpenAI, etc.)
  scheduler.py    ──┤                      └──► proveedor B (si se configura otro)
storage/
  learning.py     ──┘
```

---

## Configuración de modelos

Los modelos se definen en un archivo `config/models.yaml` externo al código. El cliente lo lee al inicializarse.

### Estructura del archivo

```yaml
# config/models.yaml

providers:
  local_ollama:
    type: openai_compatible
    api_base: http://localhost:11434/v1
    api_key: ollama

  openai_cloud:
    type: openai_compatible
    api_base: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}

  anthropic_cloud:
    type: anthropic
    api_key: ${ANTHROPIC_API_KEY}

roles:
  interpreter:
    provider: local_ollama
    model: qwen2.5-coder:7b
    temperature: 0.1
    max_tokens: 1024

  estimator:
    provider: local_ollama
    model: qwen2.5-coder:7b
    temperature: 0.1
    max_tokens: 512

  evaluator:
    provider: local_ollama
    model: qwen2.5-coder:7b
    temperature: 0.2
    max_tokens: 2048

  conversador:
    provider: local_ollama
    model: qwen2.5-coder:7b
    temperature: 0.4
    max_tokens: 512

  learning:
    provider: local_ollama
    model: qwen2.5-coder:7b
    temperature: 0.1
    max_tokens: 1024
```

Cambiar de modelo para un rol es editar una línea en este archivo. No se toca código.

---

## Interfaz del cliente

```python
# core/ai_client.py

class AIClient:
    def __init__(self, config_path: str = "config/models.yaml"):
        ...

    def complete(
        self,
        role: str,
        system_prompt: str,
        user_message: str,
        json_mode: bool = False,
    ) -> str:
        """
        Llama al modelo asignado al rol indicado.
        Retorna el contenido del mensaje de respuesta como string.
        Si json_mode=True, fuerza respuesta en JSON cuando el proveedor lo soporta.
        """
        ...

    def complete_messages(
        self,
        role: str,
        messages: list[dict],
        json_mode: bool = False,
    ) -> str:
        """
        Versión multi-turn. Recibe lista de mensajes en formato OpenAI
        ({"role": "user"/"assistant"/"system", "content": "..."}).
        """
        ...
```

### Uso desde cualquier módulo

```python
from core.ai_client import ai_client

# llamada simple
result = ai_client.complete(
    role="interpreter",
    system_prompt=INTERPRETER_SYSTEM_PROMPT,
    user_message=raw_input_text,
    json_mode=True,
)

# llamada multi-turn (para el Conversador)
result = ai_client.complete_messages(
    role="conversador",
    messages=conversation_history,
)
```

El módulo expone una instancia singleton `ai_client` para que no haya que instanciar el cliente en cada módulo.

---

## Proveedores soportados

El cliente traduce internamente cada llamada al formato del proveedor configurado.

| Tipo de proveedor | Descripción | Ejemplos compatibles |
|---|---|---|
| `openai_compatible` | API REST compatible con el formato OpenAI `/v1/chat/completions` | Ollama, LM Studio, vLLM, OpenAI, Groq, Together AI, cualquier proxy |
| `anthropic` | API nativa de Anthropic | API de Anthropic directamente |

La mayoría de proveedores (incluyendo modelos locales vía Ollama) son compatibles con el formato OpenAI, así que `openai_compatible` cubre casi todos los casos.

---

## Manejo de errores

El cliente debe manejar de forma transparente:

- **Timeout**: reintentar N veces con backoff exponencial antes de propagar el error
- **Respuesta no parseable como JSON** cuando `json_mode=True`: loggear y propagar error específico para que el rol llamante lo maneje
- **Proveedor no disponible**: propagar error claro con el nombre del rol y proveedor afectado, para que el handler de Telegram pueda responder al usuario con un mensaje apropiado

---

## Lo que el cliente NO hace

- No construye prompts. Cada módulo (interpreter, estimator, etc.) es responsable de sus propios system prompts.
- No parsea ni valida el JSON de respuesta. Eso le corresponde al módulo que llama.
- No guarda historial de conversación. El estado conversacional vive en el handler.
- No decide qué rol usar. El llamante siempre especifica el rol.

---

## Evolución

Este diseño permite agregar en el futuro:

- **Fallback automático**: si el proveedor primario falla, intentar con uno secundario
- **Caché de respuestas**: para prompts deterministas (estimaciones sobre tareas idénticas)
- **Logging de uso**: registrar tokens consumidos por rol para auditar costos
- **Modo mock**: proveedor fake para tests sin depender de ninguna API externa
