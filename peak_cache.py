import threading


class PeakCache:
    _ALLOWED_BLOCKS = (64, 128, 256, 512)
    _CLIP_THRESHOLD = 1.0
    _BYTES_PER_VALUE = 8

    def __init__(self):
        self._lock = threading.RLock()
        self._samples = []
        self._channels = 0
        self._block = 0
        self._frames = 0
        self._levels = []
        self._last_used = []
        self._pinned = []
        self._version = 0
        self._queries = 0
        self._tick = 0

    def build(self, samples, channels, block):
        if block not in self._ALLOWED_BLOCKS:
            raise ValueError("block must be one of %s" % (self._ALLOWED_BLOCKS,))
        if channels < 1:
            raise ValueError("channels must be >= 1")
        samples = list(samples)
        if len(samples) % channels != 0:
            raise ValueError("sample count must be a multiple of channels")
        with self._lock:
            self._samples = samples
            self._channels = channels
            self._block = block
            self._frames = len(samples) // channels
            self._levels = []
            self._version = 0
            self._queries = 0
            if self._frames > 0:
                self._levels.append(self._compute_level_zero())
                while len(self._levels[-1]) > 1:
                    self._levels.append(self._merge_level(self._levels[-1]))
            self._last_used = [0] * len(self._levels)
            self._pinned = [0] * len(self._levels)

    def update(self, start, samples, channels):
        samples = list(samples)
        with self._lock:
            if self._channels == 0:
                raise ValueError("cache has not been built")
            if channels != self._channels:
                raise ValueError("channel count does not match build")
            if len(samples) % channels != 0:
                raise ValueError("sample count must be a multiple of channels")
            count = len(samples) // channels
            if start < 0 or start + count > self._frames:
                raise ValueError("update range out of bounds")
            self._samples[start * channels:(start + count) * channels] = samples
            if count > 0 and self._levels:
                first = start // self._block
                last = (start + count - 1) // self._block
                level_zero = self._levels[0]
                for index in range(first, last + 1):
                    level_zero[index] = self._compute_block(index)
                for li in range(1, len(self._levels)):
                    first //= 2
                    last //= 2
                    child = self._levels[li - 1]
                    for index in range(first, last + 1):
                        self._levels[li][index] = self._merge_block(child, index)
            self._version += 1

    def query(self, start, end, level, channel):
        with self._lock:
            if start < 0:
                raise ValueError("start must be >= 0")
            if end > self._frames:
                raise ValueError("end exceeds sample length")
            if start > end:
                raise ValueError("start must be <= end")
            if level < 0 or level >= len(self._levels):
                raise ValueError("level out of range")
            if channel < 0 or channel >= self._channels:
                raise ValueError("channel out of range")
            self._queries += 1
            self._pinned[level] += 1
            try:
                self._tick += 1
                self._last_used[level] = self._tick
                if start == end:
                    return {"min": 0.0, "max": 0.0, "clipped": False}
                span = self._block << level
                first = start // span
                last = (end - 1) // span
                blocks = self._levels[level]
                low = min(blocks[i][channel][0] for i in range(first, last + 1))
                high = max(blocks[i][channel][1] for i in range(first, last + 1))
                clipped = (
                    high >= self._CLIP_THRESHOLD or low <= -self._CLIP_THRESHOLD
                )
                return {"min": low, "max": high, "clipped": clipped}
            finally:
                self._pinned[level] -= 1

    def evict(self, budget_bytes):
        with self._lock:
            while self._memory() > budget_bytes and len(self._levels) > 1:
                highest_pinned = 0
                for li in range(1, len(self._levels)):
                    if self._pinned[li] > 0:
                        highest_pinned = li
                candidates = range(highest_pinned + 1, len(self._levels))
                if not candidates:
                    break
                coldest = min(
                    candidates, key=lambda li: (self._last_used[li], -li)
                )
                del self._levels[coldest:]
                del self._last_used[coldest:]
                del self._pinned[coldest:]

    def stats(self):
        with self._lock:
            return {
                "levels": len(self._levels),
                "blocks": len(self._levels[0]) if self._levels else 0,
                "memory": self._memory(),
                "version": self._version,
                "queries": self._queries,
            }

    def _memory(self):
        per_block = self._channels * 2 * self._BYTES_PER_VALUE
        return sum(len(level) for level in self._levels) * per_block

    def _compute_level_zero(self):
        count = (self._frames + self._block - 1) // self._block
        return [self._compute_block(index) for index in range(count)]

    def _compute_block(self, index):
        begin = index * self._block
        end = min(begin + self._block, self._frames)
        result = []
        for ch in range(self._channels):
            values = self._samples[begin * self._channels + ch:
                                   end * self._channels:self._channels]
            result.append((min(values), max(values)))
        return result

    def _merge_level(self, child):
        count = (len(child) + 1) // 2
        return [self._merge_block(child, index) for index in range(count)]

    def _merge_block(self, child, index):
        left = child[index * 2]
        if index * 2 + 1 < len(child):
            right = child[index * 2 + 1]
            return [
                (min(l[0], r[0]), max(l[1], r[1]))
                for l, r in zip(left, right)
            ]
        return list(left)
