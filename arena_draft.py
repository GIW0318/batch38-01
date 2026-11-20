STEP_SECONDS = 30
MAX_BANS = 3
MAX_PICKS = 5
MIN_BANS_BEFORE_PICK = 2
TEAMS = ("A", "B")


class DraftRoom:
    def __init__(self, heroes):
        self.heroes = {}
        for hero in heroes:
            hero_id = hero["id"]
            if hero_id in self.heroes:
                raise ValueError(f"duplicate hero in pool: {hero_id}")
            self.heroes[hero_id] = dict(hero)
        self._first = "A"
        self._reset()

    def _reset(self):
        self.bans = {"A": [], "B": []}
        self.picks = {"A": [], "B": []}
        self.started = False
        self._last_clock = None
        self._step_start = 0
        self._now = 0

    @property
    def step(self):
        return self._total_bans() + self._total_picks()

    def _total_bans(self):
        return len(self.bans["A"]) + len(self.bans["B"])

    def _total_picks(self):
        return len(self.picks["A"]) + len(self.picks["B"])

    def _other(self, team):
        return "B" if team == "A" else "A"

    def _track_team(self, count):
        return self._first if count % 2 == 0 else self._other(self._first)

    def _used(self):
        return (
            set(self.bans["A"])
            | set(self.bans["B"])
            | set(self.picks["A"])
            | set(self.picks["B"])
        )

    def _complete(self):
        return all(len(self.picks[team]) == MAX_PICKS for team in TEAMS)

    def _check_common(self, team, hero, clock):
        if self.started:
            raise ValueError("draft already started")
        if self._complete():
            raise ValueError("draft is complete")
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        if self._last_clock is not None and clock <= self._last_clock:
            raise ValueError("conflicting submission timestamp")
        if hero not in self.heroes:
            raise ValueError(f"unknown hero: {hero}")
        if hero in self._used():
            raise ValueError(f"hero already banned or picked: {hero}")

    def _advance(self, clock):
        self._last_clock = clock
        self._now = clock
        self._step_start = clock

    def ban(self, team, hero, clock):
        self._check_common(team, hero, clock)
        if len(self.bans[team]) >= MAX_BANS:
            raise ValueError(f"team {team} ban quota exhausted")
        if team != self._track_team(self._total_bans()):
            raise ValueError(f"out of turn: ban belongs to {self._track_team(self._total_bans())}")
        self.bans[team].append(hero)
        self._advance(clock)

    def pick(self, team, hero, clock):
        self._check_common(team, hero, clock)
        if self._total_bans() < MIN_BANS_BEFORE_PICK:
            raise ValueError("ban phase not complete")
        if len(self.picks[team]) >= MAX_PICKS:
            raise ValueError(f"team {team} pick quota exhausted")
        if team != self._track_team(self._total_picks()):
            raise ValueError(f"out of turn: pick belongs to {self._track_team(self._total_picks())}")
        self.picks[team].append(hero)
        self._advance(clock)

    def timeout(self, clock):
        if self._last_clock is not None and clock < self._last_clock:
            raise ValueError("clock moved backwards")
        self._now = clock
        while not self._complete() and clock - self._step_start >= STEP_SECONDS:
            available = sorted(hero_id for hero_id in self.heroes if hero_id not in self._used())
            if not available:
                break
            hero = available[0]
            if self._total_bans() < MIN_BANS_BEFORE_PICK:
                team = self._track_team(self._total_bans())
                self.bans[team].append(hero)
            else:
                team = self._track_team(self._total_picks())
                if len(self.picks[team]) >= MAX_PICKS:
                    break
                self.picks[team].append(hero)
            self._step_start += STEP_SECONDS
        self._last_clock = clock

    def start(self):
        if not self._complete():
            raise ValueError("draft is not complete")
        for team in TEAMS:
            roles = {self.heroes[hero]["role"] for hero in self.picks[team]}
            if "tank" not in roles or "healer" not in roles:
                raise ValueError(f"team {team} missing tank or healer")
        self.started = True
        return {"ok": True}

    def rematch(self):
        self._first = self._other(self._first)
        self._reset()

    def draft_view(self):
        return {
            "bans": {"A": list(self.bans["A"]), "B": list(self.bans["B"])},
            "picks": {"A": list(self.picks["A"]), "B": list(self.picks["B"])},
            "step": self.step,
            "remaining": max(0, STEP_SECONDS - (self._now - self._step_start)),
        }
