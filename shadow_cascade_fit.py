import copy
import math


class CascadeFit:
    RATIOS = (0.1, 0.3, 0.6)
    MAX_SHADOW_DISTANCE = 100.0
    OVERLAP = 0.1
    RESOLUTION = 2048.0

    def __init__(self):
        self._cascades = []

    @staticmethod
    def _validate_camera(camera):
        near = float(camera["near"])
        far = float(camera["far"])
        if near < 0.0 or far < 0.0:
            raise ValueError("camera distances must be non-negative")
        if near > far:
            raise ValueError("near plane must not exceed far plane")
        return near, far

    def splits(self, camera):
        _, far = self._validate_camera(camera)
        shadow_far = min(far, self.MAX_SHADOW_DISTANCE)
        values = [ratio * shadow_far for ratio in self.RATIOS]
        if far > shadow_far:
            values[-1] = far
        return values

    @staticmethod
    def _quantize_direction(direction):
        x, y, z = (float(v) for v in direction)
        length = math.sqrt(x * x + y * y + z * z)
        if length == 0.0:
            raise ValueError("light direction must be non-zero")
        x, y, z = x / length, y / length, z / length
        azimuth = math.radians(round(math.degrees(math.atan2(x, z))))
        elevation = math.radians(round(math.degrees(math.asin(max(-1.0, min(1.0, y))))))
        cos_elevation = math.cos(elevation)
        return (
            math.sin(azimuth) * cos_elevation,
            math.sin(elevation),
            math.cos(azimuth) * cos_elevation,
        )

    @staticmethod
    def _light_basis(forward):
        up = (0.0, 1.0, 0.0)
        if abs(forward[1]) > 0.999:
            up = (0.0, 0.0, 1.0)
        right = (
            up[1] * forward[2] - up[2] * forward[1],
            up[2] * forward[0] - up[0] * forward[2],
            up[0] * forward[1] - up[1] * forward[0],
        )
        length = math.sqrt(sum(component * component for component in right))
        right = tuple(component / length for component in right)
        up = (
            forward[1] * right[2] - forward[2] * right[1],
            forward[2] * right[0] - forward[0] * right[2],
            forward[0] * right[1] - forward[1] * right[0],
        )
        return right, up, forward

    def fit(self, light, camera):
        near, far = self._validate_camera(camera)
        forward = self._quantize_direction(light["direction"])
        right, up, forward = self._light_basis(forward)
        tan_half = math.tan(math.radians(float(camera["fov"])) * 0.5)
        aspect = float(camera["aspect"])

        splits = self.splits(camera)
        bounds = [near] + list(splits)
        cascades = []
        for index in range(len(splits)):
            slice_near = bounds[index]
            slice_far = bounds[index + 1]
            if index + 1 < len(splits):
                slice_far += self.OVERLAP * (slice_far - slice_near)
            else:
                slice_far = max(slice_far, far)

            corners = []
            for depth in (slice_near, slice_far):
                half_height = depth * tan_half
                half_width = half_height * aspect
                for sign_x in (-1.0, 1.0):
                    for sign_y in (-1.0, 1.0):
                        corners.append((sign_x * half_width, sign_y * half_height, depth))

            light_x = [sum(p[axis] * right[axis] for axis in range(3)) for p in corners]
            light_y = [sum(p[axis] * up[axis] for axis in range(3)) for p in corners]
            light_z = [sum(p[axis] * forward[axis] for axis in range(3)) for p in corners]

            size = max(max(light_x) - min(light_x), max(light_y) - min(light_y))
            texel = size / self.RESOLUTION
            center = []
            for values in (light_x, light_y, light_z):
                middle = (min(values) + max(values)) * 0.5
                center.append(round(middle / texel) * texel)

            cascades.append({
                "near": slice_near,
                "far": slice_far,
                "center": tuple(center),
                "size": size,
                "texel": texel,
            })
        self._cascades = cascades
        return self

    def cascades(self):
        return copy.deepcopy(self._cascades)
