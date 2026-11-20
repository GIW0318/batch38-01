import copy
import hashlib
import json
import struct


FORMATS = {
    "float32": {"size": 4, "code": "f", "integer": False, "min": None, "max": None},
    "float16": {"size": 2, "code": "e", "integer": False, "min": None, "max": None},
    "uint8": {"size": 1, "code": "B", "integer": True, "min": 0, "max": 255},
    "uint16": {"size": 2, "code": "H", "integer": True, "min": 0, "max": 65535},
    "int16": {"size": 2, "code": "h", "integer": True, "min": -32768, "max": 32767},
}

SEMANTICS = {
    "position": (3, (0.0, 0.0, 0.0)),
    "uv": (2, (0.0, 0.0)),
    "normal": (3, (0.0, 0.0, 1.0)),
    "color": (4, (1.0, 1.0, 1.0, 1.0)),
}

MAX_STREAMS = 4
MAX_ATTRIBUTES = 16


def _align4(value):
    return (value + 3) & ~3


class VertexPlan:
    def __init__(self):
        self._streams = {}
        self._stream_order = []
        self._names = set()
        self._strides = {}
        self._defaults = {}
        self._built = False

    def add_stream(self, stream_id, attributes):
        if stream_id in self._streams:
            raise ValueError(f"duplicate stream id: {stream_id}")
        if len(self._stream_order) >= MAX_STREAMS:
            raise ValueError("more than 4 streams are not allowed")
        if not isinstance(attributes, (list, tuple)) or not attributes:
            raise ValueError("attributes must be a non-empty list")

        records = []
        new_names = []
        cursor = 0
        for attribute in attributes:
            if not isinstance(attribute, dict):
                raise ValueError("attribute must be a dict")
            name = attribute.get("name")
            fmt = attribute.get("fmt")
            if not isinstance(name, str) or not name:
                raise ValueError("attribute missing valid name")
            if fmt not in FORMATS:
                raise ValueError(f"unknown format: {fmt}")
            normalized = bool(attribute.get("normalized", False))
            if normalized and not FORMATS[fmt]["integer"]:
                raise ValueError(f"normalized requires an integer format: {name}")
            if name in self._names or name in new_names:
                raise ValueError(f"duplicate semantic name: {name}")

            components = SEMANTICS.get(name, (1, None))[0]
            size = FORMATS[fmt]["size"] * components

            if "offset" in attribute:
                offset = attribute["offset"]
                if not isinstance(offset, int) or offset < 0 or offset % 4 != 0:
                    raise ValueError(f"invalid explicit offset: {name}")
                for existing in records:
                    if (
                        offset < existing["offset"] + existing["size"]
                        and offset + size > existing["offset"]
                    ):
                        raise ValueError(f"attribute range overlaps: {name}")
            else:
                offset = _align4(cursor)

            records.append(
                {
                    "name": name,
                    "fmt": fmt,
                    "stream": stream_id,
                    "offset": offset,
                    "size": size,
                    "components": components,
                    "normalized": normalized,
                }
            )
            new_names.append(name)
            cursor = max(cursor, offset + size)

        if len(self._names) + len(new_names) > MAX_ATTRIBUTES:
            raise ValueError("more than 16 attributes are not allowed")

        self._streams[stream_id] = records
        self._stream_order.append(stream_id)
        self._names.update(new_names)
        self._built = False

    def build(self, shader_inputs, max_streams=4, stride_hint=None):
        if not self._stream_order:
            raise ValueError("cannot build without any streams")
        if len(self._stream_order) > max_streams:
            raise ValueError(f"more than {max_streams} streams are not allowed")
        if "position" not in self._names:
            raise ValueError("position attribute is required before build")

        layout_by_name = {}
        for records in self._streams.values():
            for record in records:
                layout_by_name[record["name"]] = record

        defaults = {}
        matched = set()
        for shader_input in shader_inputs:
            name = shader_input.get("name")
            input_type = shader_input.get("type")
            if name in layout_by_name:
                if layout_by_name[name]["fmt"] != input_type:
                    raise ValueError(f"shader input type mismatch: {name}")
                matched.add(name)
            elif name in SEMANTICS:
                defaults[name] = SEMANTICS[name][1]
            else:
                raise ValueError(f"unexpected shader input: {name}")

        for name, record in layout_by_name.items():
            if name in SEMANTICS:
                defaults[name] = SEMANTICS[name][1]
            elif name not in matched:
                defaults[name] = tuple(0 for _ in range(record["components"]))

        strides = {}
        for stream_id in self._stream_order:
            end = max(
                record["offset"] + record["size"]
                for record in self._streams[stream_id]
            )
            if stride_hint is not None:
                if stride_hint % 4 != 0 or stride_hint < end:
                    raise ValueError(f"invalid stride for stream {stream_id}")
                strides[stream_id] = stride_hint
            else:
                strides[stream_id] = _align4(end)

        self._strides = strides
        self._defaults = defaults
        self._built = True

    def _encode_component(self, record, value):
        info = FORMATS[record["fmt"]]
        if info["integer"]:
            if record["normalized"] and isinstance(value, float):
                scale = info["max"] if info["min"] == 0 else -info["min"]
                value = round(value * scale)
            elif isinstance(value, float):
                if not value.is_integer():
                    raise ValueError(f"non-integral value for integer attribute: {record['name']}")
                value = int(value)
            if not isinstance(value, int) or value < info["min"] or value > info["max"]:
                raise ValueError(f"value out of range for attribute: {record['name']}")
        elif not isinstance(value, (int, float)):
            raise ValueError(f"invalid value for attribute: {record['name']}")
        return struct.pack("<" + info["code"], value)

    def pack(self, vertices):
        if not self._built:
            raise ValueError("plan must be built before pack")

        layout_names = set()
        for records in self._streams.values():
            for record in records:
                layout_names.add(record["name"])

        output = bytearray()
        for vertex in vertices:
            if not isinstance(vertex, dict):
                raise ValueError("each vertex must be a dict")
            unknown = set(vertex) - layout_names
            if unknown:
                raise ValueError(f"unknown vertex fields: {sorted(unknown)}")

            for stream_id in self._stream_order:
                block = bytearray(self._strides[stream_id])
                for record in self._streams[stream_id]:
                    name = record["name"]
                    if name in vertex:
                        value = vertex[name]
                        if not isinstance(value, (list, tuple)):
                            value = (value,)
                        if len(value) > record["components"]:
                            raise ValueError(f"too many components for attribute: {name}")
                    else:
                        value = self._defaults.get(
                            name, tuple(0 for _ in range(record["components"]))
                        )

                    offset = record["offset"]
                    for index, component in enumerate(value):
                        encoded = self._encode_component(record, component)
                        start = offset + index * FORMATS[record["fmt"]]["size"]
                        block[start:start + len(encoded)] = encoded

                output.extend(block)
        return bytes(output)

    def _descriptor(self, strides):
        descriptor = []
        for stream_id in sorted(self._stream_order):
            descriptor.append(
                {
                    "stream": stream_id,
                    "stride": strides[stream_id],
                    "attributes": [
                        {
                            "name": record["name"],
                            "fmt": record["fmt"],
                            "offset": record["offset"],
                            "size": record["size"],
                            "components": record["components"],
                            "normalized": record["normalized"],
                        }
                        for record in self._streams[stream_id]
                    ],
                }
            )
        return descriptor

    def layout(self):
        if self._built:
            strides = dict(self._strides)
        else:
            strides = {
                stream_id: _align4(
                    max(
                        record["offset"] + record["size"]
                        for record in self._streams[stream_id]
                    )
                )
                for stream_id in self._stream_order
            }

        attributes = []
        for stream_id in self._stream_order:
            for record in self._streams[stream_id]:
                attributes.append(copy.deepcopy(record))

        canonical = json.dumps(
            self._descriptor(strides), sort_keys=True, separators=(",", ":")
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        return copy.deepcopy(
            {
                "streams": len(self._stream_order),
                "attributes": attributes,
                "attribute_count": len(attributes),
                "bytes": sum(strides.values()),
                "strides": strides,
                "defaults": self._defaults,
                "hash": digest,
            }
        )
