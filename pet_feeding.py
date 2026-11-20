QUALITY_HAPPINESS = {1: 1, 2: 2, 3: 3, 4: 5, 5: 8}
BUFF_DURATION = 300
MAX_BUFFS = 2
PLAY_COOLDOWN = 120
PLAY_HAPPINESS = 10
PLAY_HUNGER_COST = 5
HUNGER_DECAY_INTERVAL = 600
HUNGER_DECAY_AMOUNT = 5
LOW_HUNGER_THRESHOLD = 20
HAPPINESS_DECAY_PER_MINUTE = 2


class FeedBowl:
    def __init__(self, pets, meals):
        self.pets = pets
        self.meals = meals
        self._now = 0
        self._meal_last = {}
        self._play_last = {}
        self._buffs = {}
        self._hunger_acc = 0
        self._happiness_acc = 0

    def _pet(self, pet_id):
        pet = self.pets.get(pet_id)
        if pet is None:
            raise ValueError("unknown pet: %r" % pet_id)
        return pet

    def _check_ts(self, ts):
        if ts < 0:
            raise ValueError("negative timestamp")
        self._now = max(self._now, ts)

    def _active_buffs(self, pet_id, now):
        return [b for b in self._buffs.get(pet_id, []) if b["expires"] > now]

    def give(self, pet_id, meal_id, ts):
        self._check_ts(ts)
        pet = self._pet(pet_id)
        meal = self.meals.get(meal_id)
        if meal is None:
            raise ValueError("unknown meal: %r" % meal_id)
        if not pet["alive"]:
            raise ValueError("pet is dead")
        key = (pet_id, meal_id)
        last = self._meal_last.get(key)
        if last is not None and ts - last < meal["cooldown"]:
            raise ValueError("meal on cooldown")
        nutrition = meal["nutrition"]
        if meal.get("category") != pet.get("diet"):
            nutrition //= 2
        if pet["hunger"] + nutrition > 100:
            raise ValueError("hunger would exceed 100")
        buff_id = meal.get("buff")
        active = self._active_buffs(pet_id, ts)
        if buff_id and not any(b["id"] == buff_id for b in active):
            if len(active) >= MAX_BUFFS:
                raise ValueError("too many distinct buffs")
        pet["hunger"] += nutrition
        pet["happiness"] = min(
            100, pet["happiness"] + QUALITY_HAPPINESS.get(meal["quality"], 0)
        )
        self._meal_last[key] = ts
        if buff_id:
            active = [b for b in active if b["id"] != buff_id]
            active.append({"id": buff_id, "expires": ts + BUFF_DURATION})
            self._buffs[pet_id] = active

    def tick(self, ts):
        if ts < 0:
            raise ValueError("negative timestamp")
        self._now += ts
        self._hunger_acc += ts
        hunger_drops = self._hunger_acc // HUNGER_DECAY_INTERVAL
        self._hunger_acc -= hunger_drops * HUNGER_DECAY_INTERVAL
        self._happiness_acc += ts
        minutes = self._happiness_acc // 60
        self._happiness_acc -= minutes * 60
        for pet in self.pets.values():
            if not pet["alive"]:
                continue
            pet["hunger"] = max(0, pet["hunger"] - hunger_drops * HUNGER_DECAY_AMOUNT)
            if pet["hunger"] < LOW_HUNGER_THRESHOLD:
                pet["happiness"] = max(
                    0, pet["happiness"] - minutes * HAPPINESS_DECAY_PER_MINUTE
                )

    def play(self, pet_id, ts):
        self._check_ts(ts)
        pet = self._pet(pet_id)
        if not pet["alive"]:
            raise ValueError("pet is dead")
        last = self._play_last.get(pet_id)
        if last is not None and ts - last < PLAY_COOLDOWN:
            raise ValueError("play on cooldown")
        pet["happiness"] = min(100, pet["happiness"] + PLAY_HAPPINESS)
        pet["hunger"] = max(0, pet["hunger"] - PLAY_HUNGER_COST)
        self._play_last[pet_id] = ts

    def pet_view(self, pet_id):
        pet = self._pet(pet_id)
        buffs = [
            {"id": b["id"], "expires": b["expires"]}
            for b in self._active_buffs(pet_id, self._now)
        ]
        cooldowns = {}
        for (pid, meal_id), last in self._meal_last.items():
            if pid != pet_id:
                continue
            remaining = self.meals[meal_id]["cooldown"] - (self._now - last)
            if remaining > 0:
                cooldowns[meal_id] = remaining
        play_last = self._play_last.get(pet_id)
        play_cooldown = (
            max(0, PLAY_COOLDOWN - (self._now - play_last))
            if play_last is not None
            else 0
        )
        return {
            "id": pet_id,
            "hunger": pet["hunger"],
            "happiness": pet["happiness"],
            "alive": pet["alive"],
            "buffs": buffs,
            "cooldowns": cooldowns,
            "play_cooldown": play_cooldown,
        }
