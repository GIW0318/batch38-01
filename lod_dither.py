import math
from numbers import Integral, Real


class LodDither:
    DEFAULT_THRESHOLDS = (30.0, 60.0, 120.0)
    HYSTERESIS = 0.05
    CROSSFADE_BAND = 0.10
    MIN_BIAS = -1.0
    MAX_BIAS = 2.0

    _BAYER_4X4 = (
        (0, 8, 2, 10),
        (12, 4, 14, 6),
        (3, 11, 1, 9),
        (15, 7, 13, 5),
    )

    def __init__(
        self,
        thresholds=None,
        msaa=False,
        *,
        msaa_enabled=None,
        alpha_to_coverage=None,
    ):
        if isinstance(thresholds, bool) and msaa is False and msaa_enabled is None:
            msaa = thresholds
            thresholds = None

        self._thresholds = self._validate_thresholds(thresholds)
        if msaa_enabled is not None:
            msaa = msaa_enabled
        if alpha_to_coverage is not None:
            msaa = alpha_to_coverage
        self._msaa = bool(msaa)

        self._current_level = None
        self._switch_counts = [0, 0, 0, 0]
        self._current_bias = 0.0

    @property
    def thresholds(self):
        return self._thresholds

    @property
    def msaa(self):
        return self._msaa

    @msaa.setter
    def msaa(self, enabled):
        self._msaa = bool(enabled)

    @property
    def msaa_enabled(self):
        return self._msaa

    @msaa_enabled.setter
    def msaa_enabled(self, enabled):
        self._msaa = bool(enabled)

    @property
    def alpha_to_coverage(self):
        return self._msaa

    @alpha_to_coverage.setter
    def alpha_to_coverage(self, enabled):
        self._msaa = bool(enabled)

    @classmethod
    def _validate_thresholds(cls, thresholds):
        if thresholds is None:
            thresholds = cls.DEFAULT_THRESHOLDS

        try:
            values = tuple(float(value) for value in thresholds)
        except (TypeError, ValueError):
            raise ValueError("thresholds must contain three finite numbers") from None

        if len(values) != 3:
            raise ValueError("exactly three LOD thresholds are required")
        if any(not math.isfinite(value) or value <= 0.0 for value in values):
            raise ValueError("thresholds must be positive finite numbers")
        if any(left >= right for left, right in zip(values, values[1:])):
            raise ValueError("thresholds must be strictly increasing")
        return values

    @staticmethod
    def _validate_distance(distance):
        if isinstance(distance, bool) or not isinstance(distance, Real):
            raise ValueError("distance must be a non-negative finite number")
        value = float(distance)
        if not math.isfinite(value) or value < 0.0:
            raise ValueError("distance must be a non-negative finite number")
        return value

    @staticmethod
    def _clamp_bias(lod_bias):
        if isinstance(lod_bias, bool) or not isinstance(lod_bias, Real):
            raise ValueError("lod_bias must be a finite number")
        value = float(lod_bias)
        if not math.isfinite(value):
            raise ValueError("lod_bias must be a finite number")
        return min(LodDither.MAX_BIAS, max(LodDither.MIN_BIAS, value))

    @staticmethod
    def _validate_coordinate(value, name):
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise ValueError(f"{name} must be an integer")
        return int(value) % 4

    @staticmethod
    def _validate_frame(frame):
        if isinstance(frame, bool) or not isinstance(frame, Integral):
            raise ValueError("frame must be a non-negative integer")
        value = int(frame)
        if value < 0:
            raise ValueError("frame must be a non-negative integer")
        return value

    def _first_level(self, distance):
        level = 0
        for threshold in self._thresholds:
            if distance < threshold:
                break
            level += 1
        return level

    def _next_level(self, level, distance):
        while (
            level < len(self._thresholds)
            and distance >= self._thresholds[level]
        ):
            level += 1

        while (
            level > 0
            and distance < self._thresholds[level - 1] * (1.0 - self.HYSTERESIS)
        ):
            level -= 1
        return level

    def _blend_for(self, level, distance):
        boundaries = []
        if level > 0:
            boundaries.append(self._thresholds[level - 1])
        if level < len(self._thresholds):
            boundaries.append(self._thresholds[level])

        half_band = self.CROSSFADE_BAND * 0.5
        for boundary in boundaries:
            lower = boundary * (1.0 - half_band)
            upper = boundary * (1.0 + half_band)
            if lower <= distance <= upper:
                return min(1.0, max(0.0, (distance - lower) / (upper - lower)))
        return 0.0

    def select(self, distance, lod_bias):
        distance = self._validate_distance(distance)
        bias = self._clamp_bias(lod_bias)
        effective_distance = distance * (2.0 ** bias)

        previous_level = self._current_level
        if previous_level is None:
            level = self._first_level(effective_distance)
        else:
            level = self._next_level(previous_level, effective_distance)

        if level != previous_level:
            self._switch_counts[level] += 1

        self._current_level = level
        self._current_bias = bias
        blend = self._blend_for(level, effective_distance)
        use_alpha_to_coverage = self._msaa and blend > 0.0

        return {
            "level": level,
            "blend": blend,
            "alpha_to_coverage": use_alpha_to_coverage,
            "blend_mode": (
                "alpha_to_coverage" if use_alpha_to_coverage else "alpha_blend"
            ),
        }

    def pattern(self, x, y, frame):
        x = self._validate_coordinate(x, "x")
        y = self._validate_coordinate(y, "y")
        frame = self._validate_frame(frame)

        bayer_value = self._BAYER_4X4[y][x]
        phase = (frame % 8) * 2
        return int(((bayer_value + phase) % 16) >= 8)

    def detail(self):
        return {
            "switches": list(self._switch_counts),
            "bias": self._current_bias,
        }
