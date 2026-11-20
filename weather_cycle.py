from __future__ import annotations

import bisect
import hashlib
import math
from dataclasses import dataclass
from typing import Iterable


WEATHER_STATES = ("clear", "cloud", "rain", "storm", "snow")

ALLOWED_TRANSITIONS = {
    "clear": ("cloud",),
    "cloud": ("clear", "rain", "snow"),
    "rain": ("storm",),
    "storm": ("cloud",),
    "snow": ("clear",),
}

_ALLOWED_PAIRS = {
    (left, right)
    for left, rights in ALLOWED_TRANSITIONS.items()
    for right in rights
}

MIN_STATE_SECONDS = 120
MIN_FRONT_SECONDS = 20 * 60
MAX_FRONT_SECONDS = 60 * 60
MAX_FORECAST_SECONDS = 604800
WARNING_LEAD_SECONDS = 600
WARNING_CONFIDENCE = 0.70


_FRONT_TYPES = ("warm", "cold", "stationary", "occluded")

_FRONT_TEMP_DELTA = {
    "warm": 1.0,
    "cold": -1.0,
    "stationary": 0.2,
    "occluded": -0.6,
}

_FRONT_WEIGHTS = {
    "warm": {
        "clear": 2.4,
        "cloud": 1.5,
        "rain": 0.4,
        "storm": 0.10,
        "snow": 0.15,
    },
    "cold": {
        "clear": 0.6,
        "cloud": 1.4,
        "rain": 1.3,
        "storm": 1.2,
        "snow": 1.6,
    },
    "stationary": {
        "clear": 1.2,
        "cloud": 2.2,
        "rain": 0.8,
        "storm": 0.25,
        "snow": 0.7,
    },
    "occluded": {
        "clear": 0.3,
        "cloud": 1.2,
        "rain": 1.6,
        "storm": 1.5,
        "snow": 0.9,
    },
}

_BIOMES = {
    "forest": {
        "temp_offset": 0.0,
        "weights": {
            "clear": 0.9,
            "cloud": 1.2,
            "rain": 1.2,
            "storm": 0.9,
            "snow": 1.0,
        },
    },
    "plains": {
        "temp_offset": 0.6,
        "weights": {
            "clear": 1.4,
            "cloud": 1.0,
            "rain": 0.8,
            "storm": 0.8,
            "snow": 0.8,
        },
    },
    "grassland": {
        "temp_offset": 0.6,
        "weights": {
            "clear": 1.4,
            "cloud": 1.0,
            "rain": 0.8,
            "storm": 0.8,
            "snow": 0.8,
        },
    },
    "desert": {
        "temp_offset": 2.2,
        "weights": {
            "clear": 2.2,
            "cloud": 0.6,
            "rain": 0.25,
            "storm": 0.15,
            "snow": 0.10,
        },
    },
    "tundra": {
        "temp_offset": -3.5,
        "weights": {
            "clear": 0.8,
            "cloud": 1.2,
            "rain": 0.6,
            "storm": 1.0,
            "snow": 2.2,
        },
    },
    "taiga": {
        "temp_offset": -2.0,
        "weights": {
            "clear": 0.8,
            "cloud": 1.3,
            "rain": 0.9,
            "storm": 0.9,
            "snow": 1.8,
        },
    },
    "mountain": {
        "temp_offset": -1.8,
        "weights": {
            "clear": 1.0,
            "cloud": 1.1,
            "rain": 1.1,
            "storm": 1.4,
            "snow": 1.8,
        },
    },
    "hills": {
        "temp_offset": -0.5,
        "weights": {
            "clear": 1.1,
            "cloud": 1.2,
            "rain": 1.0,
            "storm": 1.1,
            "snow": 1.1,
        },
    },
    "swamp": {
        "temp_offset": 1.0,
        "weights": {
            "clear": 0.7,
            "cloud": 1.4,
            "rain": 1.6,
            "storm": 1.1,
            "snow": 0.5,
        },
    },
    "marsh": {
        "temp_offset": 1.0,
        "weights": {
            "clear": 0.7,
            "cloud": 1.4,
            "rain": 1.6,
            "storm": 1.1,
            "snow": 0.5,
        },
    },
    "jungle": {
        "temp_offset": 2.0,
        "weights": {
            "clear": 0.8,
            "cloud": 1.2,
            "rain": 1.8,
            "storm": 1.3,
            "snow": 0.05,
        },
    },
    "rainforest": {
        "temp_offset": 2.0,
        "weights": {
            "clear": 0.8,
            "cloud": 1.2,
            "rain": 1.8,
            "storm": 1.3,
            "snow": 0.05,
        },
    },
    "savanna": {
        "temp_offset": 1.8,
        "weights": {
            "clear": 1.5,
            "cloud": 1.0,
            "rain": 0.8,
            "storm": 0.7,
            "snow": 0.1,
        },
    },
    "ocean": {
        "temp_offset": 0.5,
        "weights": {
            "clear": 0.8,
            "cloud": 1.0,
            "rain": 1.5,
            "storm": 1.7,
            "snow": 0.6,
        },
    },
    "coast": {
        "temp_offset": 0.4,
        "weights": {
            "clear": 1.0,
            "cloud": 1.2,
            "rain": 1.2,
            "storm": 1.1,
            "snow": 0.7,
        },
    },
    "beach": {
        "temp_offset": 1.0,
        "weights": {
            "clear": 1.6,
            "cloud": 1.0,
            "rain": 0.8,
            "storm": 0.7,
            "snow": 0.2,
        },
    },
    "volcano": {
        "temp_offset": 1.5,
        "weights": {
            "clear": 0.9,
            "cloud": 1.2,
            "rain": 1.0,
            "storm": 1.5,
            "snow": 0.5,
        },
    },
}


@dataclass(frozen=True)
class _Segment:
    start: int
    end: int
    weather: str
    front_id: str
    front_index: int
    front_type: str
    temp: float


class WeatherEngine:
    def __init__(self, world_seed, biome, temp_base=10.0, **kwargs):
        if "temp" in kwargs:
            temp_base = kwargs.pop("temp")
        if kwargs:
            names = ", ".join(sorted(kwargs))
            raise TypeError(f"unexpected keyword argument(s): {names}")

        biome_name = self._canonical_biome(biome)
        if biome_name not in _BIOMES:
            raise ValueError(f"unknown biome: {biome!r}")
        if not isinstance(temp_base, (int, float)) or not math.isfinite(temp_base):
            raise ValueError("temp_base must be a finite number")

        self.world_seed = world_seed
        self.biome = biome_name
        self.temp_base = float(temp_base)
        self._seed_token = str(world_seed)
        self._biome_config = _BIOMES[biome_name]
        self._now = None
        self._segments: list[_Segment] = []
        self._starts: list[int] = []
        self._add_initial_segment()

    @staticmethod
    def _canonical_biome(biome) -> str:
        if not isinstance(biome, str):
            return ""
        return biome.strip().lower().replace("-", "_").replace(" ", "_")

    def _hash_int(self, *parts) -> int:
        payload = "|".join((self._seed_token, self.biome, *(str(p) for p in parts)))
        return int.from_bytes(
            hashlib.blake2b(payload.encode("utf-8"), digest_size=8).digest(),
            "big",
        )

    def _unit(self, *parts) -> float:
        return self._hash_int(*parts) / float(1 << 64)

    def _front_type(self, index: int) -> str:
        return _FRONT_TYPES[self._hash_int("front-type", index) % len(_FRONT_TYPES)]

    def _front_duration(self, index: int) -> int:
        span = MAX_FRONT_SECONDS - MIN_FRONT_SECONDS + 1
        return MIN_FRONT_SECONDS + self._hash_int("front-duration", index) % span

    def _front_id(self, index: int) -> str:
        return f"front-{self._seed_token}-{index}"

    def _temperature(self, index: int, front_type: str) -> float:
        drift = (self._unit("front-temp", index) - 0.5) * 0.4
        temp = (
            self.temp_base
            + self._biome_config["temp_offset"]
            + _FRONT_TEMP_DELTA[front_type]
            + drift
        )
        return round(temp, 2)

    def _weight(self, front_type: str, weather: str, temp: float) -> float:
        if weather == "snow" and temp > 0:
            return 0.0
        return (
            _FRONT_WEIGHTS[front_type][weather]
            * self._biome_config["weights"][weather]
        )

    def _pick(self, weights: Iterable[tuple[str, float]], *parts) -> str:
        choices = [(name, weight) for name, weight in weights if weight > 0]
        if not choices:
            return "cloud"
        total = sum(weight for _, weight in choices)
        roll = self._unit(*parts) * total
        upto = 0.0
        for name, weight in choices:
            upto += weight
            if roll < upto:
                return name
        return choices[-1][0]

    def _initial_weather(self, front_type: str, temp: float) -> str:
        choices = [
            (weather, self._weight(front_type, weather, temp))
            for weather in WEATHER_STATES
        ]
        return self._pick(choices, "initial-weather", 0)

    def _initial_segment(self) -> _Segment:
        index = 0
        front_type = self._front_type(index)
        temp = self._temperature(index, front_type)
        weather = self._initial_weather(front_type, temp)
        return _Segment(
            start=0,
            end=self._front_duration(index),
            weather=weather,
            front_id=self._front_id(index),
            front_index=index,
            front_type=front_type,
            temp=temp,
        )

    def _add_initial_segment(self) -> None:
        segment = self._initial_segment()
        self._segments.append(segment)
        self._starts.append(segment.start)

    def _next_weather(
        self,
        current: str,
        front_type: str,
        temp: float,
        index: int,
    ) -> str:
        candidates = list(ALLOWED_TRANSITIONS[current])
        if current not in candidates:
            candidates.append(current)
        choices = []
        for weather in candidates:
            weight = self._weight(front_type, weather, temp)
            if weather == current:
                weight *= 0.85
            choices.append((weather, weight))
        return self._pick(choices, "next-weather", index, current)

    def _append_segment(self) -> None:
        previous = self._segments[-1]
        index = previous.front_index + 1
        front_type = self._front_type(index)
        temp = self._temperature(index, front_type)
        weather = self._next_weather(previous.weather, front_type, temp, index)
        duration = self._front_duration(index)
        segment = _Segment(
            start=previous.end,
            end=previous.end + duration,
            weather=weather,
            front_id=self._front_id(index),
            front_index=index,
            front_type=front_type,
            temp=temp,
        )
        self._segments.append(segment)
        self._starts.append(segment.start)

    def _predecessors(self, weather: str) -> list[str]:
        result = []
        for candidate in WEATHER_STATES:
            if candidate == weather or (candidate, weather) in _ALLOWED_PAIRS:
                result.append(candidate)
        return result

    def _prepend_segment(self) -> None:
        following = self._segments[0]
        index = following.front_index - 1
        front_type = self._front_type(index)
        temp = self._temperature(index, front_type)
        choices = [
            (weather, self._weight(front_type, weather, temp))
            for weather in self._predecessors(following.weather)
        ]
        weather = self._pick(choices, "previous-weather", index, following.weather)
        duration = self._front_duration(index)
        segment = _Segment(
            start=following.start - duration,
            end=following.start,
            weather=weather,
            front_id=self._front_id(index),
            front_index=index,
            front_type=front_type,
            temp=temp,
        )
        self._segments.insert(0, segment)
        self._starts.insert(0, segment.start)

    def _ensure_covered(self, t: int) -> None:
        while t < self._segments[0].start:
            self._prepend_segment()
        while t >= self._segments[-1].end:
            self._append_segment()

    def _find_segment(self, t: int) -> _Segment:
        self._ensure_covered(t)
        index = bisect.bisect_right(self._starts, t) - 1
        return self._segments[index]

    def _make_interval(self, start, end, segment: _Segment) -> dict:
        return {
            "start": start,
            "end": end,
            "weather": segment.weather,
            "temp": segment.temp,
            "front_id": segment.front_id,
        }

    def _intervals(self, start, end, merge_weather: bool) -> list[dict]:
        if end <= start:
            return []

        self._ensure_covered(start)
        self._ensure_covered(end)

        rows = []
        cursor = start
        index = bisect.bisect_right(self._starts, cursor) - 1
        while cursor < end:
            segment = self._segments[index]
            if segment.end <= cursor:
                index += 1
                continue
            piece_start = cursor
            piece_end = min(segment.end, end)
            row = self._make_interval(piece_start, piece_end, segment)
            if merge_weather and rows and rows[-1]["weather"] == row["weather"]:
                rows[-1]["end"] = piece_end
            else:
                rows.append(row)
            cursor = piece_end
            index += 1
        return rows

    def advance(self, now):
        if not isinstance(now, (int, float)) or not math.isfinite(now):
            raise ValueError("now must be a finite number")
        if self._now is not None and now < self._now:
            raise ValueError("time cannot move backwards")
        self._now = now

    def at(self, t):
        if not isinstance(t, (int, float)) or not math.isfinite(t):
            raise ValueError("time must be a finite number")
        segment = self._find_segment(t)
        return {
            "weather": segment.weather,
            "remaining": segment.end - t,
            "front_id": segment.front_id,
            "temp": segment.temp,
        }

    def forecast(self, t, horizon):
        if not isinstance(t, (int, float)) or not math.isfinite(t):
            raise ValueError("time must be a finite number")
        if (
            not isinstance(horizon, (int, float))
            or not math.isfinite(horizon)
            or horizon < 1
            or horizon > MAX_FORECAST_SECONDS
        ):
            raise ValueError("horizon must be between 1 and 604800 seconds")
        return self._intervals(t, t + horizon, merge_weather=True)

    def warning(self, t):
        if not isinstance(t, (int, float)) or not math.isfinite(t):
            raise ValueError("time must be a finite number")

        horizon = t + WARNING_LEAD_SECONDS
        self._ensure_covered(horizon)
        index = bisect.bisect_right(self._starts, t) - 1
        while index < len(self._segments):
            segment = self._segments[index]
            if segment.start > horizon:
                break
            if segment.weather == "storm" and segment.start > t:
                lead = segment.start - t
                confidence = 0.72 + 0.27 * (1.0 - lead / WARNING_LEAD_SECONDS)
                if confidence < WARNING_CONFIDENCE:
                    return None
                return {
                    "weather": "storm",
                    "type": "storm",
                    "start": segment.start,
                    "end": segment.end,
                    "storm_at": segment.start,
                    "front_id": segment.front_id,
                    "lead": lead,
                    "confidence": round(confidence, 3),
                }
            index += 1
        return None

    def history(self, start, end):
        if (
            not isinstance(start, (int, float))
            or not math.isfinite(start)
            or not isinstance(end, (int, float))
            or not math.isfinite(end)
        ):
            raise ValueError("history bounds must be finite numbers")
        if end < start:
            raise ValueError("end cannot be before start")
        return self._intervals(start, end, merge_weather=False)
