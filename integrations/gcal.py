import json
import subprocess
from datetime import datetime, timedelta, timezone

TIMEZONE = "America/Bogota"


class CalendarAuthError(Exception):
    """Token vencido. El usuario debe correr: gws auth login"""


class CalendarError(Exception):
    """Error genérico de Calendar."""


def _run_gws(*args) -> dict:
    result = subprocess.run(
        ["gws"] + list(args),
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        stderr = result.stderr.strip()
        raise CalendarError(f"gws no devolvió JSON válido: {stderr or result.stdout[:200]}")

    if "error" in data:
        err = data["error"]
        msg = err.get("message", "")
        reason = err.get("reason", "")
        if err.get("code") == 401 or "reauth" in msg.lower() or "auth" in reason.lower():
            raise CalendarAuthError(
                "Token de Google Calendar vencido. Corré: gws auth login"
            )
        raise CalendarError(f"Error de Calendar ({err.get('code')}): {msg}")

    return data


def get_events(days_ahead: int = 7) -> list[dict]:
    """Devuelve los eventos de los próximos N días en formato simplificado."""
    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=days_ahead)

    data = _run_gws(
        "calendar", "events", "list",
        "--params", json.dumps({
            "calendarId": "primary",
            "maxResults": 50,
            "orderBy": "startTime",
            "singleEvents": True,
            "timeMin": now.isoformat(),
            "timeMax": time_max.isoformat(),
        }),
        "--format", "json",
    )

    events = []
    for item in data.get("items", []):
        start = item.get("start", {})
        end = item.get("end", {})
        all_day = "date" in start and "dateTime" not in start
        events.append({
            "id": item.get("id"),
            "summary": item.get("summary", "(sin título)"),
            "start": start.get("dateTime") or start.get("date"),
            "end": end.get("dateTime") or end.get("date"),
            "location": item.get("location"),
            "allDay": all_day,
        })

    return events


def create_event(summary: str, start_dt: str, end_dt: str, description: str = "") -> str:
    """Crea un evento en el calendario. Devuelve el eventId de Google."""
    event_body: dict = {
        "summary": summary,
        "start": {"dateTime": start_dt, "timeZone": TIMEZONE},
        "end": {"dateTime": end_dt, "timeZone": TIMEZONE},
    }
    if description:
        event_body["description"] = description

    data = _run_gws(
        "calendar", "events", "insert",
        "--params", json.dumps({"calendarId": "primary"}),
        "--json", json.dumps(event_body),
        "--format", "json",
    )

    return data.get("id", "")
