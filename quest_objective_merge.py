OBJECTIVE_TYPES = ("kill", "collect", "interact")
SHARE_RANGE = 100.0


def _positive_integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("%s must be a positive integer" % name)
    return value


def _non_negative_time(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("now must be a non-negative number")
    if value < 0:
        raise ValueError("now must not be negative")
    return value


class ObjectiveMerge:
    def __init__(self, quests, inventory=None):
        self.quests = quests
        self.inventory = inventory or {}
        self._players = {}

    def _locate_objective(self, quest_id, objective_id):
        quest = self.quests.get(quest_id)
        if quest is None:
            raise ValueError("unknown quest %s" % quest_id)
        for stage_index, stage in enumerate(quest["stages"]):
            for objective in stage["objectives"]:
                if objective["id"] == objective_id:
                    return quest, stage_index, objective
        raise ValueError("unknown objective %s in quest %s" % (objective_id, quest_id))

    def _fresh_state(self, quest):
        return {
            "stage": 0,
            "stages": [
                {"objectives": {obj["id"]: 0 for obj in stage["objectives"]}}
                for stage in quest["stages"]
            ],
            "sources": set(),
            "submitted": False,
        }

    def _player_state(self, player, quest):
        per_quest = self._players.setdefault(player, {})
        state = per_quest.get(quest["id"])
        if state is None:
            state = self._fresh_state(quest)
            per_quest[quest["id"]] = state
        return state

    @staticmethod
    def _stage_complete(stage_record, stage_def):
        return all(
            stage_record["objectives"][obj["id"]] >= obj["count"]
            for obj in stage_def["objectives"]
        )

    @staticmethod
    def _kwarg(kwargs, *names):
        for name in names:
            if name in kwargs:
                return kwargs[name]
        return None

    def _check_range(self, kwargs):
        distance = self._kwarg(kwargs, "distance", "range", "dist")
        if distance is None:
            return
        if isinstance(distance, bool) or not isinstance(distance, (int, float)):
            raise ValueError("distance must be a number")
        if distance < 0:
            raise ValueError("distance must not be negative")
        if distance > SHARE_RANGE:
            raise ValueError(
                "source is %.1f yards away, shared credit range is %.0f"
                % (distance, SHARE_RANGE)
            )

    def credit(self, quest, objective, player, amount, now, **kwargs):
        action = self._kwarg(kwargs, "action", "op")
        if action == "abandon" or kwargs.get("abandon"):
            return self.abandon(quest, player)
        if action in ("submit", "turn_in", "turn-in") or kwargs.get("submit"):
            return self.submit(quest, player, now)

        quest_def, stage_index, obj = self._locate_objective(quest, objective)
        _positive_integer(amount, "amount")
        _non_negative_time(now)

        objective_type = obj["type"]
        if objective_type not in OBJECTIVE_TYPES:
            raise ValueError("unknown objective type %s" % objective_type)

        existing = self._players.get(player, {}).get(quest)
        if existing is not None:
            if existing["submitted"]:
                raise ValueError("quest %s has already been submitted" % quest)
            if stage_index != existing["stage"]:
                raise ValueError(
                    "objective %s belongs to stage %d, active stage is %d"
                    % (objective, stage_index, existing["stage"])
                )
        elif stage_index != 0:
            raise ValueError(
                "objective %s belongs to stage %d, active stage is %d"
                % (objective, stage_index, 0)
            )

        if objective_type == "kill":
            tag = self._kwarg(kwargs, "tag", "monster_tag")
            required_tag = obj.get("tag")
            if tag is not None and tag != required_tag:
                raise ValueError(
                    "kill objective %s requires tag %r, got %r"
                    % (objective, required_tag, tag)
                )
        self._check_range(kwargs)

        state = self._player_state(player, quest_def)
        source_id = self._kwarg(kwargs, "source_id", "source", "entity_id")
        if source_id is not None and source_id in state["sources"]:
            return None

        stage_record = state["stages"][stage_index]
        current = stage_record["objectives"][objective]
        if current >= obj["count"]:
            raise ValueError(
                "objective %s in quest %s is already complete" % (objective, quest)
            )
        capped = min(current + amount, obj["count"])
        stage_record["objectives"][objective] = capped
        if source_id is not None:
            state["sources"].add(source_id)

        while (
            state["stage"] < len(quest_def["stages"]) - 1
            and self._stage_complete(
                state["stages"][state["stage"]],
                quest_def["stages"][state["stage"]],
            )
        ):
            state["stage"] += 1
        return capped

    def _player_inventory(self, player, kwargs):
        bag = self._kwarg(kwargs, "inventory", "items", "bag")
        if bag is not None:
            if player in bag and isinstance(bag[player], dict):
                return bag[player]
            return bag
        per_player = self.inventory.get(player)
        if per_player is None:
            return {}
        return per_player

    def submit(self, quest, player, now=None, **kwargs):
        quest_def = self.quests.get(quest)
        if quest_def is None:
            raise ValueError("unknown quest %s" % quest)
        if now is not None:
            _non_negative_time(now)
        state = self._player_state(player, quest_def)
        if state["submitted"]:
            raise ValueError("quest %s has already been submitted" % quest)

        last_index = len(quest_def["stages"]) - 1
        if state["stage"] != last_index or not self._stage_complete(
            state["stages"][last_index], quest_def["stages"][last_index]
        ):
            raise ValueError("quest %s is not complete and cannot be submitted" % quest)

        bag = self._player_inventory(player, kwargs)
        consumed = {}
        for stage_def in quest_def["stages"]:
            for obj in stage_def["objectives"]:
                if obj["type"] != "collect":
                    continue
                item = obj.get("item", obj["id"])
                needed = obj["count"]
                available = bag.get(item, 0)
                if not isinstance(available, int) or isinstance(available, bool):
                    raise ValueError("inventory count for %s must be an integer" % item)
                if available < needed:
                    raise ValueError(
                        "not enough %s to submit quest %s: need %d, have %d"
                        % (item, quest, needed, available)
                    )
                bag[item] = available - needed
                consumed[item] = needed

        state["submitted"] = True
        return {"ok": True, "quest": quest, "player": player, "consumed": consumed}

    turn_in = submit
    complete_quest = submit

    def abandon(self, quest, player):
        quest_def = self.quests.get(quest)
        if quest_def is None:
            raise ValueError("unknown quest %s" % quest)
        per_quest = self._players.get(player)
        if not per_quest or quest not in per_quest:
            return {"ok": True, "rolled_back": False}
        state = per_quest[quest]
        if state["submitted"]:
            return {"ok": True, "rolled_back": False}
        per_quest[quest] = self._fresh_state(quest_def)
        return {"ok": True, "rolled_back": True}

    give_up = abandon
    cancel_quest = abandon

    def progress(self):
        snapshot = {}
        for player, per_quest in self._players.items():
            player_snapshot = {}
            for quest_id, state in per_quest.items():
                quest_def = self.quests[quest_id]
                entry = {"stage": state["stage"]}
                stage_breakdown = []
                for stage_index, stage_def in enumerate(quest_def["stages"]):
                    stage_entry = {"stage": stage_index, "objectives": {}}
                    for obj in stage_def["objectives"]:
                        value = state["stages"][stage_index]["objectives"][obj["id"]]
                        entry[obj["id"]] = value
                        stage_entry["objectives"][obj["id"]] = value
                    stage_breakdown.append(stage_entry)
                entry["submitted"] = state["submitted"]
                entry["stages"] = stage_breakdown
                player_snapshot[quest_id] = entry
            snapshot[player] = player_snapshot
        return snapshot
