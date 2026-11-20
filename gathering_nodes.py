import threading


class NodeField:
    RESPAWN_SECONDS = 300
    LOCK_SECONDS = 30
    BONUS_PER_TIER = 0.1
    MAX_BONUS = 0.5

    def __init__(self, nodes):
        self._lock = threading.RLock()
        self._now = 0
        self._nodes = {}

        for node_id, data in nodes.items():
            node = dict(data)
            charges = int(node.get("charges", 0))
            node["id"] = node.get("id", node_id)
            node["charges"] = max(0, charges)
            node["tier"] = int(node.get("tier", 0))
            node["respawn_at"] = node.get("respawn_at", 0)
            node["_capacity"] = max(0, charges)
            node["_tappers"] = set()
            node["_locked_by"] = None
            node["_locked_at"] = None
            self._nodes[node_id] = node

    def _require_node(self, node):
        try:
            return self._nodes[node]
        except (KeyError, TypeError):
            raise ValueError(f"unknown node: {node}") from None

    def _require_time(self, ts):
        try:
            backwards = ts < self._now
        except TypeError:
            raise ValueError("timestamp must be numeric") from None
        if backwards:
            raise ValueError("time cannot move backwards")

    @staticmethod
    def _active_lock(node, ts):
        owner = node["_locked_by"]
        if owner is None:
            return None
        if ts - node["_locked_at"] >= NodeField.LOCK_SECONDS:
            return None
        return owner

    def tap(self, node, player, tool_tier, ts):
        with self._lock:
            self._require_time(ts)
            target = self._require_node(node)

            if target["charges"] <= 0:
                raise ValueError("node is depleted")
            if target["tier"] > tool_tier:
                raise ValueError("tool tier is too low")
            if player in target["_tappers"]:
                raise ValueError("player already tapped this round")

            owner = self._active_lock(target, ts)
            if owner is not None and owner != player:
                raise ValueError("node is locked by another player")

            target["charges"] -= 1
            target["_tappers"].add(player)
            if owner == player:
                target["_locked_by"] = None
                target["_locked_at"] = None
            if target["charges"] == 0:
                target["respawn_at"] = ts + self.RESPAWN_SECONDS
                target["_locked_by"] = None
                target["_locked_at"] = None

            bonus = min(
                self.MAX_BONUS,
                max(0, tool_tier - target["tier"]) * self.BONUS_PER_TIER,
            )
            self._now = ts
            return {
                "node": target["id"],
                "player": player,
                "yield": round(1.0 + bonus, 2),
                "charges": target["charges"],
            }

    def respawn(self, ts):
        with self._lock:
            self._require_time(ts)
            for target in self._nodes.values():
                if target["charges"] <= 0 and target["respawn_at"] <= ts:
                    target["charges"] = target["_capacity"]
                    target["respawn_at"] = 0
                    target["_tappers"].clear()
                    target["_locked_by"] = None
                    target["_locked_at"] = None
            self._now = ts

    def lock(self, node, player, ts):
        with self._lock:
            self._require_time(ts)
            target = self._require_node(node)

            if target["charges"] <= 0:
                raise ValueError("node is depleted")

            owner = self._active_lock(target, ts)
            if owner is not None and owner != player:
                raise ValueError("node is locked by another player")

            target["_locked_by"] = player
            target["_locked_at"] = ts
            self._now = ts

    def nodes(self):
        with self._lock:
            snapshot = {}
            for node_id, target in self._nodes.items():
                owner = self._active_lock(target, self._now)
                cooldown = 0
                if target["charges"] <= 0:
                    cooldown = max(0, target["respawn_at"] - self._now)
                snapshot[node_id] = {
                    "charges": target["charges"],
                    "cooldown": cooldown,
                    "locked_by": owner,
                }
            return snapshot
