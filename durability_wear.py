import math
import secrets

QUALITY_WEAR = {1: 1.0, 2: 0.9, 3: 0.8, 4: 0.7, 5: 0.6}
QUOTE_TTL_SECONDS = 60
DAY_SECONDS = 86400
DEATH_PENALTY_RATIO = 0.10


class DurabilityBook:
    def __init__(self, items):
        self.items = {item["id"]: item for item in items}
        self._combat = False
        self._quotes = {}
        self._audit = []
        self._seq = 0
        self._versions = {item_id: 0 for item_id in self.items}
        self._bless_day = {}

    def _item(self, item_id):
        item = self.items.get(item_id)
        if item is None:
            raise ValueError("unknown item: %s" % item_id)
        return item

    def _touch(self, item_id):
        self._versions[item_id] = self._versions.get(item_id, 0) + 1

    def _record(self, event_type, item_id, **fields):
        self._seq += 1
        entry = {"seq": self._seq, "type": event_type, "item_id": item_id}
        entry.update(fields)
        self._audit.append(entry)

    def wear(self, item_id, hits, cause, now):
        item = self._item(item_id)
        if hits < 0:
            raise ValueError("hits must be non-negative")
        coef = QUALITY_WEAR.get(item.get("quality", 1), 1.0)
        damage = math.ceil(hits * coef)
        if cause == "environment":
            damage = math.ceil(damage / 2)
        elif cause == "death":
            damage += math.ceil(item["max"] * DEATH_PENALTY_RATIO)
        if damage <= 0:
            return 0
        new_current = item["current"] - damage
        if new_current <= 0:
            day = now // DAY_SECONDS
            if item.get("blessed") and self._bless_day.get(item_id) != day:
                item["current"] = 1
                item["blessed"] = False
                item["broken"] = False
                self._bless_day[item_id] = day
                self._touch(item_id)
                self._record("wear", item_id, hits=hits, cause=cause,
                             damage=damage, current=1, blessed_save=True)
                return damage
            new_current = 0
        item["current"] = new_current
        item["broken"] = new_current <= 0
        self._touch(item_id)
        self._record("wear", item_id, hits=hits, cause=cause,
                     damage=damage, current=new_current)
        return damage

    def quote(self, item_id, points, now):
        item = self._item(item_id)
        if points <= 0:
            raise ValueError("points must be positive")
        unit_price = item.get("quality", 1) * 2
        record = {
            "quote_id": secrets.token_hex(16),
            "item_id": item_id,
            "points": points,
            "unit_price": unit_price,
            "cost": points * unit_price,
            "missing": item["max"] - item["current"],
            "version": self._versions.get(item_id, 0),
            "created": now,
            "used": False,
        }
        self._quotes[record["quote_id"]] = record
        self._record("quote", item_id, quote_id=record["quote_id"],
                     points=points, cost=record["cost"])
        return {
            "quote_id": record["quote_id"],
            "points": points,
            "unit_price": unit_price,
            "cost": record["cost"],
        }

    def repair(self, item_id, quote_id, now):
        item = self._item(item_id)
        if self._combat:
            raise ValueError("cannot repair while in combat")
        record = self._quotes.get(quote_id)
        if record is None or record["item_id"] != item_id:
            raise ValueError("unknown quote")
        if record["used"]:
            raise ValueError("quote already consumed")
        if now - record["created"] > QUOTE_TTL_SECONDS:
            raise ValueError("quote expired")
        if record["version"] != self._versions.get(item_id, 0):
            raise ValueError("quote voided by durability change")
        missing = item["max"] - item["current"]
        if record["points"] > missing:
            raise ValueError("repair points exceed missing durability")
        record["used"] = True
        item["current"] += record["points"]
        item["broken"] = False
        self._touch(item_id)
        self._record("repair", item_id, quote_id=quote_id,
                     points=record["points"], cost=record["cost"],
                     current=item["current"])
        return {"cost": record["cost"], "current": item["current"]}

    def upgrade_max(self, item_id, new_max, now):
        item = self._item(item_id)
        if self._combat:
            raise ValueError("cannot upgrade while in combat")
        if new_max <= 0:
            raise ValueError("new_max must be positive")
        old_max = item["max"]
        ratio = (item["current"] / old_max) if old_max else 0.0
        item["max"] = new_max
        item["current"] = int(round(ratio * new_max))
        item["broken"] = item["current"] <= 0
        self._touch(item_id)
        self._record("upgrade", item_id, new_max=new_max,
                     current=item["current"])
        return item["current"]

    def set_combat(self, flag):
        self._combat = bool(flag)

    def reconcile(self):
        active = {}
        for item in self.items.values():
            set_id = item.get("set_id")
            if not set_id:
                continue
            active.setdefault(set_id, 0)
            if item["current"] > 0:
                active[set_id] += 1
        return active

    def audit(self):
        return [dict(entry) for entry in self._audit]
