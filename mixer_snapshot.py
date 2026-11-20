import copy
import math
import operator


class MixerRecall:
    def __init__(self):
        self._snapshots = {}
        self._versions = []
        self._current_name = None
        self._current_version = None
        self._current_index = None
        self._current_params = {}
        self._scheduled_name = None
        self._transition = None
        self._pending = []
        self._clock = None
        self._cursor = None

    def capture(self, name, buses, params, now):
        snapshot_params, bus_ids = self._normalize_snapshot(buses, params)
        version = len(self._snapshots.get(name, ())) + 1
        snapshot = {
            "name": name,
            "version": version,
            "order": len(self._versions),
            "now": now,
            "params": snapshot_params,
            "bus_versions": {bus_id: version for bus_id in bus_ids},
        }

        self._snapshots.setdefault(name, []).append(snapshot)
        self._versions.append(snapshot)
        self._cursor = snapshot["order"]
        if self._current_name is None:
            self._current_name = name
            self._current_version = version
            self._current_index = snapshot["order"]
            self._current_params = copy.deepcopy(snapshot_params)
        self._remember_time(now)
        return None

    def blend(self, a, b, t, curve):
        first = self._latest(a)
        second = self._latest(b)
        position = self._clamp_t(t)
        curve = self._curve(curve)

        result = {}
        bus_ids = list(first["params"])
        bus_ids.extend(bus_id for bus_id in second["params"] if bus_id not in first["params"])

        for bus_id in bus_ids:
            left = first["params"].get(bus_id)
            right = second["params"].get(bus_id)
            if left is None:
                result[bus_id] = copy.deepcopy(right)
                result[bus_id]["send"] = self._soft_send(result[bus_id]["send"])
                continue
            if right is None:
                result[bus_id] = copy.deepcopy(left)
                result[bus_id]["send"] = self._soft_send(result[bus_id]["send"])
                continue

            gain = self._mix(left["gain"], right["gain"], position, curve)
            send = self._mix(left["send"], right["send"], position, curve)
            lowpass = self._mix_linear(left["lowpass"], right["lowpass"], position)
            result[bus_id] = {
                "gain": min(1.0, max(0.0, gain)),
                "send": self._soft_send(send),
                "lowpass": min(20000.0, max(200.0, lowpass)),
                "parent": right["parent"],
                "locked": bool(left["locked"] or right["locked"]),
            }

        return result

    def apply(self, name, bus, now):
        self._advance(now)
        snapshot = self._latest(name)
        if bus not in snapshot["params"]:
            raise ValueError(f"unknown bus: {bus}")

        if self._transition is not None:
            self._pending.append((name, bus, now))
            return None

        self._apply_bus(snapshot, bus)
        return None

    def schedule(self, name, at, curve):
        snapshot = self._latest(name)
        if not self._is_number(at):
            raise ValueError("schedule time must be a finite number")
        curve = self._curve(curve)
        self._transition = {
            "snapshot": snapshot,
            "at": at,
            "curve": curve,
        }
        self._scheduled_name = name
        return None

    def rollback(self, steps):
        try:
            steps = operator.index(steps)
        except TypeError as exc:
            raise ValueError("rollback steps must be an integer") from exc
        if steps < 0:
            raise ValueError("rollback steps must not be negative")
        if not self._versions:
            return None

        index = self._cursor if self._cursor is not None else len(self._versions) - 1
        target = max(0, index - steps)
        snapshot = self._versions[target]

        self._current_name = snapshot["name"]
        self._current_version = snapshot["version"]
        self._current_index = target
        self._cursor = target
        self._current_params = copy.deepcopy(snapshot["params"])
        self._scheduled_name = None
        self._transition = None
        self._pending.clear()
        return None

    def detail(self):
        history = []
        for snapshot in self._versions:
            history.append(
                {
                    "name": snapshot["name"],
                    "version": snapshot["version"],
                    "order": snapshot["order"],
                    "now": snapshot["now"],
                    "params": copy.deepcopy(snapshot["params"]),
                    "bus_versions": copy.deepcopy(snapshot["bus_versions"]),
                }
            )

        locked = {
            bus_id: True
            for bus_id, bus_params in self._current_params.items()
            if bus_params.get("locked")
        }
        return {
            "versions": len(self._versions),
            "version": self._current_version,
            "version_stack": history,
            "history": copy.deepcopy(history),
            "current": self._current_name,
            "current_params": copy.deepcopy(self._current_params),
            "locked": locked,
            "scheduled": self._scheduled_name,
            "pending": len(self._pending),
        }

    def _normalize_snapshot(self, buses, params):
        if not isinstance(params, dict):
            raise ValueError("params must be a mapping")
        if not isinstance(buses, (list, tuple)) or not buses:
            raise ValueError("buses must be a non-empty sequence")

        normalized = {}
        bus_ids = []
        for entry in buses:
            bus_id, source = self._bus_source(entry, params)
            if bus_id in normalized:
                raise ValueError(f"duplicate bus: {bus_id}")
            if source is None:
                raise ValueError(f"unknown bus: {bus_id}")
            if not isinstance(source, dict):
                raise ValueError(f"bus params must be a mapping: {bus_id}")

            gain = source.get("gain", 1.0)
            send = source.get("send", 0.0)
            lowpass = source.get("lowpass", 20000)
            parent = source.get("parent")
            locked = source.get("locked", False)

            if not self._is_number(gain) or not 0.0 <= gain <= 1.0:
                raise ValueError(f"gain out of range for bus {bus_id}")
            if not self._is_number(send) or send < 0.0:
                raise ValueError(f"send out of range for bus {bus_id}")
            if not self._is_number(lowpass) or not 200.0 <= lowpass <= 20000.0:
                raise ValueError(f"lowpass out of range for bus {bus_id}")

            normalized[bus_id] = {
                "gain": float(gain),
                "send": self._soft_send(send),
                "lowpass": float(lowpass),
                "parent": parent,
                "locked": bool(locked),
            }
            bus_ids.append(bus_id)

        for bus_id in bus_ids:
            parent = normalized[bus_id]["parent"]
            if parent is not None and parent not in normalized:
                raise ValueError(f"unknown parent bus: {parent}")

        for bus_id in bus_ids:
            seen = set()
            current = bus_id
            while current is not None:
                if current in seen:
                    raise ValueError("parent chain contains a cycle")
                seen.add(current)
                current = normalized[current]["parent"]

        return normalized, bus_ids

    def _bus_source(self, entry, params):
        if isinstance(entry, str):
            return entry, params.get(entry)
        if isinstance(entry, dict):
            bus_id = entry.get("id")
            if bus_id is None:
                raise ValueError("bus entry is missing id")
            return bus_id, params.get(bus_id, entry)

        bus_id = getattr(entry, "id", None)
        if bus_id is None:
            raise ValueError("bus entry is missing id")
        source = params.get(bus_id)
        if source is None:
            source = {
                "gain": getattr(entry, "gain", 1.0),
                "send": getattr(entry, "send", 0.0),
                "lowpass": getattr(entry, "lowpass", 20000),
                "parent": getattr(entry, "parent", None),
                "locked": getattr(entry, "locked", False),
            }
        return bus_id, source

    def _latest(self, name):
        versions = self._snapshots.get(name)
        if not versions:
            raise ValueError(f"unknown snapshot: {name}")
        return versions[-1]

    def _advance(self, now):
        self._remember_time(now)

        transition = self._transition
        if transition is None or now < transition["at"]:
            return

        snapshot = transition["snapshot"]
        for bus_id in snapshot["params"]:
            self._apply_bus(snapshot, bus_id)

        self._current_name = snapshot["name"]
        self._current_version = snapshot["version"]
        self._current_index = snapshot["order"]
        self._cursor = snapshot["order"]
        self._scheduled_name = None
        self._transition = None

        pending = self._pending
        self._pending = []
        for name, bus_id, pending_now in pending:
            queued = self._latest(name)
            if bus_id not in queued["params"]:
                raise ValueError(f"unknown bus: {bus_id}")
            self._apply_bus(queued, bus_id)

    def _apply_bus(self, snapshot, bus_id):
        target = snapshot["params"][bus_id]
        current = self._current_params.get(bus_id)
        if target["locked"] or (current is not None and current.get("locked")):
            return False

        updated = copy.deepcopy(target)
        updated["gain"] = min(
            1.0,
            max(0.0, target["gain"] * self._ancestor_gain(snapshot, bus_id)),
        )
        updated["send"] = self._soft_send(target["send"])
        self._current_params[bus_id] = updated
        self._current_name = snapshot["name"]
        self._current_version = snapshot["version"]
        self._current_index = snapshot["order"]
        self._cursor = snapshot["order"]
        return True

    def _ancestor_gain(self, snapshot, bus_id):
        gain = 1.0
        parent = snapshot["params"][bus_id]["parent"]
        seen = {bus_id}
        while parent is not None:
            if parent in seen or parent not in snapshot["params"]:
                raise ValueError("parent chain contains a cycle")
            seen.add(parent)
            gain *= snapshot["params"][parent]["gain"]
            parent = snapshot["params"][parent]["parent"]
        return gain

    def _curve(self, curve):
        if not isinstance(curve, str):
            raise ValueError("curve must be linear or equal_power")
        normalized = curve.strip().lower().replace("-", "_")
        if normalized == "equalpower":
            normalized = "equal_power"
        if normalized not in {"linear", "equal_power"}:
            raise ValueError(f"unsupported curve: {curve}")
        return normalized

    def _clamp_t(self, t):
        if not self._is_number(t):
            raise ValueError("blend position must be a finite number")
        return min(1.0, max(0.0, float(t)))

    def _mix(self, left, right, t, curve):
        if t <= 0.0:
            return float(left)
        if t >= 1.0:
            return float(right)
        if curve == "linear":
            return float(left) + (float(right) - float(left)) * t
        return math.sqrt((1.0 - t) * float(left) ** 2 + t * float(right) ** 2)

    def _mix_linear(self, left, right, t):
        return float(left) + (float(right) - float(left)) * t

    def _soft_send(self, send):
        return min(1.0, max(0.0, float(send)))

    def _remember_time(self, now):
        if not self._is_number(now):
            raise ValueError("time must be a finite number")
        self._clock = float(now)

    def _is_number(self, value):
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
