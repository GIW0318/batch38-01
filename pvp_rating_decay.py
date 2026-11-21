DAY = 86400
WEEK = 7 * DAY
IDLE_GRACE = 30 * DAY
DECAY_PER_WEEK = 25
DECAY_CAP = 200
PLACEMENT_GAMES = 10
K_PLACEMENT = 64
K_NORMAL = 32
MIN_TEAM = 1
MAX_TEAM = 5


class RatingBook:
    def __init__(self):
        self.players = {}
        self._last_active = {}
        self._games = {}
        self._decay_applied = {}
        self._reported = set()
        self._last_time = 0

    def _check_time(self, at):
        if not isinstance(at, (int, float)) or at < 0:
            raise ValueError("invalid timestamp")
        if at < self._last_time:
            raise ValueError("time went backwards")
        self._last_time = at

    def register(self, player, at):
        self._check_time(at)
        if player not in self.players:
            self.players[player] = 1500
            self._games[player] = 0
            self._decay_applied[player] = 0
        self._last_active[player] = at
        self._decay_applied[player] = 0
        return True

    def _validate_team(self, team):
        if not isinstance(team, (list, tuple)):
            raise ValueError("team must be a list")
        if not MIN_TEAM <= len(team) <= MAX_TEAM:
            raise ValueError("team size must be 1..5")
        if len(set(team)) != len(team):
            raise ValueError("duplicate player in team")

    def report(self, winner_team, loser_team, at):
        self._check_time(at)
        self._validate_team(winner_team)
        self._validate_team(loser_team)
        if set(winner_team) & set(loser_team):
            raise ValueError("player appears in both teams")
        for name in list(winner_team) + list(loser_team):
            if name not in self.players:
                raise ValueError("unknown player: %r" % (name,))

        key = (tuple(sorted(winner_team)), tuple(sorted(loser_team)), at)
        if key in self._reported:
            return False
        self._reported.add(key)

        avg_w = sum(self.players[p] for p in winner_team) / len(winner_team)
        avg_l = sum(self.players[p] for p in loser_team) / len(loser_team)
        expected_w = 1.0 / (1.0 + 10.0 ** ((avg_l - avg_w) / 400.0))

        k_w = K_PLACEMENT if any(self._games[p] < PLACEMENT_GAMES for p in winner_team) else K_NORMAL
        k_l = K_PLACEMENT if any(self._games[p] < PLACEMENT_GAMES for p in loser_team) else K_NORMAL
        gain = int(round(k_w * (1.0 - expected_w)))
        loss = int(round(k_l * expected_w))

        for p in winner_team:
            self.players[p] += gain
            self._games[p] += 1
            self._last_active[p] = at
            self._decay_applied[p] = 0
        for p in loser_team:
            self.players[p] -= loss
            self._games[p] += 1
            self._last_active[p] = at
            self._decay_applied[p] = 0
        return True

    def decay(self, at):
        self._check_time(at)
        for name in self.players:
            idle = at - self._last_active.get(name, 0)
            if idle < IDLE_GRACE:
                continue
            weeks = int((idle - IDLE_GRACE) // WEEK) + 1
            target = min(weeks * DECAY_PER_WEEK, DECAY_CAP)
            delta = target - self._decay_applied[name]
            if delta <= 0:
                continue
            self.players[name] = max(0, self.players[name] - delta)
            self._decay_applied[name] = target
        return True

    def rating(self, player):
        return self.players.get(player)

    def book(self):
        return {
            "count": len(self.players),
            "decayed": sum(1 for v in self._decay_applied.values() if v > 0),
            "players": dict(self.players),
        }
