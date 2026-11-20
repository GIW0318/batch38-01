SIZE_CLASS_MIN = 256
SIZE_CLASS_MAX = 64 * 1024 * 1024

_KIND_PRIORITY = {"transient": 0, "buffer": 1, "texture": 2}


def _priority(kind):
    return _KIND_PRIORITY.get(kind, 1)


class _Block:
    __slots__ = ("size", "offset", "kind", "tag", "pinned", "created", "handles")

    def __init__(self, size, offset, kind, tag, created):
        self.size = size
        self.offset = offset
        self.kind = kind
        self.tag = tag
        self.pinned = False
        self.created = created
        self.handles = set()

    @property
    def live(self):
        return bool(self.handles)


class GpuBudget:
    def __init__(self, limit=1024 * 1024):
        self.limit = limit
        self._blocks = []
        self._handles = {}
        self._handle_seq = 0
        self._clock = 0
        self._peak = 0

    def alloc(self, size, kind="buffer", tag=""):
        if size is None or size < 0:
            raise ValueError("size must be non-negative")
        if size > SIZE_CLASS_MAX:
            raise ValueError("size exceeds largest size class")
        class_size = SIZE_CLASS_MIN
        while class_size < size:
            class_size *= 2
        if kind == "transient":
            shared = self._find_transient(class_size)
            if shared is not None:
                return self._attach(shared)
        self._ensure_budget(class_size, kind)
        block = self._reuse_free(class_size)
        if block is None:
            offset = max((b.offset + b.size for b in self._blocks), default=0)
            block = _Block(class_size, offset, kind, tag, self._tick())
            self._blocks.append(block)
        else:
            block.kind = kind
            block.tag = tag
            block.pinned = False
            block.created = self._tick()
        return self._attach(block)

    def free(self, handle):
        block = self._handles.pop(handle, None)
        if block is None:
            raise ValueError("unknown or already freed handle")
        block.handles.discard(handle)

    def pin(self, handle):
        self._lookup(handle).pinned = True

    def unpin(self, handle):
        self._lookup(handle).pinned = False

    def defrag(self, now):
        live = sorted((b for b in self._blocks if b.live), key=lambda b: b.offset)
        pinned_intervals = sorted(
            (b.offset, b.offset + b.size) for b in live if b.pinned
        )
        cursor = 0
        for block in live:
            if block.pinned:
                continue
            for start, end in pinned_intervals:
                if start <= cursor < end:
                    cursor = end
            block.offset = cursor
            cursor += block.size
        self._blocks = list(live)
        pos = 0
        for block in live:
            if block.offset > pos:
                self._blocks.append(
                    _Block(block.offset - pos, pos, "free", "", self._tick())
                )
            pos = max(pos, block.offset + block.size)

    def usage(self):
        total = len(self._blocks)
        free_count = sum(1 for b in self._blocks if not b.live)
        kinds = {}
        for block in self._blocks:
            if block.live:
                kinds[block.kind] = kinds.get(block.kind, 0) + block.size
        return {
            "used": self._used(),
            "peak": self._peak,
            "fragmentation": (free_count / total) if total else 0.0,
            "kinds": kinds,
        }

    def _tick(self):
        self._clock += 1
        return self._clock

    def _used(self):
        return sum(b.size for b in self._blocks if b.live)

    def _lookup(self, handle):
        block = self._handles.get(handle)
        if block is None:
            raise ValueError("unknown or already freed handle")
        return block

    def _attach(self, block):
        self._handle_seq += 1
        handle = self._handle_seq
        block.handles.add(handle)
        self._handles[handle] = block
        self._peak = max(self._peak, self._used())
        return {"handle": handle, "offset": block.offset, "size": block.size}

    def _find_transient(self, class_size):
        for block in self._blocks:
            if block.live and block.kind == "transient" and block.size >= class_size:
                return block
        return None

    def _reuse_free(self, class_size):
        for block in self._blocks:
            if not block.live and block.size == class_size:
                return block
        return None

    def _ensure_budget(self, class_size, kind):
        incoming = _priority(kind)
        while self._used() + class_size > self.limit:
            candidates = [
                b
                for b in self._blocks
                if b.live and not b.pinned and _priority(b.kind) < incoming
            ]
            if not candidates:
                raise ValueError("budget exceeded and nothing evictable")
            victim = min(candidates, key=lambda b: (_priority(b.kind), b.created))
            self._evict(victim)

    def _evict(self, block):
        for handle in block.handles:
            del self._handles[handle]
        block.handles.clear()
        block.pinned = False
