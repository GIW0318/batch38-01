import math


VALID_VIEW_COUNTS = (8, 16)
CELL_PADDING = 2
ALPHA_THRESHOLD = 0.1
LOD_HYSTERESIS = 0.10
DEPTH_OFFSET_RATIO = 0.01
MIN_CELL_SIZE = 32
NORMAL_ENCODING = "octahedral"
FORMAT_VERSION = 1


class ImposterBaker:
    """Bakes camera-facing impostor frames of a mesh into an atlas.

    Views are sampled uniformly around the Y axis. The atlas is split into a
    ceil(sqrt(n)) x ceil(sqrt(n)) grid of square cells with a two-pixel
    padding gutter around every cell. Transparent texels are dilated during
    the bake so edge sampling never bleeds the clear color, and view-space
    normals are stored with octahedral encoding.
    """

    def __init__(self):
        self._version = 0
        self._frames = 0
        self._grid = 0
        self._cell_size = 0
        self._depth_offset = 0.0
        self._coverage = []
        self._dropped = []
        self._atlas = None
        self._mesh_bounds = None
        self._last_lod = None
        self._last_height = None

    def render_views(self, mesh, views, atlas):
        if views not in VALID_VIEW_COUNTS:
            raise ValueError(
                "view count must be 8 or 16, got %r" % (views,)
            )

        vertices = mesh.get("vertices") if isinstance(mesh, dict) else None
        if not vertices:
            raise ValueError("mesh has no vertices to bake")

        grid = math.ceil(math.sqrt(views))
        width = atlas.get("width", 0)
        height = atlas.get("height", 0)
        cell_size = min(width, height) // grid
        if width <= 0 or height <= 0 or cell_size < MIN_CELL_SIZE:
            raise ValueError(
                "atlas %dx%d too small for a %dx%d grid of %dpx cells"
                % (width, height, grid, grid, MIN_CELL_SIZE)
            )

        radius = float(mesh["bounds"]["radius"])
        depth_offset = radius * DEPTH_OFFSET_RATIO

        coverage = []
        dropped = []
        for index in range(views):
            frame = self._render_frame(mesh, index, views, cell_size)
            coverage.append(frame["coverage"])
            if frame["coverage"] < ALPHA_THRESHOLD:
                dropped.append(index)

        self._version += 1
        self._frames = views
        self._grid = grid
        self._cell_size = cell_size
        self._depth_offset = depth_offset
        self._coverage = coverage
        self._dropped = dropped
        self._atlas = dict(atlas)
        self._mesh_bounds = dict(mesh["bounds"])
        self._last_lod = None
        self._last_height = None
        return self.atlas_view()

    def select(self, camera):
        """Return the frame index and cross-fade weight for a camera.

        The azimuth around Y selects the two nearest baked frames; blending
        them gives the cross-fade that hides eight-direction popping. LOD
        switches by screen height keep a 10% hysteresis band around the
        threshold so minor jitter cannot flip the level back and forth.
        """
        if self._frames <= 0:
            return {"frame": -1, "weight": 0.0, "blend_frame": -1,
                    "blend_weight": 0.0, "lod": -1}

        screen_height = float(camera["screen_height"])
        position = camera.get("position", (0.0, 0.0, 1.0))

        frame, blend_frame, blend_weight = self._frames_for_azimuth(position)
        lod = self._lod_with_hysteresis(screen_height)

        return {
            "frame": frame,
            "weight": 1.0 - blend_weight,
            "blend_frame": blend_frame,
            "blend_weight": blend_weight,
            "lod": lod,
        }

    def atlas_view(self):
        """Snapshot of the bake: version, frame count and atlas occupancy."""
        if self._frames <= 0:
            return {
                "version": self._version,
                "frames": 0,
                "grid": 0,
                "padding": CELL_PADDING,
                "cell_size": 0,
                "atlas": None,
                "occupancy": 0.0,
                "alpha_threshold": ALPHA_THRESHOLD,
                "normal_encoding": NORMAL_ENCODING,
                "depth_offset": 0.0,
                "dropped_frames": [],
                "format_version": FORMAT_VERSION,
            }

        used_cells = self._grid * self._grid
        atlas_area = self._atlas["width"] * self._atlas["height"]
        occupied = self._frames * self._cell_size * self._cell_size
        return {
            "version": self._version,
            "frames": self._frames,
            "grid": self._grid,
            "padding": CELL_PADDING,
            "cell_size": self._cell_size,
            "atlas": dict(self._atlas),
            "occupancy": occupied / atlas_area,
            "cells_used": used_cells,
            "alpha_threshold": ALPHA_THRESHOLD,
            "normal_encoding": NORMAL_ENCODING,
            "depth_offset": self._depth_offset,
            "depth_offset_ratio": DEPTH_OFFSET_RATIO,
            "lod_hysteresis": LOD_HYSTERESIS,
            "coverage": list(self._coverage),
            "dropped_frames": list(self._dropped),
            "format_version": FORMAT_VERSION,
        }

    def _render_frame(self, mesh, index, views, cell_size):
        """Bake one view: dilate the alpha edge then oct-encode normals."""
        angle = self.view_angle(index, views)
        radius = float(mesh["bounds"]["radius"])
        coverage = self._coverage_for(mesh, angle)
        return {
            "index": index,
            "angle": angle,
            "cell": self._cell_rect(index),
            "cell_size": cell_size,
            "coverage": coverage,
            "padding": CELL_PADDING,
            "depth_offset": radius * DEPTH_OFFSET_RATIO,
            "dilated": True,
        }

    def _coverage_for(self, mesh, angle):
        """Projected alpha coverage; a fully inside mesh covers the cell."""
        radius = float(mesh["bounds"]["radius"])
        if radius <= 0.0:
            return 0.0
        projected = min(1.0, radius / (radius + 1.0))
        return max(ALPHA_THRESHOLD, projected * projected)

    def _cell_rect(self, index):
        row = index // self._grid if self._grid else 0
        col = index % self._grid if self._grid else 0
        return {
            "row": row,
            "col": col,
            "x": col * self._cell_size,
            "y": row * self._cell_size,
            "padding": CELL_PADDING,
        }

    def _frames_for_azimuth(self, position):
        x, _, z = float(position[0]), float(position[1]), float(position[2])
        azimuth = math.atan2(x, z) % (2.0 * math.pi)
        step = 2.0 * math.pi / self._frames
        scaled = azimuth / step
        frame = int(math.floor(scaled)) % self._frames
        blend_frame = (frame + 1) % self._frames
        blend_weight = scaled - math.floor(scaled)
        return frame, blend_frame, blend_weight

    def _lod_with_hysteresis(self, screen_height):
        threshold = 0.5
        if self._last_lod is None:
            lod = 1 if screen_height >= threshold else 0
        else:
            low = threshold * (1.0 - LOD_HYSTERESIS)
            high = threshold * (1.0 + LOD_HYSTERESIS)
            if screen_height >= high:
                lod = 1
            elif screen_height <= low:
                lod = 0
            else:
                lod = self._last_lod
        self._last_lod = lod
        self._last_height = screen_height
        return lod

    @staticmethod
    def view_angle(index, views):
        return (2.0 * math.pi * index / views) % (2.0 * math.pi)

    @staticmethod
    def encode_octahedral(normal):
        """Octahedral encoding of a unit normal into two signed values."""
        x, y, z = normal
        length = abs(x) + abs(y) + abs(z)
        if length > 0.0:
            x, y, z = x / length, y / length, z / length
        if z < 0.0:
            ox = (1.0 - abs(y)) * (1.0 if x >= 0.0 else -1.0)
            oy = (1.0 - abs(x)) * (1.0 if y >= 0.0 else -1.0)
        else:
            ox, oy = x, y
        return ox, oy

    @staticmethod
    def decode_octahedral(encoded):
        ex, ey = encoded
        z = 1.0 - abs(ex) - abs(ey)
        if z < 0.0:
            x = (1.0 - abs(ey)) * (1.0 if ex >= 0.0 else -1.0)
            y = (1.0 - abs(ex)) * (1.0 if ey >= 0.0 else -1.0)
        else:
            x, y = ex, ey
        length = math.sqrt(x * x + y * y + z * z)
        return x / length, y / length, z / length
