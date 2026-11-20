GAIT_DRAIN = {"walk": 1, "trot": 3, "gallop": 8, "sprint": 15}
TERRAIN_FACTOR = {"road": 0.8, "grass": 1.0, "sand": 1.3, "water": 2.0}
FEED_ITEMS = {"apple", "carrot", "hay", "oats"}
FEED_RESTORE = 40
FEED_COOLDOWN = 60
REST_REGEN = 5
JUMP_BASE_COST = 10
JUMP_HEIGHT_COST = 2
FALL_THRESHOLD = 3
FALL_PENALTY = 10
EXHAUSTION_WALK_SECONDS = 10


class MountMeter:
    def __init__(self, max_stamina=100):
        self._max_stamina = max_stamina
        self._stamina = max_stamina
        self._terrain = None
        self._last_feed_ts = None
        self._now = 0
        self._exhaustion_remaining = 0

    @property
    def max_stamina(self):
        return self._max_stamina

    @max_stamina.setter
    def max_stamina(self, value):
        self._max_stamina = value
        self._stamina = min(self._stamina, value)

    def _spend(self, amount):
        self._stamina = round(self._stamina - amount, 6)
        if self._stamina <= 0:
            self._stamina = 0
            self._exhaustion_remaining = EXHAUSTION_WALK_SECONDS

    def _regen(self, amount):
        self._stamina = min(self._max_stamina, round(self._stamina + amount, 6))

    def _tick_exhaustion(self, seconds):
        if self._exhaustion_remaining > 0:
            self._exhaustion_remaining = max(0, self._exhaustion_remaining - seconds)

    def ride(self, gait, terrain, seconds):
        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        if gait not in GAIT_DRAIN:
            raise ValueError(f"unknown gait: {gait}")
        if terrain not in TERRAIN_FACTOR:
            raise ValueError(f"unknown terrain: {terrain}")
        if self._exhaustion_remaining > 0:
            gait = "walk"
        self._terrain = terrain
        self._now += seconds
        self._tick_exhaustion(seconds)
        cost = GAIT_DRAIN[gait] * TERRAIN_FACTOR[terrain] * seconds
        self._spend(cost)

    def rest(self, seconds):
        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        self._now += seconds
        self._tick_exhaustion(seconds)
        self._regen(REST_REGEN * seconds)

    def feed(self, item, ts):
        if item not in FEED_ITEMS:
            raise ValueError(f"unknown feed item: {item}")
        if self._last_feed_ts is not None and ts - self._last_feed_ts < FEED_COOLDOWN:
            raise ValueError("feed is on cooldown")
        self._last_feed_ts = ts
        self._now = max(self._now, ts)
        self._regen(FEED_RESTORE)

    def jump(self, height):
        if height < 0:
            raise ValueError("height must be non-negative")
        cost = JUMP_BASE_COST + JUMP_HEIGHT_COST * height
        if height > FALL_THRESHOLD:
            cost += FALL_PENALTY
        self._spend(cost)

    def mount_view(self):
        cooldown_remaining = 0
        if self._last_feed_ts is not None:
            cooldown_remaining = max(0, FEED_COOLDOWN - (self._now - self._last_feed_ts))
        return {
            "stamina": self._stamina,
            "max_stamina": self._max_stamina,
            "status": "exhausted" if self._exhaustion_remaining > 0 else "ok",
            "terrain": self._terrain,
            "cooldown_remaining": cooldown_remaining,
        }
