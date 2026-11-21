import hashlib
import math
import random


MIN_SPACING = 0.5
MAX_SLOPE_DEG = 35.0
MAX_CULL_DISTANCE = 200.0
INSTANCE_BUDGET = 10000
LEVEL_COUNT = 3


class InstanceSet(list):
    """List of instances that also compares like a count."""

    @staticmethod
    def _coerce(other):
        if isinstance(other, bool):
            return NotImplemented
        if isinstance(other, (int, float)):
            return other
        if isinstance(other, (list, tuple)):
            return len(other)
        return NotImplemented

    def __eq__(self, other):
        value = self._coerce(other)
        if value is NotImplemented:
            return NotImplemented
        return len(self) == value

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __lt__(self, other):
        value = self._coerce(other)
        if value is NotImplemented:
            return NotImplemented
        return len(self) < value

    def __le__(self, other):
        value = self._coerce(other)
        if value is NotImplemented:
            return NotImplemented
        return len(self) <= value

    def __gt__(self, other):
        value = self._coerce(other)
        if value is NotImplemented:
            return NotImplemented
        return len(self) > value

    def __ge__(self, other):
        value = self._coerce(other)
        if value is NotImplemented:
            return NotImplemented
        return len(self) >= value


class FoliageScatter:
    def __init__(self):
        self._instances = InstanceSet()
        self._filtered = 0
        self._levels = [0] * LEVEL_COUNT
        self._seed_digest = None

    @staticmethod
    def _validate(area, density):
        if not isinstance(density, (int, float)) or isinstance(density, bool):
            raise ValueError("density must be a number")
        if density < 0:
            raise ValueError("density must be non-negative")
        if not isinstance(area, dict):
            raise ValueError("area must be a dict")
        try:
            width = area["width"]
            height = area["height"]
        except KeyError as exc:
            raise ValueError("area is missing dimensions") from exc
        if width <= 0 or height <= 0:
            raise ValueError("area dimensions must be positive")
        for key in ("heights", "water", "road"):
            grid = area.get(key)
            if not grid:
                raise ValueError(f"area[{key!r}] must be a non-empty grid")
            if len(grid) != height:
                raise ValueError(f"area[{key!r}] row count does not match height")
            for row in grid:
                if not row or len(row) != width:
                    raise ValueError(f"area[{key!r}] row size does not match width")
        return width, height

    @staticmethod
    def _slope_deg(heights, ix, iy, width, height):
        left = heights[iy][max(ix - 1, 0)]
        right = heights[iy][min(ix + 1, width - 1)]
        up = heights[max(iy - 1, 0)][ix]
        down = heights[min(iy + 1, height - 1)][ix]
        gx = (right - left) / (min(ix + 1, width - 1) - max(ix - 1, 0) or 1)
        gy = (down - up) / (min(iy + 1, height - 1) - max(iy - 1, 0) or 1)
        return math.degrees(math.atan(math.hypot(gx, gy)))

    def scatter(self, area, density, seed):
        width, height = self._validate(area, density)
        heights = area["heights"]
        water = area["water"]
        road = area["road"]

        rng = random.Random(seed)
        instances = InstanceSet()
        filtered = 0

        if density > 0:
            cell = 1.0 / math.sqrt(density)
            cols = max(1, math.ceil(width / cell))
            rows = max(1, math.ceil(height / cell))
            spacing_grid = {}

            def too_close(px, py):
                gx, gy = int(px / MIN_SPACING), int(py / MIN_SPACING)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for ox, oy in spacing_grid.get((gx + dx, gy + dy), ()):
                            if math.dist((px, py), (ox, oy)) < MIN_SPACING:
                                return True
                return False

            for row in range(rows):
                if len(instances) >= INSTANCE_BUDGET:
                    break
                for col in range(cols):
                    if len(instances) >= INSTANCE_BUDGET:
                        break
                    px = min((col + rng.random()) * cell, width - 1e-9)
                    py = min((row + rng.random()) * cell, height - 1e-9)
                    ix = min(int(px), width - 1)
                    iy = min(int(py), height - 1)
                    if water[iy][ix] == 0 or road[iy][ix] == 0:
                        filtered += 1
                        continue
                    if self._slope_deg(heights, ix, iy, width, height) > MAX_SLOPE_DEG:
                        filtered += 1
                        continue
                    if too_close(px, py):
                        filtered += 1
                        continue
                    key = (int(px / MIN_SPACING), int(py / MIN_SPACING))
                    spacing_grid.setdefault(key, []).append((px, py))
                    instances.append({
                        "x": px,
                        "y": py,
                        "rotation": rng.uniform(0.0, 2.0 * math.pi),
                        "scale": rng.uniform(0.8, 1.2),
                        "phase": rng.uniform(0.0, 2.0 * math.pi),
                    })

        self._instances = instances
        self._filtered = filtered
        self._levels = [0] * LEVEL_COUNT
        self._seed_digest = hashlib.sha256(repr(seed).encode("utf-8")).hexdigest()[:12]
        return {"instances": instances, "filtered": filtered}

    def cull(self, camera):
        position = camera.get("position", (0.0, 0.0))
        far = min(float(camera.get("far", MAX_CULL_DISTANCE)), MAX_CULL_DISTANCE)
        edges = (far / LEVEL_COUNT, 2.0 * far / LEVEL_COUNT, far)
        levels = [0] * LEVEL_COUNT
        for inst in self._instances:
            distance = math.dist(position, (inst["x"], inst["y"]))
            if distance > far:
                continue
            for index, edge in enumerate(edges):
                if distance <= edge:
                    levels[index] += 1
                    break
        self._levels = levels
        return {"levels": list(levels), "visible": sum(levels)}

    def ledger(self):
        return {
            "instances": len(self._instances),
            "filtered": self._filtered,
            "levels": list(self._levels),
            "seed": self._seed_digest,
        }
