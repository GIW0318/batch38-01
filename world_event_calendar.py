from collections import Counter
from datetime import date, datetime, time as datetime_time, timezone, tzinfo
from numbers import Real
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _error(message):
    return ValueError(message)


def _timezone(value):
    if isinstance(value, tzinfo):
        return value
    if not isinstance(value, str) or not value.strip():
        raise _error("event timezone is required")
    try:
        return ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError):
        raise _error(f"unknown timezone: {value}") from None


def _parse_time(value, tz):
    if isinstance(value, bool):
        raise _error("invalid time")
    if isinstance(value, Real):
        return float(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=tz)
        return value.astimezone(timezone.utc).timestamp()
    if isinstance(value, date):
        value = datetime.combine(value, datetime_time.min, tzinfo=tz)
        return value.astimezone(timezone.utc).timestamp()
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                return float(value)
            except ValueError:
                raise _error(f"invalid time: {value}") from None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=tz)
        return parsed.astimezone(timezone.utc).timestamp()
    raise _error("invalid time")


class EventCalendar:
    def __init__(self):
        self._events = {}

    def add(self, event, now):
        if not isinstance(event, dict):
            raise _error("event must be a mapping")

        event_id = event.get("id")
        if event_id is None or event_id == "":
            raise _error("event id is required")
        if event_id in self._events:
            raise _error(f"duplicate event id: {event_id}")

        tz = _timezone(event.get("timezone"))
        if "start" not in event or "end" not in event:
            raise _error("event start and end are required")
        start = _parse_time(event["start"], tz)
        end = _parse_time(event["end"], tz)
        if start >= end:
            raise _error("event start must be before end")

        phases = event.get("phases")
        if not isinstance(phases, (list, tuple)) or not phases:
            raise _error("event must have at least one phase")

        normalized_phases = []
        expected_start = start
        for phase in phases:
            if not isinstance(phase, dict):
                raise _error("phase must be a mapping")
            name = phase.get("name")
            if not isinstance(name, str) or not name:
                raise _error("phase name is required")
            if "start" not in phase or "end" not in phase:
                raise _error("phase start and end are required")
            phase_start = _parse_time(phase["start"], tz)
            phase_end = _parse_time(phase["end"], tz)
            if phase_start >= phase_end:
                raise _error("phase start must be before end")
            if phase_start != expected_start:
                raise _error("phases must be contiguous")
            normalized_phases.append(
                {"start": phase_start, "end": phase_end, "name": name}
            )
            expected_start = phase_end
        if expected_start != end:
            raise _error("phases must cover the event interval")

        for other in self._events.values():
            if start < other["end"] and end > other["start"]:
                raise _error(f"event overlaps: {other['id']}")

        self._events[event_id] = {
            "id": event_id,
            "start": start,
            "end": end,
            "phases": normalized_phases,
            "timezone": tz,
            "cancelled": False,
            "settled": False,
        }
        return None

    def _get(self, event_id):
        try:
            return self._events[event_id]
        except KeyError:
            raise _error(f"unknown event: {event_id}") from None

    def phase(self, event_id, t):
        event = self._get(event_id)
        if event["cancelled"]:
            return "cancelled"

        at = _parse_time(t, event["timezone"])
        if at < event["start"] or at >= event["end"]:
            return None
        for phase in event["phases"]:
            if phase["start"] <= at < phase["end"]:
                return phase["name"]
        return None

    def cancel(self, event_id, now):
        event = self._get(event_id)
        event["cancelled"] = True
        return None

    def settle(self, event_id, now):
        event = self._get(event_id)
        if event["cancelled"]:
            raise _error("cancelled event cannot settle")
        if event["settled"]:
            raise _error("event already settled")

        at = _parse_time(now, event["timezone"])
        if at < event["end"]:
            raise _error("event has not ended")

        event["settled"] = True
        return {"settled": True}

    def snapshot(self):
        phase_counts = Counter()
        for event in self._events.values():
            phase_counts.update(phase["name"] for phase in event["phases"])

        active = [
            event
            for event in self._events.values()
            if not event["cancelled"] and not event["settled"]
        ]
        next_event = (
            min(active, key=lambda event: (event["start"], str(event["id"])))
            if active
            else None
        )

        return {
            "events": len(self._events),
            "phase_counts": dict(phase_counts),
            "next_event": next_event["id"] if next_event else None,
        }
