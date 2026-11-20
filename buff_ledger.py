KNOWN_CLASSES = {
    "warrior",
    "mage",
    "priest",
    "druid",
    "shaman",
    "paladin",
    "hunter",
    "rogue",
    "warlock",
    "death_knight",
    "monk",
    "demon_hunter",
    "evoker",
}

TOTEM_SLOTS = 4
REFRESH_WINDOW = 30
REFRESH_DURATION = 600
INTERNAL_KEYS = ("placed_at", "expiry")


class BuffLedger:
    def __init__(self, groups):
        self.groups = {gid: [dict(m) for m in members] for gid, members in groups.items()}
        self._buffs = {gid: {} for gid in self.groups}

    def _require_group(self, group):
        if group not in self.groups:
            raise ValueError(f"unknown group: {group}")

    @staticmethod
    def _require_time(now):
        if now < 0:
            raise ValueError(f"negative time: {now}")

    def place(self, group, buffs):
        self._require_group(group)
        buffs = list(buffs)
        for b in buffs:
            if b["class"] not in KNOWN_CLASSES:
                raise ValueError(f"unknown class: {b['class']}")
        existing = self._buffs[group]
        seen = set(existing)
        for b in buffs:
            if b["id"] in seen:
                raise ValueError(f"duplicate buff: {b['id']}")
            seen.add(b["id"])
        active_totems = sum(1 for rec in existing.values() if rec["totem"])
        if any(b["totem"] for b in buffs) and active_totems >= TOTEM_SLOTS:
            raise ValueError(f"totem slots full ({TOTEM_SLOTS})")
        for b in buffs:
            record = dict(b)
            record["placed_at"] = 0
            record["expiry"] = record["duration"]
            rival = next(
                (rec for rec in existing.values() if rec["category"] == record["category"]),
                None,
            )
            if rival is not None:
                if record["rank"] > rival["rank"]:
                    del existing[rival["id"]]
                else:
                    continue
            existing[record["id"]] = record

    def refresh(self, now):
        self._require_time(now)
        for buffs in self._buffs.values():
            for rec in buffs.values():
                remaining = rec["expiry"] - now
                if remaining <= 0:
                    continue
                if remaining <= REFRESH_WINDOW:
                    rec["expiry"] = now + REFRESH_DURATION

    def remove(self, group, buff_id):
        self._require_group(group)
        self._buffs[group].pop(buff_id, None)

    def recompute(self, now):
        self._require_time(now)
        for gid, buffs in self._buffs.items():
            self._buffs[gid] = {
                bid: rec for bid, rec in buffs.items() if rec["expiry"] > now
            }

    def _caster(self, members, cls):
        for member in members:
            if member["class"] == cls:
                return member
        return members[0] if members else None

    def coverage(self, now):
        self._require_time(now)
        result = {"groups": {}}
        for gid, members in self.groups.items():
            active = [rec for rec in self._buffs[gid].values() if rec["expiry"] > now]
            active.sort(key=lambda rec: (-rec["rank"], rec["id"]))
            entries = []
            covered = set()
            buff_classes = set()
            for rec in active:
                entry = {k: v for k, v in rec.items() if k not in INTERNAL_KEYS}
                entry["remaining"] = rec["expiry"] - now
                entries.append(entry)
                buff_classes.add(rec["class"])
                caster = self._caster(members, rec["class"])
                for index, member in enumerate(members):
                    if member is caster or member.get("distance", 0) <= rec["range"]:
                        covered.add(index)
            missing = sorted({m["class"] for m in members} - buff_classes)
            result["groups"][gid] = {
                "buffs": entries,
                "covered": len(covered),
                "missing": missing,
            }
        return result
