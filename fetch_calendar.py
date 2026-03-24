import os
import json
import requests
from datetime import datetime, timezone, timedelta
from icalendar import Calendar
from dateutil import tz
import recurring_ical_events

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
            return dt_val.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
        return dt_val.astimezone(timezone.utc)
    return datetime(dt_val.year, dt_val.month, dt_val.day, tzinfo=timezone.utc)


def format_time(dt_val):
    if not isinstance(dt_val, datetime):
        return None
    if dt_val.tzinfo is None:
        dt_val = dt_val.replace(tzinfo=LOCAL_TZ)
    local = dt_val.astimezone(LOCAL_TZ)
    return local.strftime("%-I:%M %p")


def fetch_events_from_url(name, url, now, cutoff):
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    cal = Calendar.from_ical(response.content)
    calendar_name = str(cal.get("X-WR-CALNAME", "")) or name

    # Use recurring_ical_events to expand recurrences (RRULE/RDATE/EXDATE)
    range_start = now.astimezone(LOCAL_TZ)
    range_end   = cutoff.astimezone(LOCAL_TZ)
    components  = recurring_ical_events.of(cal).between(range_start, range_end)

    events = []
    for component in components:
        if component.name != "VEVENT":
            continue

        dtstart = component.get("DTSTART")
        dtend   = component.get("DTEND")
        if not dtstart:
            continue

        all_day  = not isinstance(dtstart.dt, datetime)
        start_dt = parse_dt(dtstart.dt)
        end_dt   = parse_dt(dtend.dt) if dtend else None

        summary  = str(component.get("SUMMARY",  ""))
        location = str(component.get("LOCATION", "")) or None

        events.append({
            "title":    summary,
            "date":     start_dt.astimezone(LOCAL_TZ).strftime("%Y-%m-%d"),
            "time":     format_time(dtstart.dt) if not all_day else None,
            "end":      end_dt.isoformat() if end_dt else None,
            "all_day":  all_day,
            "location": location,
            "calendar": calendar_name,
        })

    return events


def main():
    if not CALENDAR_URLS:
        print("Warning: no calendar URLs configured (OUTLOOK_CALENDAR_URL / ICLOUD_CALENDAR_URL not set)")
        output = {
            "events":    [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "calendars": [],
            "error":     "No calendar URLs configured",
        }
        with open("events.json", "w") as f:
            json.dump(output, f, indent=2)
        return

    print(f"Configured calendars: {[name for name, _ in CALENDAR_URLS]}")

    now    = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=DAYS_AHEAD)

    all_events = []
    errors     = []
    calendars_fetched = []

    for name, url in CALENDAR_URLS:
        try:
            events = fetch_events_from_url(name, url, now, cutoff)
            all_events.extend(events)
            calendars_fetched.append(name)
            print(f"  {name}: fetched {len(events)} events")
        except Exception as e:
            errors.append(f"{name}: {e}")
            print(f"  {name}: ERROR — {e}")

    all_events.sort(key=lambda e: e["date"] + (e["time"] or "00:00 AM"))

    output = {
        "events":     all_events,
        "fetched_at": now.isoformat(),
        "calendars":  calendars_fetched,
        "error":      "; ".join(errors) if errors else None,
    }

    with open("events.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(all_events)} total events to events.json")
    if errors:
        print(f"Errors: {'; '.join(errors)}")


if __name__ == "__main__":
    main()
