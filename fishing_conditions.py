import random

PITY_THRESHOLD = 10
COOLDOWN_SECONDS = 30
SECONDS_PER_DAY = 86400
SPECIES_SALT = 1
ESCAPE_SALT = 2


class FishingSpot:
    def __init__(self, spots, fish, multipliers=None, king_limit=1):
        self.spots = spots
        self.fish = fish
        self.multipliers = multipliers or {}
        self.king_limit = king_limit
        self._casts = {}
        self._next_cast_id = 1
        self._last_cast_at = {}
        self._pity = 0
        self._catches = {}
        self._king_caught = {}
        self._cast_count = 0

    def _known_baits(self):
        return set(self.multipliers.get("bait", {}).keys())

    def _known_weathers(self):
        return set(self.multipliers.get("weather", {}).keys())

    def _known_seasons(self):
        seasons = set(self.multipliers.get("season", {}).keys())
        for entry in self.fish:
            seasons.update(entry.get("seasons", []))
        return seasons

    def _known_depths(self):
        return set(self.multipliers.get("depth", {}).keys())

    def _eligible(self, entry, conditions):
        season = conditions.get("season")
        if season is not None and entry.get("seasons") and season not in entry["seasons"]:
            return False
        hour = conditions.get("hour")
        window = entry.get("hours")
        if hour is not None and window and not (window[0] <= hour < window[1]):
            return False
        return True

    def weights(self, spot, bait):
        conditions = self.spots[spot]
        result = {}
        for entry in self.fish:
            if not self._eligible(entry, conditions):
                result[entry["id"]] = 0
                continue
            weight = float(entry.get("base", 0))
            for axis in ("weather", "season", "hour", "depth", "bait"):
                table = self.multipliers.get(axis)
                if not table:
                    continue
                key = bait if axis == "bait" else conditions.get(axis)
                axis_table = table.get(key)
                if axis_table is None:
                    continue
                weight *= axis_table.get(entry["id"], 1.0)
            result[entry["id"]] = weight
        return result

    def cast(self, player, spot, bait, rod, now):
        if bait not in self._known_baits():
            raise ValueError(f"unknown bait: {bait}")
        conditions = self.spots[spot]
        if conditions.get("weather") not in self._known_weathers():
            raise ValueError(f"unknown weather: {conditions.get('weather')}")
        if conditions.get("season") is not None and conditions["season"] not in self._known_seasons():
            raise ValueError(f"unknown season: {conditions['season']}")
        known_depths = self._known_depths()
        if known_depths and conditions.get("depth") not in known_depths:
            raise ValueError(f"unknown depth: {conditions.get('depth')}")

        cooldown_key = (player, spot)
        last_cast = self._last_cast_at.get(cooldown_key)
        if last_cast is not None and now - last_cast < COOLDOWN_SECONDS:
            raise ValueError(f"spot {spot} is on cooldown for {player}")

        cast_id = self._next_cast_id
        self._next_cast_id += 1
        self._casts[cast_id] = {
            "player": player,
            "spot": spot,
            "bait": bait,
            "rod": rod,
            "now": now,
        }
        self._last_cast_at[cooldown_key] = now
        self._cast_count += 1
        return cast_id

    def _eligible_rare(self, conditions):
        return [
            entry["id"]
            for entry in self.fish
            if entry.get("rarity") == "rare" and self._eligible(entry, conditions)
        ]

    def _pick_fish(self, weights, seed):
        choices = [(fish_id, weight) for fish_id, weight in weights.items() if weight > 0]
        if not choices:
            return None
        total = sum(weight for _, weight in choices)
        point = self._random(seed, SPECIES_SALT, int(total))
        upto = 0
        for fish_id, weight in choices:
            upto += weight
            if point < upto:
                return fish_id
        return choices[-1][0]

    def _random(self, seed, salt, modulo):
        rng_seed = (seed * 73856093) ^ (salt * 19349663)
        return random.Random(rng_seed).getrandbits(64) % modulo

    def _escape_roll(self, fish_id, rod, seed):
        entry = next(item for item in self.fish if item["id"] == fish_id)
        difficulty = entry.get("difficulty", 1)
        escape_rate = min(1.0, max(0.0, difficulty * 0.15 - rod * 0.05))
        if escape_rate <= 0:
            return False
        roll = self._random(seed, ESCAPE_SALT, 1000) / 1000.0
        return roll < escape_rate

    def resolve(self, cast_id, seed):
        pending = self._casts.pop(cast_id, None)
        if pending is None:
            raise ValueError(f"unknown cast: {cast_id}")

        spot = pending["spot"]
        conditions = self.spots[spot]
        weights = self.weights(spot, pending["bait"])
        day = pending["now"] // SECONDS_PER_DAY

        rare_ids = self._eligible_rare(conditions)
        forced_rare = self._pity >= PITY_THRESHOLD and rare_ids
        fish_id = rare_ids[0] if forced_rare else self._pick_fish(weights, seed)
        entry = None

        if fish_id is not None:
            entry = self._fish_entry(fish_id)
            if entry.get("rarity") == "king":
                caught_today = self._king_caught.get(day, 0)
                if caught_today >= self.king_limit:
                    fish_id = None
                    entry = None

        escaped = False
        if fish_id is not None and not forced_rare:
            escaped = self._escape_roll(fish_id, pending["rod"], seed)

        if fish_id is not None and not escaped:
            if entry.get("rarity") == "rare":
                self._pity = 0
            else:
                self._pity += 1
            if entry.get("rarity") == "king":
                self._king_caught[day] = self._king_caught.get(day, 0) + 1
            self._catches[fish_id] = self._catches.get(fish_id, 0) + 1
        else:
            self._pity += 1

        return {
            "cast": cast_id,
            "player": pending["player"],
            "spot": spot,
            "fish": fish_id,
            "escaped": escaped,
        }

    def _fish_entry(self, fish_id):
        return next(item for item in self.fish if item["id"] == fish_id)

    def snapshot(self):
        occupancy = {}
        for pending in self._casts.values():
            occupancy[pending["spot"]] = occupancy.get(pending["spot"], 0) + 1
        return {
            "casts": self._cast_count,
            "catches": dict(self._catches),
            "pity": self._pity,
            "occupancy": occupancy,
            "king_caught": dict(self._king_caught),
        }
