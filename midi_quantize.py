from collections import defaultdict, deque
from fractions import Fraction
import re


_GRID_RE = re.compile(r"^1/(4|8|16|32)(T)?$", re.IGNORECASE)


class MidiQuantize:
    def __init__(self):
        self._stats = {
            "events": 0,
            "mean_offset": 0.0,
            "overlap_corrections": 0,
        }

    def quantize(self, events, ppq, grid, swing):
        ppq = self._validate_ppq(ppq)
        grid_ticks = self._grid_ticks(ppq, grid)
        swing = self._validate_swing(swing)

        if events is None:
            raise ValueError("events are required")
        events = list(events)

        indexed = []
        for index, raw in enumerate(events):
            event = self._copy_event(raw)
            indexed.append((event, index))

        indexed.sort(key=lambda item: (item[0]["tick"], item[1]))
        pairs = self._pair_notes(indexed)

        offsets = []
        for pair in pairs:
            pair["quantized_on"] = self._quantize_tick(
                pair["on"]["tick"], grid_ticks, swing
            )
            offsets.append(pair["quantized_on"] - pair["on"]["tick"])
            pair["quantized_off"] = (
                pair["quantized_on"]
                + pair["off"]["tick"]
                - pair["on"]["tick"]
            )

        overlap_corrections = self._trim_overlaps(pairs)

        output = [None] * len(indexed)
        for pair in pairs:
            on_event = dict(pair["on"])
            on_event["tick"] = pair["quantized_on"]
            off_event = dict(pair["off"])
            off_event["tick"] = max(pair["quantized_on"], pair["quantized_off"])
            output[pair["on_index"]] = on_event
            output[pair["off_index"]] = off_event

        output.sort(
            key=lambda event: (
                event["tick"],
                event["channel"],
                event["note"],
            )
        )

        self._stats = {
            "events": len(output),
            "mean_offset": (
                float(sum(offsets, Fraction(0)) / len(offsets))
                if offsets
                else 0.0
            ),
            "overlap_corrections": overlap_corrections,
        }
        return output

    def tracks(self):
        return dict(self._stats)

    @staticmethod
    def _validate_ppq(ppq):
        if isinstance(ppq, bool) or not isinstance(ppq, int):
            raise ValueError("ppq must be an integer")
        if not 96 <= ppq <= 960:
            raise ValueError("ppq must be between 96 and 960")
        return ppq

    @staticmethod
    def _validate_swing(swing):
        if isinstance(swing, bool) or not isinstance(swing, (int, float)):
            raise ValueError("swing must be a number")
        if not 50 <= swing <= 75:
            raise ValueError("swing must be between 50 and 75")
        return swing

    @staticmethod
    def _grid_ticks(ppq, grid):
        if not isinstance(grid, str):
            raise ValueError("invalid grid")
        match = _GRID_RE.fullmatch(grid)
        if match is None:
            raise ValueError("invalid grid")

        denominator = int(match.group(1))
        ticks = Fraction(ppq * 4, denominator)
        if match.group(2):
            ticks *= Fraction(2, 3)
        return ticks

    @staticmethod
    def _copy_event(raw):
        if not isinstance(raw, dict):
            raise ValueError("events must be dictionaries")

        required = ("tick", "type", "channel", "note", "velocity")
        if any(key not in raw for key in required):
            raise ValueError("event is missing required fields")

        event = dict(raw)
        tick = event["tick"]
        channel = event["channel"]
        note = event["note"]
        velocity = event["velocity"]
        kind = event["type"]

        if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
            raise ValueError("tick must be a non-negative integer")
        if isinstance(channel, bool) or not isinstance(channel, int):
            raise ValueError("channel must be an integer")
        if not 0 <= channel <= 15:
            raise ValueError("channel must be between 0 and 15")
        if isinstance(note, bool) or not isinstance(note, int):
            raise ValueError("note must be an integer")
        if not 0 <= note <= 127:
            raise ValueError("note must be between 0 and 127")
        if isinstance(velocity, bool) or not isinstance(velocity, int):
            raise ValueError("velocity must be an integer")
        if kind == "note_on":
            if not 1 <= velocity <= 127:
                raise ValueError("note_on velocity must be between 1 and 127")
        elif kind == "note_off":
            if not 0 <= velocity <= 127:
                raise ValueError("note_off velocity must be between 0 and 127")
        else:
            raise ValueError("unsupported event type")

        return event

    @staticmethod
    def _pair_notes(indexed):
        pending = defaultdict(deque)
        pairs = []

        for event, original_index in indexed:
            key = (event["channel"], event["note"])
            if event["type"] == "note_on":
                pending[key].append((event, original_index))
                continue

            if not pending[key]:
                raise ValueError("note_off has no matching note_on")
            on_event, on_index = pending[key].popleft()
            pairs.append(
                {
                    "on": on_event,
                    "off": event,
                    "on_index": on_index,
                    "off_index": original_index,
                }
            )

        if any(queue for queue in pending.values()):
            raise ValueError("note_on has no matching note_off")

        return pairs

    @staticmethod
    def _quantize_tick(tick, grid_ticks, swing):
        position = Fraction(tick, 1) / grid_ticks
        grid_index = int(position + Fraction(1, 2))
        quantized = grid_index * grid_ticks

        if grid_index != 0 and grid_index % 2 == 0:
            quantized += (
                grid_ticks
                * Fraction(str(swing - 50)).limit_denominator()
                / 50
            )

        return int(quantized + Fraction(1, 2))

    @staticmethod
    def _trim_overlaps(pairs):
        grouped = defaultdict(list)
        for pair in pairs:
            grouped[(pair["on"]["channel"], pair["on"]["note"])].append(pair)

        corrections = 0
        for group in grouped.values():
            group.sort(key=lambda pair: pair["quantized_on"])
            for previous, current in zip(group, group[1:]):
                if previous["quantized_off"] >= current["quantized_on"]:
                    trimmed = max(
                        previous["quantized_on"],
                        (previous["quantized_on"] + current["quantized_on"]) // 2
                        - 1,
                    )
                    trimmed = min(trimmed, current["quantized_on"] - 1)
                    if trimmed != previous["quantized_off"]:
                        previous["quantized_off"] = trimmed
                        corrections += 1
        return corrections
