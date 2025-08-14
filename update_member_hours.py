#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#     "requests>=2.25.0"
# ]
# ///

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/New_York")
DT_FMT = "%A, %B %-d, %Y at %-I:%M %p"
DT_FMT_FULL = "%A, %B %-d, %Y at %-I:%M %p %Z"


def parse_ical_event(event_text):
    event = {}

    summary_match = re.search(r"SUMMARY:(.+)", event_text)
    if summary_match:
        event["summary"] = summary_match.group(1).strip()

    dtstart_match = re.search(r"DTSTART:(\d{8}T\d{6}Z)", event_text)
    if dtstart_match:
        dt_str = dtstart_match.group(1)
        dt = datetime.strptime(dt_str, "%Y%m%dT%H%M%SZ")
        dt = dt.replace(tzinfo=timezone.utc)
        event["start_datetime"] = dt

    return event


def fetch_and_parse_calendar(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    ical_text = response.text

    # Split into individual events
    events = re.findall(r"BEGIN:VEVENT.*?END:VEVENT", ical_text, re.DOTALL)

    member_hours_events = []
    for event_text in events:
        event = parse_ical_event(event_text)
        if event.get("summary") == "Member Guest Hours" and "start_datetime" in event:
            member_hours_events.append(event)

    return member_hours_events


def get_next_member_hours_event(events):
    now = datetime.now(timezone.utc)
    future_events = [e for e in events if e["start_datetime"] > now]
    if not future_events:
        return "N/A"

    return min(future_events, key=lambda x: x["start_datetime"])["start_datetime"]


def render_locations_content(location_events):
    if location_events:
        locations_html = ""
        for location, next_event_dt in location_events.items():
            local_time = next_event_dt.astimezone(LOCAL_TZ)
            formatted_time = local_time.strftime(DT_FMT)
            formatted_time_full = local_time.strftime(DT_FMT_FULL)
            locations_html += f"""
        <div class="location">
            <div class="location-name">{location}</div>
            <div class="event-time" title="{formatted_time_full}">{formatted_time}</div>
        </div>"""
        return locations_html
    else:
        return """
        <div class="no-events">
            No upcoming Member Guest Hours events found.
        </div>"""


def generate_html_page(location_events):
    template_path = Path(__file__).parent / "template.html"
    with open(template_path) as f:
        template = f.read()

    locations_content = render_locations_content(location_events)

    now = datetime.now(timezone.utc).astimezone(LOCAL_TZ)
    formatted_update_time = now.strftime(DT_FMT)
    formatted_update_time_full = now.strftime(DT_FMT_FULL)

    html = template.replace("%locations_content%", locations_content)
    html = html.replace(
        "%last_updated%",
        f'<span title="{formatted_update_time_full}">{formatted_update_time}</span>',
    )

    return html


def main():
    curr_dir = Path(__file__).parent
    feeds_file = curr_dir / "feeds.json"
    with open(feeds_file) as f:
        feeds_config = json.load(f)

    location_events = {}
    for location, feed_url in feeds_config["calendar_feeds"].items():
        print(f"Processing {location}...")
        events = fetch_and_parse_calendar(feed_url)
        next_event_dt = get_next_member_hours_event(events)
        location_events[location] = next_event_dt
        if not next_event_dt:
            print(f"E: No upcoming Member Guest Hours found at {location}.")

    # Sort locations by start time
    location_events = dict(sorted(location_events.items(), key=lambda x: x[1]))

    html_content = generate_html_page(location_events)

    output_file = curr_dir / "index.html"
    with open(output_file, "w") as f:
        f.write(html_content)

    print(f"\nGenerated page: {output_file}")


if __name__ == "__main__":
    main()
