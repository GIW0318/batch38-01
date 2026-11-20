from collections import deque
from math import ceil


TOTAL_BUDGET = 16.6
PASS_BUDGETS = {
    "render": TOTAL_BUDGET * 0.60,
    "logic": TOTAL_BUDGET * 0.25,
    "other": TOTAL_BUDGET * 0.15,
}
PASS_PRIORITY = ("other", "logic", "render")
WINDOW_SIZE = 60
SPIKE_MULTIPLIER = 2.0
SPIKE_STREAK = 3
DOWNSCALE_STREAK = 3
UPSCALE_STREAK = 120
MIN_SCALE = 0.5
MAX_SCALE = 1.0
SCALE_STEP = 0.1
EPSILON = 1e-9


class FrameGovernor:
    def __init__(self):
        self._samples = {name: deque(maxlen=WINDOW_SIZE) for name in PASS_BUDGETS}
        self._seen_frames = {name: set() for name in PASS_BUDGETS}
        self._spike_streaks = {name: 0 for name in PASS_BUDGETS}
        self._in_spike = {name: False for name in PASS_BUDGETS}
        self._spikes = {name: 0 for name in PASS_BUDGETS}

        self._frames = {}
        self._processed_frames = set()
        self._last_frame_total = None

        self._scale = MAX_SCALE
        self._over_streak = 0
        self._stable_streak = 0

    def record(self, pass_name, ms, frame):
        if pass_name not in PASS_BUDGETS:
            raise ValueError(f"unknown pass: {pass_name}")
        if ms < 0:
            raise ValueError("duration must not be negative")
        if frame in self._seen_frames[pass_name]:
            raise ValueError(f"duplicate frame {frame} for pass {pass_name}")

        self._seen_frames[pass_name].add(frame)
        self._record_spike(pass_name, ms)
        self._samples[pass_name].append(ms)
        self._frames.setdefault(frame, {})[pass_name] = ms

    def target(self, now):
        self._flush_frames()
        return {"scale": self._scale, "cut": self._suggested_cuts()}

    def budget(self):
        passes = {}
        for pass_name in PASS_BUDGETS:
            values = list(self._samples[pass_name])
            passes[pass_name] = {
                "mean": sum(values) / len(values) if values else 0.0,
                "p95": self._percentile(values, 95),
                "spikes": self._spikes[pass_name],
            }
        return {"passes": passes}

    def _record_spike(self, pass_name, ms):
        samples = self._samples[pass_name]
        if samples:
            mean = sum(samples) / len(samples)
            if ms > mean * SPIKE_MULTIPLIER:
                self._spike_streaks[pass_name] += 1
                if self._spike_streaks[pass_name] >= SPIKE_STREAK and not self._in_spike[pass_name]:
                    self._spikes[pass_name] += 1
                    self._in_spike[pass_name] = True
                return

        self._spike_streaks[pass_name] = 0
        self._in_spike[pass_name] = False

    def _flush_frames(self):
        for frame in sorted(self._frames):
            if frame in self._processed_frames:
                continue
            costs = self._frames[frame]
            if any(pass_name not in costs for pass_name in PASS_BUDGETS):
                continue

            self._processed_frames.add(frame)
            total = sum(costs.values())
            self._last_frame_total = total

            if total > TOTAL_BUDGET + EPSILON:
                self._over_streak += 1
                self._stable_streak = 0
                if self._over_streak >= DOWNSCALE_STREAK:
                    self._scale = round(max(MIN_SCALE, self._scale - SCALE_STEP), 2)
                    self._over_streak = 0
            else:
                self._stable_streak += 1
                self._over_streak = 0
                if self._stable_streak >= UPSCALE_STREAK:
                    self._scale = round(min(MAX_SCALE, self._scale + SCALE_STEP), 2)
                    self._stable_streak = 0

    def _suggested_cuts(self):
        if self._last_frame_total is None or self._last_frame_total <= TOTAL_BUDGET + EPSILON:
            return []

        cuts = []
        for pass_name in PASS_PRIORITY:
            values = self._samples[pass_name]
            if values and sum(values) / len(values) > PASS_BUDGETS[pass_name] + EPSILON:
                cuts.append(pass_name)
        return cuts

    @staticmethod
    def _percentile(values, percentile):
        if not values:
            return 0.0
        ordered = sorted(values)
        rank = max(1, ceil(percentile / 100.0 * len(ordered)))
        return ordered[rank - 1]
