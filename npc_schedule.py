import copy

WEEK = 604800
DAY = 86400

VALID_ACTIVITIES = {"idle", "patrol", "trade", "sleep", "eat"}


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class ScheduleBoard:
    def __init__(self):
        self.week = 0
        self._plans = {}
        self._segments = {}
        self._overrides = {}
        self._interrupts = {}
        self._counter = 0

    def assign_week(self, npc, week_plan):
        if not isinstance(week_plan, (list, tuple)) or len(week_plan) != 7:
            raise ValueError("week_plan must contain exactly 7 days")

        plan = []
        absolute_segments = []
        for day_index, day_segments in enumerate(week_plan):
            if not isinstance(day_segments, (list, tuple)):
                raise ValueError("each day must contain a list of segments")
            day_base = day_index * DAY
            day_intervals = []
            stored_day = []
            for segment in day_segments:
                if not isinstance(segment, dict):
                    raise ValueError("each segment must be a dict")
                start = segment.get("start")
                end = segment.get("end")
                waypoint = segment.get("waypoint")
                activity = segment.get("activity")
                if not _is_number(start) or not _is_number(end):
                    raise ValueError("segment start and end must be numbers")
                if activity not in VALID_ACTIVITIES:
                    raise ValueError("invalid activity: %r" % (activity,))
                if start < 0 or start > DAY or end < 0 or end > DAY:
                    raise ValueError("segment time must stay within a single day")

                abs_start = day_base + start
                abs_end = day_base + end
                if end <= start:
                    abs_end += DAY

                stored = {
                    "start": start,
                    "end": end,
                    "waypoint": waypoint,
                    "activity": activity,
                }
                stored_day.append(stored)
                day_intervals.append((abs_start, abs_end))
                absolute_segments.append(
                    {
                        "start": abs_start,
                        "end": abs_end,
                        "waypoint": waypoint,
                        "activity": activity,
                    }
                )

            day_intervals.sort()
            for previous, current in zip(day_intervals, day_intervals[1:]):
                if current[0] < previous[1]:
                    raise ValueError("segments on day %d overlap" % day_index)

            plan.append(stored_day)

        absolute_segments.sort(key=lambda item: item["start"])
        self._plans[npc] = plan
        self._segments[npc] = absolute_segments
        self._overrides.pop(npc, None)
        self._interrupts.pop(npc, None)

    def override(self, npc, window, activity, priority, now):
        if npc not in self._plans:
            raise ValueError("unknown npc: %r" % (npc,))
        if activity not in VALID_ACTIVITIES:
            raise ValueError("invalid activity: %r" % (activity,))
        if priority not in (1, 2, 3):
            raise ValueError("priority must be between 1 and 3")
        if not isinstance(window, (list, tuple)) or len(window) != 2:
            raise ValueError("window must be a (start, end) pair")
        start, end = window
        if not _is_number(start) or not _is_number(end):
            raise ValueError("window bounds must be numbers")
        if start < 0 or end > WEEK or start >= end:
            raise ValueError("override window is out of bounds")

        self._counter += 1
        self._overrides.setdefault(npc, []).append(
            {
                "start": start,
                "end": end,
                "activity": activity,
                "priority": priority,
                "ts": now,
                "order": self._counter,
            }
        )

    def _check_npc_and_time(self, npc, t):
        if npc not in self._plans:
            raise ValueError("unknown npc: %r" % (npc,))
        if not _is_number(t) or t < 0:
            raise ValueError("t must be non-negative")

    def _base_segment(self, npc, t):
        for segment in self._segments[npc]:
            if segment["start"] <= t < segment["end"]:
                return segment
        return None

    def _active_override(self, npc, t):
        candidates = [
            item
            for item in self._overrides.get(npc, [])
            if item["start"] <= t < item["end"]
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: (item["priority"], item["order"]))

    def status(self, npc, t):
        self._check_npc_and_time(npc, t)

        interruption = self._interrupts.get(npc)
        if interruption is not None:
            segment = interruption["segment"]
            return {
                "activity": segment["activity"],
                "source": "interrupted",
                "waypoint": segment["waypoint"],
                "remaining": segment["end"] - t,
                "next_start": segment["end"],
                "reason": interruption["reason"],
            }

        active_override = self._active_override(npc, t)
        if active_override is not None:
            base = self._base_segment(npc, t)
            return {
                "activity": active_override["activity"],
                "source": "override",
                "waypoint": base["waypoint"] if base else None,
                "remaining": active_override["end"] - t,
                "next_start": active_override["end"],
            }

        segment = self._base_segment(npc, t)
        if segment is not None:
            return {
                "activity": segment["activity"],
                "source": "base",
                "waypoint": segment["waypoint"],
                "remaining": segment["end"] - t,
                "next_start": segment["end"],
            }

        next_start = None
        for candidate in self._segments[npc]:
            if candidate["start"] > t:
                next_start = candidate["start"]
                break
        return {
            "activity": "idle",
            "source": "base",
            "waypoint": None,
            "remaining": None,
            "next_start": next_start,
        }

    def interrupt(self, npc, reason, t):
        self._check_npc_and_time(npc, t)
        segment = self._base_segment(npc, t)
        if segment is None:
            raise ValueError("cannot interrupt without an active segment")

        record = {
            "reason": reason,
            "offset": t - segment["start"],
            "segment": dict(segment),
        }
        self._interrupts[npc] = record
        return {
            "activity": segment["activity"],
            "source": "interrupted",
            "waypoint": segment["waypoint"],
            "remaining": segment["end"] - t,
            "next_start": segment["end"],
            "reason": reason,
        }

    def resume(self, npc, t):
        self._check_npc_and_time(npc, t)
        if npc not in self._interrupts:
            raise ValueError("no interruption recorded for %r" % (npc,))

        del self._interrupts[npc]
        return self.status(npc, t)

    def export(self):
        return {
            "week": self.week,
            "plans": copy.deepcopy(self._plans),
        }
