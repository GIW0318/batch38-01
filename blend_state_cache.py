from collections import OrderedDict
from collections.abc import Mapping
from copy import deepcopy


_UNSET = object()
_DEFAULT_KEY = object()


class BlendCache:
    FIELDS = (
        "blend_src",
        "blend_dst",
        "blend_op",
        "depth_test",
        "depth_write",
        "depth_func",
        "cull",
        "color_mask",
    )

    BLEND_FACTORS = frozenset(
        {
            "zero",
            "one",
            "src_color",
            "one_minus_src_color",
            "dst_color",
            "one_minus_dst_color",
            "src_alpha",
            "one_minus_src_alpha",
            "dst_alpha",
            "one_minus_dst_alpha",
            "constant_color",
            "one_minus_constant_color",
            "constant_alpha",
            "one_minus_constant_alpha",
            "src_alpha_saturate",
            "src1_color",
            "one_minus_src1_color",
            "src1_alpha",
            "one_minus_src1_alpha",
        }
    )
    BLEND_OPS = frozenset({"add", "subtract", "reverse_subtract", "min", "max"})
    DEPTH_FUNCS = frozenset(
        {
            "never",
            "less",
            "equal",
            "less_equal",
            "greater",
            "not_equal",
            "greater_equal",
            "always",
        }
    )
    CULL_MODES = frozenset({"none", "front", "back", "front_and_back"})

    _DEFAULT_DESC = {
        "blend_src": "one",
        "blend_dst": "zero",
        "blend_op": "add",
        "depth_test": False,
        "depth_write": True,
        "depth_func": "less",
        "cull": "none",
        "color_mask": "rgba",
    }

    def __init__(self, capacity=256, default_desc=None):
        if (
            not isinstance(capacity, int)
            or isinstance(capacity, bool)
            or capacity < 0
        ):
            raise ValueError("capacity must be a non-negative integer")

        self.capacity = capacity
        self.default_handle = 0

        default_source = self._DEFAULT_DESC if default_desc is None else default_desc
        self._default_values = self._normalize_fields(default_source)

        self._entries = {}
        self._lru = OrderedDict()
        self._next_handle = 1
        self._current_key = _UNSET
        self._known_passes = set()
        self.current_pass = None

        self._hits = 0
        self._misses = 0
        self._redundant = 0
        self._evicted = 0

    @classmethod
    def _normalize_fields(cls, desc):
        if not isinstance(desc, Mapping):
            raise ValueError("desc must be a mapping")

        missing = [field for field in cls.FIELDS if field not in desc]
        if missing:
            raise ValueError("missing desc field(s): " + ", ".join(missing))

        depth_test = desc["depth_test"]
        depth_write = desc["depth_write"]
        if not isinstance(depth_test, bool) or not isinstance(depth_write, bool):
            raise ValueError("depth_test and depth_write must be booleans")

        return {
            "blend_src": cls._enum(
                "blend_src", desc["blend_src"], cls.BLEND_FACTORS
            ),
            "blend_dst": cls._enum(
                "blend_dst", desc["blend_dst"], cls.BLEND_FACTORS
            ),
            "blend_op": cls._enum("blend_op", desc["blend_op"], cls.BLEND_OPS),
            "depth_test": depth_test,
            "depth_write": depth_write,
            "depth_func": cls._enum(
                "depth_func", desc["depth_func"], cls.DEPTH_FUNCS
            ),
            "cull": cls._enum("cull", desc["cull"], cls.CULL_MODES),
            "color_mask": cls._color_mask(desc["color_mask"]),
        }

    @staticmethod
    def _enum(name, value, allowed):
        if not isinstance(value, str):
            raise ValueError(f"unknown {name}: {value!r}")
        normalized = value.strip().lower()
        if normalized not in allowed:
            raise ValueError(f"unknown {name}: {value!r}")
        return normalized

    @staticmethod
    def _color_mask(value):
        if isinstance(value, (list, tuple, set, frozenset)):
            value = "".join(value)
        if not isinstance(value, str):
            raise ValueError(f"unknown color_mask: {value!r}")

        chars = value.strip().lower()
        if not chars or any(char not in "rgba" for char in chars):
            raise ValueError(f"unknown color_mask: {value!r}")
        if len(set(chars)) != len(chars):
            raise ValueError(f"unknown color_mask: {value!r}")

        return "".join(channel for channel in "rgba" if channel in chars)

    def _prepare(self, desc):
        if desc is None:
            return dict(self._default_values), _DEFAULT_KEY

        values = self._normalize_fields(desc)
        pass_id = desc.get("pass_id", desc.get("_pass_id", self.current_pass))
        try:
            hash(pass_id)
        except TypeError as exc:
            raise ValueError("pass_id must be hashable") from exc

        key = (pass_id, tuple(values[field] for field in self.FIELDS))
        return values, key

    def _is_default(self, values):
        return values == self._default_values

    def _touch(self, key):
        if key in self._lru:
            self._lru.move_to_end(key)

    def _resolve(self, values, key):
        if self._is_default(values):
            self._hits += 1
            return self.default_handle

        entry = self._entries.get(key)
        if entry is not None:
            self._hits += 1
            self._touch(key)
            return entry

        self._misses += 1
        entry = self._next_handle
        self._next_handle += 1

        pass_id = key[0]
        self._known_passes.add(pass_id)
        self._entries[key] = entry
        self._lru[key] = None

        while len(self._entries) > self.capacity:
            old_key, _ = self._lru.popitem(last=False)
            del self._entries[old_key]
            self._evicted += 1

        return entry

    def get(self, desc):
        values, key = self._prepare(desc)
        return self._resolve(values, key)

    def bind(self, desc, ts):
        values, key = self._prepare(desc)
        target = _DEFAULT_KEY if self._is_default(values) else key

        if target == self._current_key:
            self._redundant += 1
            if target is not _DEFAULT_KEY:
                self._touch(target)
            return False

        self._resolve(values, key)
        self._current_key = target
        return True

    def invalidate(self, pass_id):
        try:
            hash(pass_id)
        except TypeError as exc:
            raise ValueError("pass_id must be hashable") from exc

        self._known_passes.add(pass_id)
        targets = [key for key in self._entries if key[0] == pass_id]

        # Entries created without an explicit pass are the active/global pass.
        if not targets and pass_id is not None:
            targets = [key for key in self._entries if key[0] is None]

        for key in targets:
            del self._entries[key]
            self._lru.pop(key, None)
            if key == self._current_key:
                self._current_key = None

        return len(targets)

    def set_pass(self, pass_id):
        try:
            hash(pass_id)
        except TypeError as exc:
            raise ValueError("pass_id must be hashable") from exc

        if pass_id == self.current_pass:
            return 0

        previous = self.current_pass
        self.current_pass = pass_id
        return self.invalidate(previous)

    def stats(self):
        pass_counts = {pass_id: 0 for pass_id in self._known_passes}
        for key in self._entries:
            pass_counts[key[0]] = pass_counts.get(key[0], 0) + 1

        return {
            "hits": self._hits,
            "misses": self._misses,
            "redundant": self._redundant,
            "evicted": self._evicted,
            "entries": len(self._entries),
            "passes": deepcopy(pass_counts),
            "capacity": self.capacity,
        }

    @property
    def default_desc(self):
        return dict(self._default_values)

    @property
    def default_state(self):
        return dict(self._default_values)
