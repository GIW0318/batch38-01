BASE_TIMES = {level: 1500 + 60 * level for level in range(2, 16)}

AFFIX_TIME_BONUS = {"bloodlust": 120, "fortified": 60}
GRIEVOUS = "grievous"
GRIEVOUS_DEATH_EXTRA = 5

CHECKPOINT_REWARD = 15
DEATH_PENALTY_STEP = 5
MAX_DEATHS = 5
MAX_PAUSE_SECONDS = 180

UPGRADE_TWO_RATIO = 0.4
UPGRADE_ONE_RATIO = 0.2


class KeystoneRun:
    def __init__(self):
        self._started = False
        self._finished = False

    def start(self, key_level, party, affixes, route, now):
        if self._started:
            raise ValueError("run already started")
        if key_level not in BASE_TIMES:
            raise ValueError("invalid key level")
        if not party:
            raise ValueError("party must not be empty")
        if len(set(party)) != len(party):
            raise ValueError("duplicate party members")
        if not route:
            raise ValueError("route must not be empty")
        if len(set(route)) != len(route):
            raise ValueError("duplicate route nodes")

        self._started = True
        self._level = key_level
        self._party = list(party)
        self._affixes = set(affixes)
        self._route = list(route)
        self._start_now = now
        self._now = now
        self._last_now = now
        self._duration = BASE_TIMES[key_level] + sum(
            AFFIX_TIME_BONUS[name] for name in self._affixes if name in AFFIX_TIME_BONUS
        )
        self._claimed = []
        self._bonus = 0
        self._deaths = 0
        self._penalty = 0
        self._member_stats = {name: {"deaths": 0, "penalty": 0} for name in self._party}
        self._pause_start = None
        self._paused_total = 0
        self._depleted = False
        self._status = "running"
        self._upgrade = 0
        return self.ledger()

    def checkpoint(self, node, now):
        self._require_active(now)
        if self._pause_start is not None:
            raise ValueError("cannot checkpoint while paused")
        if node not in self._route:
            raise ValueError("unknown checkpoint node")
        granted = False
        if node not in self._claimed:
            expected = self._route[len(self._claimed)]
            if node != expected:
                raise ValueError("checkpoints must follow route order")
            self._claimed.append(node)
            self._bonus += CHECKPOINT_REWARD
            granted = True
        self._now = now
        self._last_now = now
        return {
            "node": node,
            "granted": granted,
            "bonus": self._bonus,
            "remaining": self._remaining_at(now),
        }

    def death(self, actor, now):
        self._require_active(now)
        if self._pause_start is not None:
            raise ValueError("cannot record death while paused")
        if actor not in self._party:
            raise ValueError("unknown party member")
        self._deaths += 1
        penalty = DEATH_PENALTY_STEP * self._deaths
        if GRIEVOUS in self._affixes:
            penalty += GRIEVOUS_DEATH_EXTRA
        self._penalty += penalty
        stats = self._member_stats[actor]
        stats["deaths"] += 1
        stats["penalty"] += penalty
        self._now = now
        self._last_now = now
        if self._deaths >= MAX_DEATHS:
            self._depleted = True
            self._status = "depleted"
        return {
            "deaths": self._deaths,
            "penalty": self._penalty,
            "depleted": self._depleted,
        }

    def swap(self, old_member, new_member, now):
        self._require_active(now)
        if self._pause_start is None:
            raise ValueError("swap requires the run to be paused")
        if old_member not in self._party:
            raise ValueError("unknown member")
        if new_member in self._party:
            raise ValueError("member already in party")
        index = self._party.index(old_member)
        self._party[index] = new_member
        self._member_stats[new_member] = self._member_stats.pop(old_member)
        self._now = now
        self._last_now = now
        return {"party": list(self._party)}

    def pause(self, now):
        self._require_active(now)
        if self._pause_start is not None:
            raise ValueError("run already paused")
        if not self._claimed:
            raise ValueError("pause is only allowed at a checkpoint")
        self._pause_start = now
        self._last_now = now
        return {"paused": True, "pause_start": now}

    def resume(self, now):
        self._require_active(now)
        if self._pause_start is None:
            raise ValueError("run is not paused")
        paused = now - self._pause_start
        if paused > MAX_PAUSE_SECONDS:
            raise ValueError("pause limit exceeded")
        self._paused_total += paused
        self._pause_start = None
        self._last_now = now
        return {"paused": False, "paused_total": self._paused_total}

    def finish(self, now):
        if not self._started:
            raise ValueError("run not started")
        if self._finished:
            raise ValueError("run already finished")
        if now < self._last_now:
            raise ValueError("time cannot go backwards")
        if self._pause_start is not None:
            raise ValueError("cannot finish while paused")
        remaining = self._remaining_at(now)
        if self._depleted or remaining <= 0:
            self._status = "depleted"
            self._upgrade = 0
        else:
            ratio = remaining / self._duration
            if ratio > UPGRADE_TWO_RATIO:
                self._upgrade = 2
            elif ratio > UPGRADE_ONE_RATIO:
                self._upgrade = 1
            else:
                self._upgrade = 0
            self._status = "success" if self._upgrade else "depleted"
        self._finished = True
        self._now = now
        self._last_now = now
        self._level += self._upgrade
        return {
            "status": self._status,
            "upgrade": self._upgrade,
            "level": self._level,
            "remaining": remaining,
        }

    def ledger(self):
        if not self._started:
            return {}
        members = []
        for name in self._party:
            stats = self._member_stats[name]
            members.append(
                {
                    "name": name,
                    "deaths": stats["deaths"],
                    "penalty": stats["penalty"],
                    "reward": self._bonus // len(self._party),
                    "affixes": self._affix_impact(stats),
                }
            )
        return {
            "level": self._level,
            "status": self._status,
            "duration": self._duration,
            "remaining": self._duration + self._paused_total - (self._now - self._start_now),
            "deaths": self._deaths,
            "penalty": self._penalty,
            "bonus": self._bonus,
            "paused": self._pause_start is not None,
            "paused_total": self._paused_total,
            "party": list(self._party),
            "affixes": sorted(self._affixes),
            "route": list(self._route),
            "checkpoints": list(self._claimed),
            "upgrade": self._upgrade,
            "members": members,
        }

    def _require_active(self, now):
        if not self._started:
            raise ValueError("run not started")
        if self._finished:
            raise ValueError("run already finished")
        if self._depleted:
            raise ValueError("run is depleted")
        if now < self._last_now:
            raise ValueError("time cannot go backwards")

    def _remaining_at(self, now):
        elapsed = now - self._start_now
        return self._duration + self._paused_total + self._bonus - self._penalty - elapsed

    def _affix_impact(self, stats):
        impact = {}
        for name in self._affixes:
            if name in AFFIX_TIME_BONUS:
                impact[name] = AFFIX_TIME_BONUS[name]
            elif name == GRIEVOUS:
                impact[name] = GRIEVOUS_DEATH_EXTRA * stats["deaths"]
        return impact
