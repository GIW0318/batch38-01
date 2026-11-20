class CombatFold:
    DAMAGE_TYPES = frozenset({"damage", "dot"})
    EVENT_TYPES = DAMAGE_TYPES | frozenset({"absorb", "engage", "wipe", "kill"})
    CONTROL_TYPES = frozenset({"engage", "wipe", "kill"})

    def __init__(self, pet_owner=None):
        self.pet_owner = dict(pet_owner or {})
        self._seen_ids = set()
        self._last_t = None
        self._event_count = 0
        self._encounters = []
        self._current = None

    def _new_encounter(self, start):
        encounter = {
            "start": start,
            "last_t": start,
            "end": None,
            "total_damage": 0,
            "sources": {},
            "abilities": {},
            "direct_hits": 0,
            "direct_crits": 0,
            "overkill": 0,
            "absorbed": 0,
        }
        self._encounters.append(encounter)
        self._current = encounter
        return encounter

    def _close_encounter(self, t):
        if self._current is not None:
            self._current["last_t"] = t
            self._current["end"] = t
            self._current = None

    def _validate(self, events):
        seen = set(self._seen_ids)
        last_t = self._last_t
        accepted = []

        for event in events:
            event_id = event["id"]
            if event_id in seen:
                continue

            kind = event["type"]
            if kind not in self.EVENT_TYPES:
                raise ValueError("unknown event type: {!r}".format(kind))

            amount = event.get("amount", 0)
            if kind not in self.CONTROL_TYPES and amount < 0:
                raise ValueError("negative event amount: {!r}".format(amount))

            t = event["t"]
            if last_t is not None and t < last_t:
                raise ValueError("event time went backwards: {!r} < {!r}".format(t, last_t))

            seen.add(event_id)
            accepted.append(event)
            last_t = t

        return accepted

    def ingest(self, events):
        accepted = self._validate(events)

        for event in accepted:
            self._seen_ids.add(event["id"])
            self._last_t = event["t"]
            self._event_count += 1

            kind = event["type"]
            t = event["t"]

            if kind == "engage":
                if self._current is not None:
                    self._close_encounter(t)
                self._new_encounter(t)
                continue

            if kind in ("wipe", "kill"):
                self._close_encounter(t)
                continue

            if self._current is None:
                self._new_encounter(t)

            current = self._current
            current["last_t"] = t

            if kind == "absorb":
                current["absorbed"] += event.get("amount", 0)
                continue

            source = event["source"]
            source = self.pet_owner.get(source, source)
            amount = event.get("amount", 0)
            ability = event["ability"]

            current["total_damage"] += amount
            current["sources"][source] = current["sources"].get(source, 0) + amount
            current["abilities"][ability] = current["abilities"].get(ability, 0) + amount
            current["overkill"] += event.get("overkill", 0)

            if kind == "damage":
                current["direct_hits"] += 1
                if event.get("crit", False):
                    current["direct_crits"] += 1

        return len(accepted)

    def summary(self, encounter_id=1):
        if encounter_id < 1 or encounter_id > len(self._encounters):
            return {}

        encounter = self._encounters[encounter_id - 1]
        end = encounter["last_t"] if encounter["end"] is None else encounter["end"]
        uptime = max(0, end - encounter["start"])
        total_damage = encounter["total_damage"]
        direct_hits = encounter["direct_hits"]

        return {
            "total_damage": total_damage,
            "dps": total_damage / uptime if uptime else 0.0,
            "abilities": dict(encounter["abilities"]),
            "crit_rate": (
                encounter["direct_crits"] / direct_hits if direct_hits else 0.0
            ),
            "overkill": encounter["overkill"],
            "sources": dict(encounter["sources"]),
            "absorbed": encounter["absorbed"],
            "uptime": uptime,
        }

    def totals(self):
        return {
            "events": self._event_count,
            "encounters": len(self._encounters),
        }
