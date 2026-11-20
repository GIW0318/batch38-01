import math

_FADE_ANGLE_DEG = 60.0
_DEPTH_OFFSET_RATIO = 0.001


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _length(v):
    return math.sqrt(_dot(v, v))


class DecalPool:
    def __init__(self, capacity=64):
        self.capacity = capacity
        self._decals = []
        self._evicted = 0

    def add(self, decal, now):
        size = decal["size"]
        if size <= 0:
            raise ValueError("decal size must be positive")
        normal = decal["normal"]
        normal_len = _length(normal)
        if normal_len == 0.0:
            raise ValueError("decal normal must be non-zero")
        if decal["lifetime"] < 0:
            raise ValueError("decal lifetime must be non-negative")

        entry = dict(decal)
        entry["normal"] = (
            normal[0] / normal_len,
            normal[1] / normal_len,
            normal[2] / normal_len,
        )
        entry["created"] = now
        entry["depth_offset"] = size * _DEPTH_OFFSET_RATIO
        self._decals.append(entry)

        if len(self._decals) > self.capacity:
            victim = min(self._decals, key=lambda d: (d["priority"], d["created"]))
            self._decals.remove(victim)
            self._evicted += 1
        return entry

    def project(self, point):
        best = 0.0
        for entry in self._decals:
            alpha = self._project_one(entry, point)
            if alpha > best:
                best = alpha
        return best

    def _project_one(self, entry, point):
        rel = _sub(point, entry["position"])
        normal = entry["normal"]
        along = _dot(rel, normal)
        if along < 0.0:
            return 0.0
        size = entry["size"]
        if along > size:
            return 0.0
        tangent = (
            rel[0] - along * normal[0],
            rel[1] - along * normal[1],
            rel[2] - along * normal[2],
        )
        if _length(tangent) > size:
            return 0.0
        dist = _length(rel)
        if dist == 0.0:
            return 1.0
        cos_angle = along / dist
        angle = math.degrees(math.acos(max(-1.0, min(1.0, cos_angle))))
        if angle >= _FADE_ANGLE_DEG:
            return 0.0
        return 1.0 - angle / _FADE_ANGLE_DEG

    def expire(self, now):
        kept = [
            d for d in self._decals if now - d["created"] < d["lifetime"]
        ]
        removed = len(self._decals) - len(kept)
        self._decals = kept
        return removed

    def decals(self):
        ordered = sorted(
            self._decals, key=lambda d: (-d["priority"], d["created"])
        )
        return {
            "active": len(self._decals),
            "evicted": self._evicted,
            "items": [dict(d) for d in ordered],
        }
