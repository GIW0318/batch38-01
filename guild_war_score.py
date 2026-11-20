class WarLedger:
    def __init__(self, nodes, duration=1800, start=0):
        self.nodes = {node["id"]: node for node in nodes}
        self.duration = duration
        self.start = start
        self._scores = {}
        self._owners = {}
        self._bonus_paid = set()
        self._earliest_capture = {}
        self._settled_minute = {}
        self._last_time = None
        self._ended = False
        self._surrendered_guild = None

    def capture(self, node, guild, now):
        if node not in self.nodes:
            raise ValueError("unknown node: %r" % (node,))
        if not isinstance(guild, str) or not guild.strip():
            raise ValueError("guild must be a non-empty string")
        self._check_time(now)

        self._scores.setdefault(guild, 0)
        self._earliest_capture.setdefault(guild, now)
        if node not in self._bonus_paid:
            self._scores[guild] += 50
            self._bonus_paid.add(node)
            self._settled_minute[node] = now // 60
        self._owners[node] = guild
        self._last_time = now
        return self._owners[node]

    def tick(self, now):
        self._check_time(now)
        if not self._ended:
            effective_now = min(now, self.duration)
            target_minute = effective_now // 60
            double_from = self.duration - 600
            for node_id, guild in self._owners.items():
                settled = self._settled_minute.get(node_id, 0)
                points = self.nodes[node_id]["points"]
                for minute in range(settled + 1, target_minute + 1):
                    multiplier = 2 if minute * 60 > double_from else 1
                    self._scores[guild] += points * multiplier
                    self._settled_minute[node_id] = minute
            if effective_now >= self.duration:
                self._ended = True
        self._last_time = now

    def surrender(self, guild, now):
        self._check_time(now)
        self._ended = True
        self._surrendered_guild = guild
        self._last_time = now

    def standings(self):
        guilds = set(self._scores) | set(self._owners.values())
        scores = {guild: self._scores.get(guild, 0) for guild in guilds}
        node_counts = {guild: 0 for guild in guilds}
        for guild in self._owners.values():
            node_counts[guild] += 1

        winner = None
        if guilds:
            winner = min(
                guilds,
                key=lambda guild: (
                    -scores[guild],
                    -node_counts[guild],
                    self._earliest_capture.get(guild, self._last_time or 0),
                    guild,
                ),
            )

        reference_time = self.start if self._last_time is None else self._last_time
        remaining = max(0, self.duration - reference_time)
        return {
            "scores": scores,
            "nodes": node_counts,
            "winner": winner,
            "remaining": remaining,
            "ended": self._ended,
        }

    def _check_time(self, now):
        if isinstance(now, bool) or not isinstance(now, (int, float)):
            raise ValueError("time must be a number")
        if now < 0:
            raise ValueError("time must not be negative")
        if self._last_time is not None and now < self._last_time:
            raise ValueError("time must not go backwards")
