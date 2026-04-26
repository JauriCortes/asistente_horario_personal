import datetime
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from handlers.capture import handle_message
from handlers.review import handle_cancel_command, handle_defer_command, handle_done_command

_BOGOTA = ZoneInfo("America/Bogota")
_CHAT_ID_FILE = Path(__file__).parent / "data" / "user_config.json"


def _load_chat_id() -> int | None:
    try:
        return json.loads(_CHAT_ID_FILE.read_text())["chat_id"]
    except Exception:
        return None


def _save_chat_id(chat_id: int) -> None:
    existing = {}
    if _CHAT_ID_FILE.exists():
        try:
            existing = json.loads(_CHAT_ID_FILE.read_text())
        except Exception:
            pass
    existing["chat_id"] = chat_id
    _CHAT_ID_FILE.write_text(json.dumps(existing, indent=2))


async def _register_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guarda el chat_id del usuario en el primer mensaje."""
    if update.effective_chat and not _load_chat_id():
        _save_chat_id(update.effective_chat.id)


async def _send_daily_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _load_chat_id()
    if not chat_id:
        return
    from core.proactivity import build_daily_message
    try:
        msg = build_daily_message()
        await context.bot.send_message(chat_id=chat_id, text=msg)
    except Exception as e:
        print(f"[proactivity] Error en mensaje diario: {e}")


async def _send_weekly_summary(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _load_chat_id()
    if not chat_id:
        return
    from core.proactivity import build_weekly_summary
    try:
        msg = build_weekly_summary()
        await context.bot.send_message(chat_id=chat_id, text=msg)
    except Exception as e:
        print(f"[proactivity] Error en resumen semanal: {e}")


async def handle_resumen_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from core.proactivity import build_weekly_summary
    await update.message.chat.send_action("typing")
    await update.message.reply_text(build_weekly_summary())


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN no está configurado en .env")
        sys.exit(1)

    app = Application.builder().token(token).build()

    # Middleware: registrar chat_id en el primer mensaje
    app.add_handler(MessageHandler(filters.ALL, _register_chat_id), group=-1)

    # Comandos
    app.add_handler(CommandHandler("done", handle_done_command))
    app.add_handler(CommandHandler("cancel", handle_cancel_command))
    app.add_handler(CommandHandler("defer", handle_defer_command))
    app.add_handler(CommandHandler("resumen", handle_resumen_command))

    # Mensajes de texto
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Jobs proactivos (timezone Bogotá)
    jq = app.job_queue
    # Lunes a las 9am: resumen semanal
    jq.run_daily(
        _send_weekly_summary,
        time=datetime.time(9, 0, tzinfo=_BOGOTA),
        days=(0,),  # lunes
        name="weekly_summary",
    )
    # Diario a las 9am (martes a domingo): mensaje de recordatorio
    jq.run_daily(
        _send_daily_message,
        time=datetime.time(9, 0, tzinfo=_BOGOTA),
        days=(1, 2, 3, 4, 5, 6),  # mar–dom
        name="daily_reminder",
    )

    print("Bot arrancado. Ctrl+C para detener.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
