import math
from copy import deepcopy


class ThreatTable:
    KIND_COEFFICIENTS = {"damage": 1.0, "heal": 0.5}
    DECAY_GRACE = 10.0
    DECAY_FACTOR = 0.95
    TAUNT_WINDOW = 10.0
    REWIND_WINDOW = 10.0
    MAX_LINK_PCT = 0.3
    PHASES = ("ground", "air")

    def __init__(self, bosses=None):
        self.bosses = list(dict.fromkeys(bosses or []))
        self._boss_set = set(self.bosses)
        self._entries = {boss: {} for boss in self.bosses}
        self._phase = {boss: "ground" for boss in self.bosses}
        self._last_taunt = {}
        self._links = []
        self._snapshots = {}
        self._snapshot_order = []
        self._next_snapshot_id = 1
        self._seq = 0
        self.now = 0.0

    @staticmethod
    def _number(value, label, *, minimum=None):
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"invalid {label}") from exc
        if not math.isfinite(result):
            raise ValueError(f"invalid {label}")
        if minimum is not None and result < minimum:
            raise ValueError(f"invalid {label}")
        return result

    def _check_boss(self, boss):
        if boss not in self._boss_set:
            raise ValueError(f"unknown boss: {boss}")

    def _advance_to(self, now):
        now = self._number(now, "time")
        if now < self.now:
            raise ValueError("time moved backwards")

        elapsed = now - self.now
        if elapsed > 0:
            for boss in self.bosses:
                if self._phase[boss] != "ground":
                    continue
                for entry in self._entries[boss].values():
                    old_idle = entry["idle"]
                    new_idle = old_idle + elapsed
                    decay_seconds = max(0.0, new_idle - self.DECAY_GRACE) - max(
                        0.0, old_idle - self.DECAY_GRACE
                    )
                    if decay_seconds:
                        entry["threat"] *= self.DECAY_FACTOR**decay_seconds
                    entry["idle"] = new_idle
            self.now = now
        return now

    def _bump_seq(self):
        self._seq += 1
        return self._seq

    def _new_entry(self, now):
        return {
            "threat": 0.0,
            "idle": 0.0,
            "reached": now,
            "seq": self._bump_seq(),
        }

    def _credit(self, boss, actor, amount, now):
        if amount <= 0:
            return
        entries = self._entries[boss]
        entry = entries.get(actor)
        if entry is None:
            entry = self._new_entry(now)
            entries[actor] = entry
        entry["threat"] += amount
        entry["idle"] = 0.0
        entry["reached"] = now
        entry["seq"] = self._bump_seq()

    def _apply_gain(self, boss, actor, amount, now):
        for link in self._links:
            if link["src"] == actor and now <= link["until"]:
                moved = amount * link["pct"]
                self._credit(boss, link["dst"], moved, now)
                self._credit(boss, actor, amount - moved, now)
                return
        self._credit(boss, actor, amount, now)

    def add(self, actor, boss, value, kind, now):
        self._check_boss(boss)
        value = self._number(value, "threat value", minimum=0.0)
        if kind not in self.KIND_COEFFICIENTS:
            raise ValueError(f"unknown kind: {kind}")
        now = self._advance_to(now)

        coefficient = self.KIND_COEFFICIENTS[kind]
        if kind == "heal":
            if not self.bosses:
                return None
            share = value * coefficient / len(self.bosses)
            for target in self.bosses:
                if self._phase[target] == "ground":
                    self._apply_gain(target, actor, share, now)
            return None

        if self._phase[boss] == "ground":
            self._apply_gain(boss, actor, value * coefficient, now)
        return None

    def taunt(self, actor, boss, now):
        self._check_boss(boss)
        now = self._advance_to(now)
        if self._phase[boss] != "ground":
            return None

        entries = self._entries[boss]
        highest = max((entry["threat"] for entry in entries.values()), default=0.0)
        last = self._last_taunt.get(boss)
        multiplier = 1.05 if last is not None and now - last < self.TAUNT_WINDOW else 1.1
        self._last_taunt[boss] = now

        entry = entries.get(actor)
        if entry is None:
            entry = self._new_entry(now)
            entries[actor] = entry
        target = highest * multiplier
        if target > entry["threat"]:
            entry["threat"] = target
            entry["idle"] = 0.0
            entry["reached"] = now
            entry["seq"] = self._bump_seq()
        return None

    def drop(self, actor, boss, pct):
        self._check_boss(boss)
        pct = self._number(pct, "drop percentage", minimum=0.0)

        for target in self.bosses:
            if self._phase[target] != "ground":
                continue
            entry = self._entries[target].get(actor)
            if entry is None:
                continue
            new_threat = max(0.0, entry["threat"] * (1.0 - pct))
            if new_threat != entry["threat"]:
                entry["threat"] = new_threat
                entry["reached"] = self.now
                entry["seq"] = self._bump_seq()
        return None

    def link(self, src, dst, pct, until):
        pct = self._number(pct, "link percentage")
        until = self._number(until, "link expiry")
        if pct <= 0.0 or pct > self.MAX_LINK_PCT:
            raise ValueError("link percentage must be in (0, 0.3]")
        if src == dst:
            raise ValueError("cannot link an actor to itself")

        for existing in self._links:
            if existing["src"] == src:
                raise ValueError("source already has a link")
            if existing["dst"] == src or existing["src"] == dst:
                raise ValueError("link chains and cycles are not allowed")
            if existing["dst"] == dst:
                raise ValueError("destination already has a link")

        self._links.append({"src": src, "dst": dst, "pct": pct, "until": until})
        return None

    def phase(self, boss, phase, now):
        self._check_boss(boss)
        if phase not in self.PHASES:
            raise ValueError(f"unknown phase: {phase}")
        now = self._advance_to(now)
        self._phase[boss] = phase
        return None

    def snapshot(self, boss):
        self._check_boss(boss)
        snapshot_id = self._next_snapshot_id
        self._next_snapshot_id += 1
        record = {
            "snapshot_id": snapshot_id,
            "boss": boss,
            "time": self.now,
            "phase": self._phase[boss],
            "entries": deepcopy(self._entries[boss]),
            "last_taunt": self._last_taunt.get(boss),
        }
        self._snapshots[snapshot_id] = record
        self._snapshot_order.append(snapshot_id)
        return {
            "snapshot_id": snapshot_id,
            "boss": boss,
            "time": self.now,
            "phase": self._phase[boss],
        }

    def rewind(self, snapshot_id, now):
        record = self._snapshots.get(snapshot_id)
        if record is None:
            raise ValueError(f"unknown snapshot: {snapshot_id}")
        now = self._number(now, "time")
        if now < self.now:
            raise ValueError("time moved backwards")

        boss = record["boss"]
        if self._phase[boss] != record["phase"]:
            raise ValueError("cannot rewind across phases")
        if now - record["time"] > self.REWIND_WINDOW:
            raise ValueError("snapshot expired")

        entries = deepcopy(record["entries"])
        shift = now - record["time"]
        for entry in entries.values():
            entry["reached"] += shift
        self._entries[boss] = entries

        last_taunt = record["last_taunt"]
        if last_taunt is None:
            self._last_taunt.pop(boss, None)
        else:
            self._last_taunt[boss] = last_taunt + shift
        self.now = now
        return None

    def top(self, boss, n):
        self._check_boss(boss)
        if type(n) is not int or n < 1 or n > 8:
            raise ValueError("n must be between 1 and 8")
        ordered = sorted(
            self._entries[boss].items(),
            key=lambda item: (-item[1]["threat"], item[1]["reached"], item[1]["seq"]),
        )
        return [
            {"actor": actor, "threat": entry["threat"]}
            for actor, entry in ordered[:n]
        ]

    def tick(self, now):
        self._advance_to(now)
        return None

    def state(self):
        result = {}
        summary = {}
        for boss in self.bosses:
            vector = {
                actor: entry["threat"] for actor, entry in self._entries[boss].items()
            }
            result[boss] = vector
            if vector:
                highest_actor = min(
                    self._entries[boss].items(),
                    key=lambda item: (
                        -item[1]["threat"],
                        item[1]["reached"],
                        item[1]["seq"],
                    ),
                )[0]
                summary[boss] = {
                    "highest": highest_actor,
                    "max": vector[highest_actor],
                    "total": sum(vector.values()),
                }
            else:
                summary[boss] = {"highest": None, "max": 0.0, "total": 0.0}

        result["links"] = [deepcopy(link) for link in self._links]
        result["snapshots"] = list(self._snapshot_order)
        result["summary"] = summary
        return result
