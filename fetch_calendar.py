import os
import json
import requests
from datetime import datetime, timezone, timedelta
from icalendar import Calendar
from dateutil import tz

CALENDAR_URL = os.environ.get("CALENDAR_URL")
DAYS_AHEAD = int(os.environ.get("DAYS_AHEAD", "30"))


def parse_dt(dt_val):
    """Return a timezone-aware datetime from a date or datetime value."""
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=timezone.utc)
        return dt_val.astimezone(timezone.utc)
    # all-day date
    return datetime(dt_val.year, dt_val.month, dt_val.day, tzinfo=timezone.utc)


def format_time(dt_val):
    """Return 12-hour time string, or None for all-day events."""
    if not isinstance(dt_val, datetime):
        return None
    local = dt_val.astimezone(tz.tzlocal())
    return local.strftime("%-I:%M %p")


def main():
    if not CALENDAR_URL:
        raise ValueError("CALENDAR_URL environment variable is not set")

    response = requests.get(CALENDAR_URL, timeout=30)
    response.raise_for_status()

    cal = Calendar.from_ical(response.content)

    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=DAYS_AHEAD)

    events = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        dtstart = component.get("DTSTART")
        dtend = component.get("DTEND")
        if not dtstart:
            continue

        start_dt = parse_dt(dtstart.dt)
        end_dt = parse_dt(dtend.dt) if dtend else None
        all_day = not isinstance(dtstart.dt, datetime)

        if start_dt < now or start_dt > cutoff:
            continue

        summary = str(component.get("SUMMARY", ""))
        location = str(component.get("LOCATION", "")) or None
        calendar_name = str(cal.get("X-WR-CALNAME", "")) or None

        events.append({
            "title": summary,
            "date": start_dt.astimezone(tz.tzlocal()).strftime("%Y-%m-%d"),
            "time": format_time(dtstart.dt) if not all_day else None,
            "end": end_dt.isoformat() if end_dt else None,
            "all_day": all_day,
            "location": location,
            "calendar": calendar_name,
        })

    events.sort(key=lambda e: e["date"] + (e["time"] or ""))

    output = {
        "events": events,
        "fetched_at": now.isoformat(),
        "error": None,
    }

    with open("events.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(events)} events to events.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_output = {
            "events": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        }
        with open("events.json", "w") as f:
            json.dump(error_output, f, indent=2)
        raise
