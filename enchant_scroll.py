LAYER_GAIN = (1.0, 0.5, 0.25)
MAX_LAYERS = 3
TYPE_SLOTS = {"weapon": 3, "armor": 2}


class EnchantStack:
    def __init__(self):
        self._items = {}

    def _validate_item(self, item):
        if not isinstance(item, dict) or "id" not in item or "level" not in item:
            raise ValueError("unknown item")
        item.setdefault("enchantments", [])
        self._items[item["id"]] = item

    def _slots(self, item):
        if "slots" in item:
            return item["slots"]
        return TYPE_SLOTS.get(item.get("type"), 0)

    def _find(self, item, enchant_id):
        for entry in item["enchantments"]:
            if entry["id"] == enchant_id:
                return entry
        return None

    def _entry_gain(self, entry):
        return sum(LAYER_GAIN[: entry["layers"]])

    def _total_gain(self, item):
        return sum(self._entry_gain(entry) for entry in item["enchantments"])

    def apply(self, item, enchant, ts):
        self._validate_item(item)

        if enchant["tier"] > item["level"] // 10:
            raise ValueError("item level is too low for this enchant")

        entry = self._find(item, enchant["id"])
        if entry is None:
            for other in item["enchantments"]:
                if other["group"] == enchant["group"]:
                    raise ValueError("an enchant of the same group is already applied")
            if len(item["enchantments"]) >= self._slots(item):
                raise ValueError("no free enchant slot on item")
            entry = {
                "id": enchant["id"],
                "group": enchant["group"],
                "tier": enchant["tier"],
                "curse": enchant["curse"],
                "layers": 0,
                "expire_at": ts + enchant["duration"],
            }
            item["enchantments"].append(entry)

        if entry["layers"] >= MAX_LAYERS:
            raise ValueError("enchant already at maximum layers")

        entry["layers"] += 1
        entry["expire_at"] = ts + enchant["duration"]

        return {
            "gain": LAYER_GAIN[entry["layers"] - 1],
            "slots": self._slots(item) - len(item["enchantments"]),
        }

    def remove(self, item, enchant, ts):
        self._validate_item(item)
        enchant_id = enchant["id"] if isinstance(enchant, dict) else enchant
        entry = self._find(item, enchant_id)
        if entry is None:
            raise ValueError("enchant is not applied to item")
        if entry["curse"]:
            raise ValueError("curses cannot be removed")

        entry["layers"] -= 1
        if entry["layers"] == 0:
            item["enchantments"].remove(entry)

        return {
            "layers": entry["layers"],
            "gain": self._entry_gain(entry) if entry["layers"] else 0,
        }

    def tick(self, ts):
        for item in list(self._items.values()):
            item["enchantments"] = [
                entry
                for entry in item["enchantments"]
                if entry["expire_at"] > ts
            ]

    def item_view(self, item):
        self._validate_item(item)
        entries = [dict(entry) for entry in item["enchantments"]]
        expire_at = min((entry["expire_at"] for entry in entries), default=None)
        return {
            "enchantments": entries,
            "gain": self._total_gain(item),
            "expire_at": expire_at,
        }
