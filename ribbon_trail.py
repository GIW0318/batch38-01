_EPS = 1e-9


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(v):
    return (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5


def _normalize(v):
    n = _length(v)
    if n < _EPS:
        return None
    return (v[0] / n, v[1] / n, v[2] / n)


def _lerp(a, b, t):
    return a + (b - a) * t


class _Point:
    __slots__ = ("pos", "time", "cum_len")

    def __init__(self, pos, time, cum_len):
        self.pos = pos
        self.time = time
        self.cum_len = cum_len


class _Trail:
    __slots__ = ("id", "created_at", "points", "last_emit", "last_side")

    def __init__(self, trail_id, created_at):
        self.id = trail_id
        self.created_at = created_at
        self.points = []
        self.last_emit = created_at
        self.last_side = None


class TrailPool:
    DEFAULT_WIDTH_CURVE = (1.0, 0.75, 0.4, 0.0)
    DEPTH_OFFSET_STEP = 1e-4

    def __init__(self, lifetime=2.0, spacing=0.1, width_curve=None, capacity=32):
        if lifetime < 0:
            raise ValueError("lifetime must be >= 0 seconds")
        if spacing <= 0:
            raise ValueError("spacing must be > 0 meters")
        curve = list(width_curve) if width_curve is not None else list(self.DEFAULT_WIDTH_CURVE)
        if len(curve) < 4:
            raise ValueError("width_curve needs at least 4 control points")
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.lifetime = float(lifetime)
        self.spacing = float(spacing)
        self.width_curve = [float(w) for w in curve]
        self.capacity = int(capacity)
        self._trails = []
        self._next_id = 0
        self._evicted = 0
        self._expired = 0

    def start_trail(self, now):
        trail = _Trail(self._next_id, float(now))
        self._next_id += 1
        self._trails.append(trail)
        while len(self._trails) > self.capacity:
            self._trails.pop(0)
            self._evicted += 1
        return trail.id

    def emit(self, point, now):
        if point is None or len(point) != 3:
            raise ValueError("point must be a 3-component sequence")
        pos = (float(point[0]), float(point[1]), float(point[2]))
        now = float(now)
        if not self._trails:
            self.start_trail(now)
        trail = self._trails[-1]
        trail.last_emit = now
        if not trail.points:
            trail.points.append(_Point(pos, now, 0.0))
            return
        start = trail.points[-1]
        dist = _length(_sub(pos, start.pos))
        if dist < _EPS:
            start.time = now
            return
        traveled = self.spacing
        while traveled < dist - _EPS:
            frac = traveled / dist
            trail.points.append(_Point(
                (
                    _lerp(start.pos[0], pos[0], frac),
                    _lerp(start.pos[1], pos[1], frac),
                    _lerp(start.pos[2], pos[2], frac),
                ),
                _lerp(start.time, now, frac),
                start.cum_len + traveled,
            ))
            traveled += self.spacing
        if dist - (traveled - self.spacing) > _EPS:
            trail.points.append(_Point(pos, now, start.cum_len + dist))

    def update(self, now):
        now = float(now)
        kept = []
        for trail in self._trails:
            points = trail.points
            head = 0
            while head < len(points) and now - points[head].time > self.lifetime:
                head += 1
            if head:
                del points[:head]
            if points or now - trail.last_emit <= self.lifetime:
                kept.append(trail)
            else:
                self._expired += 1
        self._trails = kept

    def build(self, camera):
        cam_pos = (0.0, 0.0, 0.0)
        if camera:
            cam_pos = tuple(float(c) for c in camera.get("position", cam_pos))
        vertices = 0
        indices = 0
        meshes = []
        ordered = sorted(self._trails, key=lambda t: (t.created_at, t.id))
        for order, trail in enumerate(ordered):
            points = trail.points
            if not points:
                continue
            depth_offset = order * self.DEPTH_OFFSET_STEP
            decorated = self._decorate(trail)
            positions = []
            uvs = []
            prev_side = trail.last_side
            for i, info in enumerate(decorated):
                pos = info["position"]
                if len(points) == 1:
                    tangent = None
                elif i == 0:
                    tangent = _normalize(_sub(points[1].pos, pos))
                elif i == len(points) - 1:
                    tangent = _normalize(_sub(pos, points[i - 1].pos))
                else:
                    tangent = _normalize(_sub(points[i + 1].pos, points[i - 1].pos))
                side = None
                if tangent is not None:
                    to_camera = _sub(cam_pos, pos)
                    side = _normalize(_cross(tangent, to_camera))
                if side is None:
                    side = prev_side if prev_side is not None else (1.0, 0.0, 0.0)
                prev_side = side
                view_dir = _normalize(_sub(cam_pos, pos)) or (0.0, 0.0, 1.0)
                half = info["width"] * 0.5
                base = (
                    pos[0] + view_dir[0] * depth_offset,
                    pos[1] + view_dir[1] * depth_offset,
                    pos[2] + view_dir[2] * depth_offset,
                )
                positions.append(tuple(base[c] - side[c] * half for c in range(3)))
                positions.append(tuple(base[c] + side[c] * half for c in range(3)))
                uvs.append((0.0, info["v"]))
                uvs.append((1.0, info["v"]))
            trail.last_side = prev_side
            n = len(decorated)
            vertices += 2 * n
            if n >= 2:
                indices += 6 * (n - 1)
            meshes.append({
                "id": trail.id,
                "depth_offset": depth_offset,
                "positions": positions,
                "uvs": uvs,
            })
        return {"vertices": vertices, "indices": indices, "trails": meshes}

    def inspect(self, trail_id):
        for trail in self._trails:
            if trail.id == trail_id:
                return {"id": trail.id, "points": self._decorate(trail)}
        return {}

    def snapshot(self):
        return {
            "active": len(self._trails),
            "points": sum(len(t.points) for t in self._trails),
            "evicted": self._evicted,
            "expired": self._expired,
            "trail_ids": [t.id for t in self._trails],
        }

    def _width(self, u):
        curve = self.width_curve
        pos = u * (len(curve) - 1)
        idx = int(pos)
        if idx >= len(curve) - 1:
            return curve[-1]
        return _lerp(curve[idx], curve[idx + 1], pos - idx)

    def _decorate(self, trail):
        points = trail.points
        n = len(points)
        if n == 0:
            return []
        first_cum = points[0].cum_len
        total = points[-1].cum_len - first_cum
        decorated = []
        for i, p in enumerate(points):
            u = i / (n - 1) if n > 1 else 0.0
            v = (p.cum_len - first_cum) / total if total > _EPS else 0.0
            decorated.append({
                "position": p.pos,
                "time": p.time,
                "width": self._width(u),
                "v": v,
            })
        return decorated
