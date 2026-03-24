import os
import json
import requests
from datetime import datetime, timezone, timedelta
from icalendar import Calendar
from dateutil import tz

DAYS_AHEAD = int(os.environ.get("DAYS_AHEAD", "30"))
LOCAL_TZ = tz.gettz("America/Moncton")

CALENDAR_SOURCES = {
    "outlook": os.environ.get("OUTLOOK_CALENDAR_URL", "").strip().replace("webcal://", "https://", 1),
    "icloud":  os.environ.get("ICLOUD_CALENDAR_URL",  "").strip().replace("webcal://", "https://", 1),
}

CALENDAR_URLS = [(name, url) for name, url in CALENDAR_SOURCES.items() if url]


def parse_dt(dt_val):
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            # Naive datetime — treat as local (Atlantic) time, not UTC
            return dt_val.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
        return dt_val.astimezone(timezone.utc)
    return datetime(dt_val.year, dt_val.month, dt_val.day, tzinfo=timezone.utc)


def format_time(dt_val):
    if not isinstance(dt_val, datetime):
        return None
    local = dt_val.astimezone(LOCAL_TZ)
    return local.strftime("%-I:%M %p")


def fetch_events_from_url(name, url, now, cutoff):
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    cal = Calendar.from_ical(response.content)
    calendar_name = str(cal.get("X-WR-CALNAME", "")) or name

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

        # For all-day events compare date only so we don't lose today's events
        if all_day:
            today = now.astimezone(LOCAL_TZ).date()
            event_date = dtstart.dt
            if event_date < today or start_dt > cutoff:
                continue
        else:
            if start_dt < now or start_dt > cutoff:
                continue

        summary = str(component.get("SUMMARY", ""))
        location = str(component.get("LOCATION", "")) or None

        events.append({
            "title": summary,
            "date": start_dt.astimezone(LOCAL_TZ).strftime("%Y-%m-%d"),
            "time": format_time(dtstart.dt) if not all_day else None,
            "end": end_dt.isoformat() if end_dt else None,
            "all_day": all_day,
            "location": location,
            "calendar": calendar_name,
        })

    return events


def main():
    if not CALENDAR_URLS:
        raise ValueError("No calendar URLs set. Define OUTLOOK_CALENDAR_URL and/or ICLOUD_CALENDAR_URL.")

    print(f"Configured calendars: {[name for name, _ in CALENDAR_URLS]}")

    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=DAYS_AHEAD)

    all_events = []
    errors = []

    for name, url in CALENDAR_URLS:
        try:
            events = fetch_events_from_url(name, url, now, cutoff)
            all_events.extend(events)
            print(f"  {name}: fetched {len(events)} events")
        except Exception as e:
            errors.append(f"{name}: {e}")
            print(f"  {name}: ERROR — {e}")

    all_events.sort(key=lambda e: e["date"] + (e["time"] or "00:00 AM"))

    output = {
        "events": all_events,
        "fetched_at": now.isoformat(),
        "error": "; ".join(errors) if errors else None,
    }

    with open("events.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(all_events)} total events to events.json")

    if errors and not all_events:
        raise RuntimeError("All calendar fetches failed:\n" + "\n".join(errors))


if __name__ == "__main__":
    main()
