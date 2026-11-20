import math
from bisect import bisect_left, bisect_right
from numbers import Real


SAMPLE_RATE = 48000
SMOOTHING_MS = 20.0
VALID_CURVES = ("linear", "hold", "exponential")
VALID_LAYERS = (0, 1, 2)


def _is_real_number(value):
    return isinstance(value, Real) and not isinstance(value, bool)


class AutomationLane:
    def __init__(self):
        self._lanes = {}
        self._smoother = {}

    def add(self, lane, point):
        if not isinstance(lane, str) or not lane:
            raise ValueError("lane must be a non-empty string")
        if not isinstance(point, dict):
            raise ValueError("point must be a dict with time, value and curve")

        time = point.get("time")
        raw_value = point.get("value")
        curve = point.get("curve", "linear")
        layer = point.get("layer", 0)

        if not _is_real_number(time) or not math.isfinite(time) or time < 0:
            raise ValueError("time must be a finite, non-negative number")
        if not _is_real_number(raw_value) or math.isnan(raw_value):
            raise ValueError("value must be a real number and must not be NaN")
        if curve not in VALID_CURVES:
            raise ValueError("curve must be one of %s" % (VALID_CURVES,))
        if layer not in VALID_LAYERS:
            raise ValueError("layer must be one of %s" % (VALID_LAYERS,))

        entry = self._lanes.setdefault(
            lane, {"layers": {layer: [] for layer in VALID_LAYERS}}
        )
        points = entry["layers"][layer]
        new_point = {"time": float(time), "value": float(raw_value), "curve": curve}

        candidate = [dict(item) for item in points]
        index = bisect_left([item["time"] for item in candidate], new_point["time"])
        if index < len(candidate) and candidate[index]["time"] == new_point["time"]:
            if layer == 0:
                raise ValueError("duplicate time %r is not allowed" % time)
            candidate[index] = new_point
        else:
            candidate.insert(index, new_point)

        self._validate_exponential_segments(candidate)

        points[:] = candidate
    def value(self, lane, t):
        if lane not in self._lanes:
            raise ValueError("unknown lane %r" % lane)
        if not _is_real_number(t) or not math.isfinite(t):
            raise ValueError("t must be a finite number")

        sample = max(0, int(round(t * SAMPLE_RATE)))
        target = self._raw_value(lane, sample / SAMPLE_RATE)
        target = min(1.0, max(0.0, target))
        smoothed = self._smooth(lane, sample, target)
        return min(1.0, max(0.0, smoothed))

    def blend(self, lane_a, lane_b, t):
        value_a = self.value(lane_a, t)
        value_b = self.value(lane_b, t)
        mixed = math.sqrt(value_a * value_a + value_b * value_b)
        return min(1.0, max(0.0, mixed))

    def lanes(self):
        report = {}
        for name, entry in self._lanes.items():
            all_points = []
            active_layers = []
            for layer in VALID_LAYERS:
                layer_points = entry["layers"][layer]
                if layer_points:
                    active_layers.append(layer)
                    all_points.extend(layer_points)
            times = [point["time"] for point in all_points]
            state = self._smoother.get(name)
            report[name] = {
                "point_count": len(all_points),
                "start_time": min(times),
                "end_time": max(times),
                "layer": active_layers[0],
                "layers": list(active_layers),
                "current_value": state["value"] if state else 0.0,
            }
        return {
            "sample_rate": SAMPLE_RATE,
            "smoothing_ms": SMOOTHING_MS,
            "lanes": report,
        }

    def _validate_exponential_segments(self, points):
        for left, right in zip(points, points[1:]):
            if left["curve"] == "exponential":
                if left["value"] <= 0 or right["value"] <= 0:
                    raise ValueError(
                        "exponential segments require both endpoints to be greater than 0"
                    )

    def _active_layer(self, lane):
        layers = self._lanes[lane]["layers"]
        for layer in VALID_LAYERS:
            if layers[layer]:
                return layer
        raise ValueError("lane %r has no points" % lane)

    def _raw_value(self, lane, t):
        layer = self._active_layer(lane)
        points = self._lanes[lane]["layers"][layer]
        times = [point["time"] for point in points]

        if t <= times[0]:
            return points[0]["value"]
        if t >= times[-1]:
            return points[-1]["value"]

        index = bisect_right(times, t)
        left = points[index - 1]
        right = points[index]
        if left["curve"] == "hold":
            return left["value"]

        span = right["time"] - left["time"]
        fraction = 0.0 if span == 0 else (t - left["time"]) / span
        if left["curve"] == "exponential":
            return left["value"] * math.pow(right["value"] / left["value"], fraction)
        return left["value"] + fraction * (right["value"] - left["value"])

    def _smooth(self, lane, sample, target):
        state = self._smoother.get(lane)
        if state is None or sample <= state["sample"]:
            self._smoother[lane] = {"sample": sample, "value": target}
            return target

        elapsed_samples = sample - state["sample"]
        time_constant_samples = SAMPLE_RATE * SMOOTHING_MS / 1000.0
        coefficient = math.exp(-elapsed_samples / time_constant_samples)
        smoothed = target + (state["value"] - target) * coefficient
        state["sample"] = sample
        state["value"] = smoothed
        return smoothed
