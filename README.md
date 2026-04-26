# Asistente de Horario Personal

A Telegram bot that captures tasks in natural language, estimates duration using an adaptive learning engine, reads your real Google Calendar, suggests time blocks, and schedules events — all from a chat message.

Built from scratch as a personal productivity tool and AI systems exercise.

---

## How it works

You send a message like:

> *"hacer los ejercicios del taller de Discretas"*

The bot:
1. Interprets the task (subject, type, deadline, clarity)
2. Estimates duration based on your personal history (`75–120 min`)
3. Reads your Google Calendar for the next 7 days
4. Suggests 2 real available time blocks
5. Schedules the event once you confirm
6. Learns from actual time spent to improve future estimates

```
You:  hacer los ejercicios del taller de Discretas

Bot:  Calculo unos 75–120 minutos, con Discretas a veces se extiende.
      Mirando tu semana: sábado 27 a las 2pm (3h libre, ideal para foco)
      o domingo 28 a las 9am. ¿Cuál te viene mejor?

You:  la primera

Bot:  Listo, quedó agendado el sábado 27 a las 2pm.
```

---

## Architecture

### Multi-agent AI with fallback chain

Six specialized AI roles, each with its own system prompt and model configuration:

| Role | Job |
|---|---|
| `interpreter` | Extracts structured task data from raw text |
| `estimator` | Estimates duration range with confidence level |
| `evaluator` | Analyzes calendar snapshot and suggests time blocks |
| `conversador` | Generates natural, context-aware reply messages |
| `learning` | Writes human-readable feedback after task closure |
| `chat` | Answers system queries and general productivity questions |

Each role has an independent fallback chain configured in `config/models.yaml`:

```
Gemini 2.5 Pro → Gemini 2.5 Flash → OpenAI Codex → Claude → Ollama (local)
```

If a model fails (quota, timeout, auth error), the next one takes over automatically — no code changes needed to swap models.

### Adaptive learning engine

After you close a task with actual duration and perceived difficulty, the system updates per-subject and per-work-type multipliers using **Exponential Moving Average** (α = 0.3):

```python
new_multiplier = 0.7 * current + 0.3 * (actual / estimated)
```

Four learning signals: actual duration, perceived difficulty, deferral count, calendar block compliance.

The math runs in pure Python — LLMs only generate the human-readable feedback message, never the arithmetic.

### Conversational state machine

Each user session tracks up to 5 concurrent states:

```
pending_schedule      → waiting for slot confirmation
pending_completion    → waiting for actual duration
pending_difficulty    → waiting for difficulty rating
pending_clarification → waiting for task clarification
```

Incoming messages are routed through an 8-step priority chain. Mid-flow interruptions (e.g. sending a new task while confirming a schedule) are handled without losing either context.

Intent classification for scheduling responses uses a dedicated LLM call:

```
"la primera"     → confirm   (rank 1)
"¿y el domingo?" → alternatives
"ese no"         → reject
"más tarde"      → defer
"tengo que leer el cap 3" → new_task (fall through to capture)
```

---

## Project structure

```
├── bot.py                  # Entry point, job queue, command handlers
├── core/
│   ├── ai_client.py        # Model-agnostic LLM client with fallback chain
│   ├── interpreter.py      # Text → structured task object
│   ├── estimator.py        # Task → duration estimate
│   ├── capacity.py         # Calendar snapshot → time block suggestions
│   ├── scheduler.py        # Confirmed slot → Google Calendar event
│   ├── proactivity.py      # Daily/weekly message generation
│   └── chat.py             # General chat fallback with system context
├── handlers/
│   ├── capture.py          # Main message handler (8-step router)
│   ├── schedule.py         # Slot confirmation flow
│   └── review.py           # Task closure (/done, /cancel, natural language)
├── storage/
│   ├── tasks.py            # CRUD on tasks.json (atomic writes)
│   ├── history.py          # Append-only event log
│   └── learning.py         # EMA multiplier updates
├── integrations/
│   └── gcal.py             # Google Calendar via gws CLI
├── config/
│   └── models.yaml         # Provider/model config per role
└── data/                   # Runtime JSON files (gitignored)
```

---

## Setup

**Requirements:** Python 3.11+, a Telegram bot token, `gws` CLI for Google Calendar.

```bash
git clone https://github.com/JauriCortes/asistente_horario_personal.git
cd asistente_horario_personal
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Add your TELEGRAM_BOT_TOKEN to .env

python bot.py
```

Configure which models to use per role in `config/models.yaml` — the system works with any OpenAI-compatible API, the Anthropic SDK, or a local Ollama instance.

---

## Milestones

The project was built incrementally through 9 defined milestones, from bare LLM integration to a fully conversational flow. See [`milestones.json`](milestones.json) for the full breakdown.

| # | Milestone | Status |
|---|---|---|
| 1 | Technical foundation (AI client, model config) | ✅ |
| 2 | Task capture and interpretation | ✅ |
| 3 | Telegram bot operational | ✅ |
| 4 | Duration estimation integrated | ✅ |
| 5 | Google Calendar integration | ✅ |
| 6 | Full scheduling flow | ✅ |
| 7 | Task closure and learning engine | ✅ |
| 8 | Proactive daily/weekly messages | ✅ |
| 9 | Robust conversational state machine | 🔄 |
