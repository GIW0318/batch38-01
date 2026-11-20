class TalentGrid:
    BASE_CAP = 51
    TIER_COUNT = 7
    POINTS_PER_TIER = 5
    RESPEC_COST_PER_POINT = 50
    FREE_WINDOW = 30 * 86400
    SPECS = ("a", "b")

    def __init__(self, tree):
        self.tree = list(tree)
        self.nodes = {}
        for node in self.tree:
            node_id = node["id"]
            if node_id in self.nodes:
                raise ValueError("duplicate node id: %s" % node_id)
            self.nodes[node_id] = node

        self.gear_bonus = 0
        self.in_combat = False
        self.builds = {}
        self.state = {
            spec: {
                "ranks": {node_id: 0 for node_id in self.nodes},
                "order": [],
                "last_free": None,
            }
            for spec in self.SPECS
        }

    def _validate_spec(self, spec):
        if spec not in self.state:
            raise ValueError("unknown spec: %s" % spec)

    def _validate_node(self, node_id):
        if node_id not in self.nodes:
            raise ValueError("unknown node: %s" % node_id)
        return self.nodes[node_id]

    def _cap(self):
        return self.BASE_CAP + self.gear_bonus

    def _spent(self, spec):
        return sum(self.state[spec]["ranks"].values())

    def _lower_tier_spent(self, spec, tier):
        ranks = self.state[spec]["ranks"]
        return sum(
            ranks[node_id]
            for node_id, node in self.nodes.items()
            if node["tier"] < tier
        )

    def _validate_spend(self, spec, spec_node, points):
        ranks = self.state[spec]["ranks"]
        node_id = spec_node["id"]
        tier = spec_node["tier"]

        if ranks[node_id] + points > spec_node["max_rank"]:
            raise ValueError("node rank exceeds max_rank: %s" % node_id)

        if self._spent(spec) + points > self._cap():
            raise ValueError("talent points exceed cap")

        required_lower = self.POINTS_PER_TIER * (tier - 1)
        if self._lower_tier_spent(spec, tier) < required_lower:
            raise ValueError("tier requirement not met: %s" % node_id)

        for required_id in spec_node.get("requires", []):
            required_node = self._validate_node(required_id)
            if ranks[required_id] != required_node["max_rank"]:
                raise ValueError("prerequisite not maxed: %s" % required_id)

    def spend(self, spec, node, points):
        self._validate_spec(spec)
        spec_node = self._validate_node(node)
        if isinstance(points, bool) or not isinstance(points, int):
            raise ValueError("points must be an integer")
        if points < 0:
            raise ValueError("points cannot be negative")
        if points == 0:
            return self._spent(spec)

        self._validate_spend(spec, spec_node, points)
        state = self.state[spec]
        state["ranks"][node] += points
        state["order"].append((node, points))
        return self._spent(spec)

    def respec(self, spec, ts, free=False):
        self._validate_spec(spec)
        if self.in_combat:
            raise ValueError("cannot respec in combat")

        state = self.state[spec]
        spent = self._spent(spec)
        cost = spent * self.RESPEC_COST_PER_POINT

        if free and spent:
            last_free = state["last_free"]
            if last_free is not None and ts - last_free < self.FREE_WINDOW:
                raise ValueError("free respec is not available yet")
            cost = 0
            state["last_free"] = ts

        while state["order"]:
            node_id, points = state["order"].pop()
            state["ranks"][node_id] -= points

        return cost

    def save_build(self, name, spec):
        self._validate_spec(spec)
        if not isinstance(name, str) or not name:
            raise ValueError("build name must be a non-empty string")
        if name in self.builds:
            raise ValueError("duplicate build name: %s" % name)

        state = self.state[spec]
        self.builds[name] = {
            "spec": spec,
            "ranks": dict(state["ranks"]),
            "order": list(state["order"]),
            "gear_bonus": self.gear_bonus,
        }
        return name

    def _validated_build(self, build):
        if not isinstance(build, dict):
            raise ValueError("invalid build")

        spec = build.get("spec")
        self._validate_spec(spec)

        gear_bonus = build.get("gear_bonus")
        if isinstance(gear_bonus, bool) or not isinstance(gear_bonus, int):
            raise ValueError("invalid gear bonus")
        if gear_bonus < 0:
            raise ValueError("gear bonus cannot be negative")
        cap = self.BASE_CAP + gear_bonus

        raw_ranks = build.get("ranks", {})
        if not isinstance(raw_ranks, dict):
            raise ValueError("invalid build ranks")
        ranks = {node_id: 0 for node_id in self.nodes}
        for node_id, rank in raw_ranks.items():
            self._validate_node(node_id)
            if isinstance(rank, bool) or not isinstance(rank, int):
                raise ValueError("invalid rank")
            if rank < 0 or rank > self.nodes[node_id]["max_rank"]:
                raise ValueError("invalid rank for node: %s" % node_id)
            ranks[node_id] = rank

        if sum(ranks.values()) > cap:
            raise ValueError("build exceeds talent cap")

        for node_id, rank in ranks.items():
            if not rank:
                continue
            node = self.nodes[node_id]
            required_lower = self.POINTS_PER_TIER * (node["tier"] - 1)
            lower_spent = sum(
                ranks[other_id]
                for other_id, other in self.nodes.items()
                if other["tier"] < node["tier"]
            )
            if lower_spent < required_lower:
                raise ValueError("build tier requirement not met")
            for required_id in node.get("requires", []):
                required_node = self._validate_node(required_id)
                if ranks[required_id] != required_node["max_rank"]:
                    raise ValueError("build prerequisite not maxed")

        raw_order = build.get("order", [])
        if not isinstance(raw_order, list):
            raise ValueError("invalid build order")
        order = []
        ordered_ranks = {node_id: 0 for node_id in self.nodes}
        for entry in raw_order:
            if not isinstance(entry, (tuple, list)) or len(entry) != 2:
                raise ValueError("invalid build order")
            node_id, points = entry
            self._validate_node(node_id)
            if isinstance(points, bool) or not isinstance(points, int) or points <= 0:
                raise ValueError("invalid build order")
            order.append((node_id, points))
            ordered_ranks[node_id] += points
        if ordered_ranks != ranks:
            raise ValueError("build order does not match ranks")

        for other_spec, state in self.state.items():
            if other_spec != spec and sum(state["ranks"].values()) > cap:
                raise ValueError("build gear bonus is too low for current points")

        return {
            "spec": spec,
            "ranks": ranks,
            "order": order,
            "gear_bonus": gear_bonus,
        }

    def load_build(self, name):
        if self.in_combat:
            raise ValueError("cannot load build in combat")
        if name not in self.builds:
            raise ValueError("unknown build: %s" % name)

        build = self._validated_build(self.builds[name])
        spec = build["spec"]
        self.gear_bonus = build["gear_bonus"]
        self.state[spec]["ranks"] = build["ranks"]
        self.state[spec]["order"] = build["order"]
        return name

    def set_gear_bonus(self, points):
        if isinstance(points, bool) or not isinstance(points, int):
            raise ValueError("gear bonus must be an integer")
        if points < 0:
            raise ValueError("gear bonus cannot be negative")
        cap = self.BASE_CAP + points
        if any(self._spent(spec) > cap for spec in self.SPECS):
            raise ValueError("gear bonus would lower cap below spent points")
        self.gear_bonus = points
        return cap

    def set_combat(self, flag):
        self.in_combat = bool(flag)

    def view(self, spec):
        self._validate_spec(spec)
        ranks = self.state[spec]["ranks"]
        spent = sum(ranks.values())
        cap = self._cap()
        tiers = []
        tier_spent = {}
        tier_remaining = {}

        for tier in range(1, self.TIER_COUNT + 1):
            tier_nodes = [
                node for node in self.nodes.values() if node["tier"] == tier
            ]
            used = sum(ranks[node["id"]] for node in tier_nodes)
            tier_cap = sum(node["max_rank"] for node in tier_nodes)
            remaining = tier_cap - used
            tier_spent[tier] = used
            tier_remaining[tier] = remaining
            tiers.append(
                {
                    "tier": tier,
                    "spent": used,
                    "remaining": remaining,
                    "cap": tier_cap,
                }
            )

        return {
            "spec": spec,
            "spent": spent,
            "remaining": cap - spent,
            "cap": cap,
            "respec_cost": spent * self.RESPEC_COST_PER_POINT,
            "cost": spent * self.RESPEC_COST_PER_POINT,
            "tiers": tiers,
            "tier_spent": tier_spent,
            "tier_remaining": tier_remaining,
        }
