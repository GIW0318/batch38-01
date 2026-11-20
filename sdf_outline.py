import math


OUTSIDE_DISTANCE = 1e6

OPS = ("union", "subtract", "intersect")


def _clamp(value, low, high):
    return max(low, min(high, value))


def _smoothstep(edge0, edge1, value):
    if edge0 == edge1:
        return 0.0 if value <= edge0 else 1.0
    t = _clamp((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class SdfOutline:
    def __init__(self, width=2.0, smooth=1.0):
        if width < 0:
            raise ValueError("outline width must not be negative")
        if smooth < 0:
            raise ValueError("smooth radius must not be negative")
        self.width = float(width)
        self.smooth = float(smooth)
        self._shapes = None
        self._box = None

    def build(self, shapes):
        if not shapes:
            raise ValueError("shapes must not be empty")

        prepared = []
        min_x = min_y = math.inf
        max_x = max_y = -math.inf

        for shape in shapes:
            kind = shape.get("type")
            op = shape.get("op", "union")
            if op not in OPS:
                raise ValueError("unknown op: {!r}".format(op))

            if kind == "circle":
                cx, cy, r = shape["cx"], shape["cy"], shape["r"]
                if r < 0:
                    raise ValueError("circle radius must not be negative")
                prepared.append(("circle", float(cx), float(cy), float(r), op))
                min_x = min(min_x, cx - r)
                max_x = max(max_x, cx + r)
                min_y = min(min_y, cy - r)
                max_y = max(max_y, cy + r)

            elif kind == "rect":
                cx, cy = shape["cx"], shape["cy"]
                w, h = shape["w"], shape["h"]
                if w < 0 or h < 0:
                    raise ValueError("rect dimensions must not be negative")
                half_w, half_h = w / 2.0, h / 2.0
                prepared.append(
                    ("rect", float(cx), float(cy), float(half_w), float(half_h), op)
                )
                min_x = min(min_x, cx - half_w)
                max_x = max(max_x, cx + half_w)
                min_y = min(min_y, cy - half_h)
                max_y = max(max_y, cy + half_h)

            elif kind == "segment":
                x1, y1 = shape["x1"], shape["y1"]
                x2, y2 = shape["x2"], shape["y2"]
                r = shape["r"]
                if r < 0:
                    raise ValueError("segment radius must not be negative")
                prepared.append(
                    (
                        "segment",
                        float(x1),
                        float(y1),
                        float(x2),
                        float(y2),
                        float(r),
                        op,
                    )
                )
                min_x = min(min_x, min(x1, x2) - r)
                max_x = max(max_x, max(x1, x2) + r)
                min_y = min(min_y, min(y1, y2) - r)
                max_y = max(max_y, max(y1, y2) + r)

            else:
                raise ValueError("unknown shape type: {!r}".format(kind))

        self._shapes = prepared
        self._box = (min_x, min_y, max_x, max_y)

    def _shape_distance(self, shape, x, y):
        kind = shape[0]

        if kind == "circle":
            _, cx, cy, r, _ = shape
            return math.hypot(x - cx, y - cy) - r

        if kind == "rect":
            _, cx, cy, half_w, half_h, _ = shape
            dx = abs(x - cx) - half_w
            dy = abs(y - cy) - half_h
            outside = math.hypot(max(dx, 0.0), max(dy, 0.0))
            inside = min(max(dx, dy), 0.0)
            return outside + inside

        _, x1, y1, x2, y2, r, _ = shape
        vx, vy = x2 - x1, y2 - y1
        length_sq = vx * vx + vy * vy
        if length_sq == 0.0:
            t = 0.0
        else:
            t = _clamp(
                ((x - x1) * vx + (y - y1) * vy) / length_sq, 0.0, 1.0
            )
        closest_x = x1 + t * vx
        closest_y = y1 + t * vy
        return math.hypot(x - closest_x, y - closest_y) - r

    def sample(self, x, y):
        if self._shapes is None:
            raise RuntimeError("build must be called before sample")

        x, y = float(x), float(y)
        reach = self.width / 2.0 + self.smooth
        min_x, min_y, max_x, max_y = self._box

        distance = None
        for shape in self._shapes:
            d = self._shape_distance(shape, x, y)
            op = shape[-1]
            if distance is None:
                distance = d
            elif op == "union":
                distance = min(distance, d)
            elif op == "subtract":
                distance = max(distance, -d)
            else:
                distance = max(distance, d)

        if (
            x < min_x - reach
            or x > max_x + reach
            or y < min_y - reach
            or y > max_y + reach
        ):
            return {"alpha": 0.0, "distance": OUTSIDE_DISTANCE}

        half_width = self.width / 2.0
        alpha = 1.0 - _smoothstep(
            half_width - self.smooth, half_width + self.smooth, distance
        )
        alpha = _clamp(alpha, 0.0, 1.0)
        return {"alpha": alpha, "distance": distance}

    def bounds(self):
        if self._box is None:
            raise RuntimeError("build must be called before bounds")
        min_x, min_y, max_x, max_y = self._box
        return {
            "count": len(self._shapes),
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
            "width": self.width,
            "smooth": self.smooth,
        }
