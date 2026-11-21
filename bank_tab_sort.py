class VaultSort:
    TAB_COUNT = 6
    SLOTS_PER_TAB = 30

    def __init__(self):
        self._tabs = [self._new_tab() for _ in range(self.TAB_COUNT)]

    @staticmethod
    def _new_tab():
        return [None for _ in range(VaultSort.SLOTS_PER_TAB)]

    @staticmethod
    def _validate_tab(tab):
        if not isinstance(tab, int) or isinstance(tab, bool):
            raise ValueError("invalid tab")
        if tab < 0 or tab >= VaultSort.TAB_COUNT:
            raise ValueError("tab out of range")

    @staticmethod
    def _validate_count(count):
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise ValueError("count must be a positive integer")

    @staticmethod
    def _validate_item(item):
        if not isinstance(item, dict):
            raise ValueError("invalid item")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError("unknown item")
        stack = item.get("stack")
        if not isinstance(stack, int) or isinstance(stack, bool) or stack <= 0:
            raise ValueError("invalid item stack limit")
        bound = item.get("bound", False)
        if not isinstance(bound, bool):
            raise ValueError("invalid item bound flag")
        category = item.get("category", "")
        if not isinstance(category, str):
            raise ValueError("invalid item category")
        return {"id": item_id, "stack": stack, "bound": bound, "category": category}

    def deposit(self, tab, item, count):
        self._validate_tab(tab)
        spec = self._validate_item(item)
        self._validate_count(count)

        slots = self._tabs[tab]
        matching = [
            slot for slot in slots
            if slot is not None
            and slot["id"] == spec["id"]
            and slot["bound"] == spec["bound"]
        ]

        if matching:
            capacity = sum(spec["stack"] - slot["count"] for slot in matching)
            if count > capacity:
                raise ValueError("deposit exceeds stack capacity")
            remaining = count
            for slot in matching:
                room = spec["stack"] - slot["count"]
                if room > 0:
                    moved = min(room, remaining)
                    slot["count"] += moved
                    remaining -= moved
                    if remaining == 0:
                        return

        if count > spec["stack"]:
            raise ValueError("deposit exceeds stack capacity")
        empty_index = next((idx for idx, slot in enumerate(slots) if slot is None), -1)
        if empty_index < 0:
            raise ValueError("tab is full")
        slots[empty_index] = {
            "id": spec["id"],
            "count": count,
            "stack": spec["stack"],
            "bound": spec["bound"],
            "category": spec["category"],
            "locked": False,
        }

    def withdraw(self, tab, item, count):
        self._validate_tab(tab)
        self._validate_count(count)
        if not isinstance(item, str) or not item:
            raise ValueError("unknown item")

        slots = self._tabs[tab]
        available = sum(
            slot["count"] for slot in slots
            if slot is not None and slot["id"] == item
        )
        if available == 0:
            raise ValueError("unknown item")
        if count > available:
            raise ValueError("withdraw exceeds available count")

        remaining = count
        for slot in slots:
            if remaining == 0:
                break
            if slot is not None and slot["id"] == item:
                moved = min(slot["count"], remaining)
                slot["count"] -= moved
                remaining -= moved
        for idx, slot in enumerate(slots):
            if slot is not None and slot["count"] == 0:
                slots[idx] = None

    def compact(self, tab):
        self._validate_tab(tab)
        slots = self._tabs[tab]

        unlocked = [
            slot for slot in slots
            if slot is not None and not slot["locked"]
        ]
        unlocked.sort(key=lambda slot: (slot["category"], slot["id"]))

        merged = []
        for slot in unlocked:
            if (
                merged
                and merged[-1]["id"] == slot["id"]
                and merged[-1]["bound"] == slot["bound"]
                and merged[-1]["count"] < merged[-1]["stack"]
            ):
                target = merged[-1]
                room = target["stack"] - target["count"]
                moved = min(room, slot["count"])
                target["count"] += moved
                slot["count"] -= moved
                if slot["count"] > 0:
                    merged.append(slot)
            else:
                merged.append(slot)

        rebuilt = self._new_tab()
        merged_index = 0
        for idx, slot in enumerate(slots):
            if slot is not None and slot["locked"]:
                rebuilt[idx] = slot
            elif merged_index < len(merged):
                rebuilt[idx] = merged[merged_index]
                merged_index += 1
        self._tabs[tab] = rebuilt

    def detail(self):
        tabs = []
        total = 0
        for tab_slots in self._tabs:
            slot_snapshot = [dict(slot) for slot in tab_slots if slot is not None]
            total += sum(slot["count"] for slot in slot_snapshot)
            tabs.append({"slots": slot_snapshot})
        return {"tabs": tabs, "total": total}
