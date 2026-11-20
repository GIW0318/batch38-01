import copy
import math


LAYOUTS = {
    "mono": ("M",),
    "stereo": ("FL", "FR"),
    "5.1": ("FL", "FR", "C", "LFE", "SL", "SR"),
    "7.1": ("FL", "FR", "C", "LFE", "BL", "BR", "SL", "SR"),
}

LAYOUT_LATENCY = {
    "mono": 0,
    "stereo": 0,
    "5.1": 8,
    "7.1": 12,
}

CENTER_GAIN = 1.0 / math.sqrt(2)
SURROUND_GAIN = 1.0 / math.sqrt(2)
LFE_GAIN = 0.5
BACK_GAIN = 0.5

MIN_RATE_RATIO = 0.5
MAX_RATE_RATIO = 2.0

STEREO_GAINS = {
    "FL": {"L": 1.0},
    "FR": {"R": 1.0},
    "C": {"L": CENTER_GAIN, "R": CENTER_GAIN},
    "LFE": {"L": LFE_GAIN, "R": LFE_GAIN},
    "SL": {"L": SURROUND_GAIN},
    "SR": {"R": SURROUND_GAIN},
    "BL": {"L": BACK_GAIN},
    "BR": {"R": BACK_GAIN},
    "M": {"L": 1.0, "R": 1.0},
}


def _row_names(layout):
    if layout == "stereo":
        return ["L", "R"]
    return list(LAYOUTS[layout])


def _resample_linear(signal, ratio, length):
    n = len(signal)
    result = []
    for index in range(length):
        position = index / ratio
        lower = int(math.floor(position))
        if lower >= n - 1:
            result.append(signal[-1])
            continue
        fraction = position - lower
        result.append(signal[lower] * (1.0 - fraction) + signal[lower + 1] * fraction)
    return result


class DownmixEngine:
    def __init__(self):
        self._source = None
        self._target = None
        self._matrix = {}
        self._normalization = {}
        self._latency = 0

    def _check_layout(self, layout):
        if layout not in LAYOUTS:
            raise ValueError(f"unknown channel layout: {layout!r}")

    def _infer_layout(self, sample_count):
        for name, channels in LAYOUTS.items():
            if len(channels) == sample_count:
                return name
        raise ValueError("cannot infer source layout from sample count")

    def _build_matrix(self, source, target):
        self._check_layout(source)
        self._check_layout(target)
        source_channels = LAYOUTS[source]

        if source == target:
            rows = {name: {name: 1.0} for name in source_channels}
        elif target == "stereo":
            rows = {"L": {}, "R": {}}
            for channel in source_channels:
                for row, gain in STEREO_GAINS.get(channel, {}).items():
                    rows[row][channel] = gain
        elif target == "mono":
            rows = {"M": {}}
            for channel in source_channels:
                gains = STEREO_GAINS.get(channel, {})
                gain = (gains.get("L", 0.0) + gains.get("R", 0.0)) / 2.0
                if gain:
                    rows["M"][channel] = gain
        else:
            rows = {name: {} for name in LAYOUTS[target]}
            for channel in source_channels:
                if channel in rows:
                    rows[channel][channel] = 1.0

        normalization = {}
        for row, coefficients in rows.items():
            normalization[row] = 1.0
            if not coefficients:
                continue
            peak = max(abs(value) for value in coefficients.values())
            if peak > 1.0:
                factor = 1.0 / peak
                normalization[row] = factor
                rows[row] = {name: value * factor for name, value in coefficients.items()}
        return rows, normalization

    def matrix(self, source, target):
        rows, normalization = self._build_matrix(source, target)
        self._source = source
        self._target = target
        self._matrix = copy.deepcopy(rows)
        self._normalization = copy.deepcopy(normalization)
        self._latency = self.latency(source, target)
        return copy.deepcopy(rows)

    def latency(self, source, target):
        self._check_layout(source)
        self._check_layout(target)
        return LAYOUT_LATENCY[source] + LAYOUT_LATENCY[target]

    def _configure(self, source, target):
        if self._source != source or self._target != target:
            rows, normalization = self._build_matrix(source, target)
            self._source = source
            self._target = target
            self._matrix = rows
            self._normalization = normalization
            self._latency = self.latency(source, target)

    def apply(self, samples, source_rate, target_rate):
        if not samples:
            raise ValueError("empty input samples")
        data = [float(value) for value in samples]

        source = self._source
        if source is None:
            source = self._infer_layout(len(data))
        self._check_layout(source)
        target = self._target or "stereo"
        self._check_layout(target)

        source_channels = LAYOUTS[source]
        if len(data) % len(source_channels) != 0:
            raise ValueError("sample count is not an integer multiple of the source channel count")

        if not isinstance(source_rate, (int, float)) or not isinstance(target_rate, (int, float)):
            raise ValueError("sample rates must be numbers")
        if source_rate <= 0 or target_rate <= 0:
            raise ValueError("sample rates must be positive")
        ratio = target_rate / source_rate
        if not (MIN_RATE_RATIO <= ratio <= MAX_RATE_RATIO):
            raise ValueError(
                f"sample rate ratio {ratio:.4f} outside [{MIN_RATE_RATIO}, {MAX_RATE_RATIO}]"
            )

        self._configure(source, target)
        matrix = self._matrix
        source_index = {channel: index for index, channel in enumerate(source_channels)}
        output_rows = _row_names(target)
        frame_count = len(data) // len(source_channels)

        mixed = [[] for _ in output_rows]
        for frame_index in range(frame_count):
            start = frame_index * len(source_channels)
            frame = data[start:start + len(source_channels)]
            for row_index, row in enumerate(output_rows):
                value = 0.0
                for channel, gain in matrix.get(row, {}).items():
                    value += gain * frame[source_index[channel]]
                mixed[row_index].append(math.tanh(value))

        delay = LAYOUT_LATENCY[source]
        output_length = max(1, math.ceil(frame_count * ratio))
        output_channels = []
        for channel in mixed:
            padded = [0.0] * delay + channel
            aligned = _resample_linear(padded, ratio, math.ceil(len(padded) * ratio))
            lag = round(delay * ratio)
            aligned = aligned[lag:lag + output_length]
            if len(aligned) < output_length:
                fill = aligned[-1] if aligned else (channel[-1] if channel else 0.0)
                aligned.extend([fill] * (output_length - len(aligned)))
            output_channels.append(aligned)

        interleaved = []
        for frame_index in range(output_length):
            for channel in output_channels:
                interleaved.append(channel[frame_index])
        return interleaved

    def state(self):
        return {
            "source": self._source,
            "target": self._target,
            "matrix": copy.deepcopy(self._matrix),
            "normalization": copy.deepcopy(self._normalization),
            "latency": self._latency,
        }
