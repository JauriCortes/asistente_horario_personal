# Personal Schedule Assistant

A Telegram bot that captures tasks in natural language, estimates duration using an adaptive learning engine, reads your real Google Calendar, suggests time blocks, and schedules events — all from a chat message.

Built from scratch as a personal productivity tool and AI systems exercise.

**Powered by a multi-agent fallback chain:** Gemini 2.5 Pro → Gemini 2.5 Flash → OpenAI Codex → Claude → Ollama (local). Six specialized AI agents, each with its own role and system prompt. If any model fails — quota, timeout, auth error — the next one takes over automatically, no code changes needed.

---

## Full conversation example

```
You:   make the exercises for the Discrete Math workshop

Bot:   Looks like the Discrete Math problem set. I'd estimate 75–120 min —
       that subject tends to run long. Checking your week:

       Option 1: Saturday the 27th at 2pm — 3h free block, good for focused work
       Option 2: Sunday the 28th at 9am — also clear

       Which one works better for you?

You:   actually, is there anything on Friday afternoon?

Bot:   Looking for Friday slots... Found one: Friday the 26th at 4pm, about
       2h free before your 6pm class. A bit tight for 120min but workable
       if you move fast. Want that one instead?

You:   yeah, go with Friday

Bot:   Done — "Discrete Math exercises" scheduled Friday the 26th at 4pm.

---

[Two days later, you message the bot]

You:   done, took me 140 minutes

Bot:   Noted. That's 20 min over the high estimate — I'll adjust Discrete Math
       upward for next time. How hard did it feel? (easy / normal / hard)

You:   pretty hard

Bot:   Got it. Updating the difficulty weight too. Next Discrete Math estimate
       will be more realistic.
```

---

## Multi-agent architecture

Six specialized AI roles, each with its own system prompt and independent model config:

| Role | Job |
|---|---|
| `interpreter` | Extracts structured task data from raw text |
| `estimator` | Estimates duration range with confidence and expansion risk |
| `evaluator` | Analyzes calendar snapshot and scores available time blocks |
| `conversador` | Generates natural, context-aware reply messages |
| `learning` | Writes human-readable feedback after task closure |
| `chat` | Answers system queries and general productivity questions |

### Fallback chain

Every role has its own fallback sequence defined in `config/models.yaml`:

```
Gemini 2.5 Pro → Gemini 2.5 Flash → OpenAI Codex → Claude → Ollama (local)
```

The AI client tries each provider in order. Quota exceeded, token expired, model unavailable — it falls through to the next one silently. Swapping models requires only a YAML edit, no code changes.

---

## Adaptive learning engine

After you close a task with actual duration and perceived difficulty, the system updates per-subject and per-work-type multipliers using **Exponential Moving Average** (α = 0.3):

```python
new_multiplier = 0.7 * current + 0.3 * (actual / estimated)
```

Four learning signals feed the engine: actual duration, perceived difficulty, deferral count, calendar block compliance.

The math runs in pure Python — LLMs only generate the human-readable feedback message, never touch the arithmetic. This prevents hallucinated multiplier updates.

After enough data, estimates for "Discrete Math problem sets" become meaningfully different from "reading assignments" — because they are.

---

## Conversational state machine

Each user session tracks up to 5 concurrent states:

```
pending_schedule      → waiting for slot confirmation
pending_completion    → waiting for actual duration
pending_difficulty    → waiting for difficulty rating
pending_clarification → waiting for task clarification
```

Incoming messages are routed through an 8-step priority chain. A new task sent mid-scheduling flow doesn't break the session — the bot captures it, then returns to the pending slot. Intent classification for ambiguous replies uses a dedicated LLM call:

```
"the first one"          → confirm   (rank 1)
"anything on Sunday?"    → alternatives
"none of those work"     → reject
"I'll figure it out later" → defer
"I need to read chapter 3" → new_task (fall through to capture)
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

Built incrementally through 9 defined milestones, from bare LLM integration to a fully conversational flow.

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
