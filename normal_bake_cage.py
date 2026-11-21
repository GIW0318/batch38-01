"""Cage-based normal map baker.

Casts rays from the low-poly surface (offset along the vertex normal,
clamped to twice the cage thickness) against the high-poly mesh and
writes tangent-space normals derived from UV derivatives.
"""

_NEUTRAL = (128, 128, 255)
_EPS = 1e-12


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(a):
    return _dot(a, a) ** 0.5


def _normalize(a):
    mag = _length(a)
    if mag < _EPS:
        return (0.0, 0.0, 1.0)
    return (a[0] / mag, a[1] / mag, a[2] / mag)


def _ray_triangle(origin, direction, v0, v1, v2, max_dist):
    """Moller-Trumbore; returns (t, u, v) of the hit or None."""
    edge1 = _sub(v1, v0)
    edge2 = _sub(v2, v0)
    pvec = _cross(direction, edge2)
    det = _dot(edge1, pvec)
    if abs(det) < _EPS:
        return None
    inv = 1.0 / det
    tvec = _sub(origin, v0)
    u = _dot(tvec, pvec) * inv
    if u < 0.0 or u > 1.0:
        return None
    qvec = _cross(tvec, edge1)
    v = _dot(direction, qvec) * inv
    if v < 0.0 or u + v > 1.0:
        return None
    t = _dot(edge2, qvec) * inv
    if t <= 0.0 or t > max_dist:
        return None
    return (t, u, v)


class NormalBaker:
    def __init__(self, padding=2, green_flip=False, resolution=256):
        if padding < 0:
            raise ValueError("padding must be >= 0")
        if resolution <= 0:
            raise ValueError("resolution must be positive")
        self.padding = int(padding)
        self.green_flip = bool(green_flip)
        self.resolution = int(resolution)
        self._samples = 0
        self._misses = 0
        self._rays = 0

    @staticmethod
    def _check_mesh(name, mesh, need_uvs):
        if not isinstance(mesh, dict):
            raise ValueError(f"{name} mesh must be a dict")
        vertices = mesh.get("vertices") or []
        if not vertices:
            raise ValueError(f"{name} mesh is empty")
        normals = mesh.get("normals") or []
        if len(normals) != len(vertices):
            raise ValueError(f"{name} mesh normals are missing or mismatched")
        if need_uvs:
            uvs = mesh.get("uvs") or []
            if len(uvs) != len(vertices):
                raise ValueError(f"{name} mesh uvs are missing or mismatched")
        return mesh

    @staticmethod
    def _check_uvs(uvs):
        us = [uv[0] for uv in uvs]
        vs = [uv[1] for uv in uvs]
        if max(us) - min(us) < _EPS and max(vs) - min(vs) < _EPS:
            raise ValueError("degenerate UVs: all texture coordinates coincide")

    @staticmethod
    def _tangent_basis(low):
        """Per-vertex tangent/bitangent from UV derivatives, averaged
        only across triangles that share the vertex (same UV island)."""
        vertices = low["vertices"]
        uvs = low["uvs"]
        tangents = [[0.0, 0.0, 0.0] for _ in vertices]
        bitangents = [[0.0, 0.0, 0.0] for _ in vertices]
        for tri in low.get("triangles") or []:
            i0, i1, i2 = tri
            p0, p1, p2 = vertices[i0], vertices[i1], vertices[i2]
            uv0, uv1, uv2 = uvs[i0], uvs[i1], uvs[i2]
            edge1 = _sub(p1, p0)
            edge2 = _sub(p2, p0)
            duv1 = (uv1[0] - uv0[0], uv1[1] - uv0[1])
            duv2 = (uv2[0] - uv0[0], uv2[1] - uv0[1])
            det = duv1[0] * duv2[1] - duv1[1] * duv2[0]
            if abs(det) < _EPS:
                continue
            r = 1.0 / det
            tangent = (
                (edge1[0] * duv2[1] - edge2[0] * duv1[1]) * r,
                (edge1[1] * duv2[1] - edge2[1] * duv1[1]) * r,
                (edge1[2] * duv2[1] - edge2[2] * duv1[1]) * r,
            )
            bitangent = (
                (edge2[0] * duv1[0] - edge1[0] * duv2[0]) * r,
                (edge2[1] * duv1[0] - edge1[1] * duv2[0]) * r,
                (edge2[2] * duv1[0] - edge1[2] * duv2[0]) * r,
            )
            for idx in tri:
                tangents[idx][0] += tangent[0]
                tangents[idx][1] += tangent[1]
                tangents[idx][2] += tangent[2]
                bitangents[idx][0] += bitangent[0]
                bitangents[idx][1] += bitangent[1]
                bitangents[idx][2] += bitangent[2]
        return (
            [_normalize(t) for t in tangents],
            [_normalize(b) for b in bitangents],
        )

    @staticmethod
    def _uv_islands(low):
        """Union vertices connected through triangles; normals are only
        averaged between vertices of the same island."""
        parent = list(range(len(low["vertices"])))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for tri in low.get("triangles") or []:
            root = find(tri[0])
            for idx in tri[1:]:
                parent[find(idx)] = root
        return [find(i) for i in range(len(parent))]

    def _cast(self, high, origin, direction, max_dist):
        vertices = high["vertices"]
        normals = high["normals"]
        best = None
        for tri in high.get("triangles") or []:
            i0, i1, i2 = tri
            hit = _ray_triangle(
                origin, direction, vertices[i0], vertices[i1], vertices[i2], max_dist
            )
            if hit is None:
                continue
            if best is None or hit[0] < best[0]:
                best = hit + (tri,)
        if best is None:
            return None
        _, u, v, tri = best
        i0, i1, i2 = tri
        w = 1.0 - u - v
        normal = _add(
            _add(_scale(normals[i0], w), _scale(normals[i1], u)),
            _scale(normals[i2], v),
        )
        return _normalize(normal)

    def bake(self, high, low, cage, samples):
        if isinstance(samples, bool) or not isinstance(samples, int):
            raise ValueError("samples must be an integer")
        if not 1 <= samples <= 64:
            raise ValueError("samples must be between 1 and 64")
        high = self._check_mesh("high", high, need_uvs=False)
        low = self._check_mesh("low", low, need_uvs=True)
        if not isinstance(cage, dict):
            raise ValueError("cage must be a dict")
        cage_vertices = cage.get("vertices") or []
        if len(cage_vertices) != len(low["vertices"]):
            raise ValueError("cage vertex count must match the low mesh")
        thickness = cage.get("thickness", 0)
        if not thickness or thickness <= 0:
            raise ValueError("cage thickness must be positive")
        self._check_uvs(low["uvs"])

        tangents, bitangents = self._tangent_basis(low)
        islands = self._uv_islands(low)
        max_dist = 2.0 * thickness

        misses = 0
        ts_normals = []
        for i, vertex in enumerate(low["vertices"]):
            normal = _normalize(low["normals"][i])
            origin = _add(vertex, _scale(normal, thickness))
            direction = _scale(normal, -1.0)
            world = self._cast(high, origin, direction, max_dist)
            if world is None:
                misses += 1
                world = normal
            tangent = tangents[i]
            bitangent = bitangents[i]
            ts_normals.append(
                [
                    _dot(world, tangent),
                    _dot(world, bitangent),
                    _dot(world, normal),
                ]
            )

        # Average only within the same UV island, never across seams.
        sums = {}
        counts = {}
        for i, ts in enumerate(ts_normals):
            root = islands[i]
            acc = sums.setdefault(root, [0.0, 0.0, 0.0])
            acc[0] += ts[0]
            acc[1] += ts[1]
            acc[2] += ts[2]
            counts[root] = counts.get(root, 0) + 1
        for i, ts in enumerate(ts_normals):
            root = islands[i]
            count = counts[root]
            ts_normals[i] = list(
                _normalize(
                    (
                        sums[root][0] / count,
                        sums[root][1] / count,
                        sums[root][2] / count,
                    )
                )
            )

        texture = self._rasterize(low["uvs"], ts_normals)

        self._samples = samples
        self._misses = misses
        self._rays = len(low["vertices"])
        return {"texture": texture, "misses": misses}

    def _to_pixel(self, ts_normal):
        r = int(round((ts_normal[0] * 0.5 + 0.5) * 255.0))
        g = int(round((ts_normal[1] * 0.5 + 0.5) * 255.0))
        b = int(round((ts_normal[2] * 0.5 + 0.5) * 255.0))
        if self.green_flip:
            g = 255 - g
        return (r, g, b)

    def _rasterize(self, uvs, ts_normals):
        res = self.resolution
        texture = [[_NEUTRAL] * res for _ in range(res)]
        us = [uv[0] for uv in uvs]
        vs = [uv[1] for uv in uvs]
        u_span = max(max(us) - min(us), _EPS)
        v_span = max(max(vs) - min(vs), _EPS)
        for uv, ts in zip(uvs, ts_normals):
            x = min(res - 1, int((uv[0] - min(us)) / u_span * (res - 1)))
            y = min(res - 1, int((uv[1] - min(vs)) / v_span * (res - 1)))
            texture[y][x] = self._to_pixel(ts)
        # Dilate written texels outward by `padding` pixels.
        written = [
            (x, y)
            for y in range(res)
            for x in range(res)
            if texture[y][x] != _NEUTRAL
        ]
        for x, y in written:
            color = texture[y][x]
            for dy in range(-self.padding, self.padding + 1):
                for dx in range(-self.padding, self.padding + 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < res and 0 <= ny < res and texture[ny][nx] == _NEUTRAL:
                        texture[ny][nx] = color
        return texture

    def inspect(self):
        miss_rate = (self._misses / self._rays) if self._rays else 0.0
        return {
            "padding": self.padding,
            "green_flip": self.green_flip,
            "samples": self._samples,
            "resolution": self.resolution,
            "misses": self._misses,
            "miss_rate": miss_rate,
        }
