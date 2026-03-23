import os
import json
import requests
from datetime import datetime, timezone, timedelta
from icalendar import Calendar
from dateutil import tz

DAYS_AHEAD = int(os.environ.get("DAYS_AHEAD", "30"))

CALENDAR_URLS = [
    url.strip().replace("webcal://", "https://", 1)
    for url in [
        os.environ.get("OUTLOOK_CALENDAR_URL", ""),
        os.environ.get("ICLOUD_CALENDAR_URL", ""),
    ]
    if url.strip()
]


def parse_dt(dt_val):
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            return dt_val.replace(tzinfo=timezone.utc)
        return dt_val.astimezone(timezone.utc)
    return datetime(dt_val.year, dt_val.month, dt_val.day, tzinfo=timezone.utc)


def format_time(dt_val):
    if not isinstance(dt_val, datetime):
        return None
    local = dt_val.astimezone(tz.tzlocal())
    return local.strftime("%-I:%M %p")


def fetch_events_from_url(url, now, cutoff):
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    cal = Calendar.from_ical(response.content)
    calendar_name = str(cal.get("X-WR-CALNAME", "")) or None

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

        events.append({
            "title": summary,
            "date": start_dt.astimezone(tz.tzlocal()).strftime("%Y-%m-%d"),
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

    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=DAYS_AHEAD)

    all_events = []
    errors = []

    for url in CALENDAR_URLS:
        try:
            events = fetch_events_from_url(url, now, cutoff)
            all_events.extend(events)
            print(f"Fetched {len(events)} events from {url[:60]}...")
        except Exception as e:
            errors.append(f"{url[:60]}...: {e}")
            print(f"Warning: failed to fetch {url[:60]}...: {e}")

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
