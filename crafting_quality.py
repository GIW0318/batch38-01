class CraftBench:
    def __init__(self, recipes, material_quality, skill=1.0):
        self.recipes = recipes
        self.material_quality = material_quality
        self.skill = skill

    def craft_batch(self, recipe_id, slots, seed, stamp):
        return None

    def quote(self, recipe_id, slots):
        return {}

    def salvage(self, item_id, stamp):
        return {}

    def ledger(self):
        return {}
import copy

ROLL_MAX = 20
DIRECT_FACTOR = 1.0


class CraftBench:
    def __init__(self, recipes, material_quality, skill=1.0):
        self.recipes = recipes
        self.material_quality = material_quality
        self.skill = skill
        self._batch_count = 0
        self._consumed = {}
        self._produced = {}
        self._salvaged = []

    def craft_batch(self, recipe_id, slots, seed, stamp):
        recipe = self.recipes.get(recipe_id)
        if recipe is None:
            raise ValueError("unknown recipe: %r" % (recipe_id,))
        if not isinstance(seed, int) or seed < 0:
            raise ValueError("seed must be a non-negative integer")

        required = recipe.get("materials", {})
        substitutes = recipe.get("substitutes", {})
        roll = seed % (ROLL_MAX + 1)

        planned = []
        claimed_ids = set()
        for index, slot in enumerate(slots):
            provided = slot.get("materials", {})
            for group in set(required) | set(provided):
                wanted = required.get(group, 0)
                given = len(provided.get(group, []))
                if given < wanted:
                    raise ValueError(
                        "missing material for group %r: need %d, got %d"
                        % (group, wanted, given)
                    )
                if given > wanted:
                    raise ValueError(
                        "extra material for group %r: need %d, got %d"
                        % (group, wanted, given)
                    )

            item_id = "%s:%d:%d" % (recipe_id, index, seed)
            if item_id in claimed_ids or item_id in self._produced:
                raise ValueError("duplicate item id: %r" % (item_id,))
            claimed_ids.add(item_id)

            planned.append(
                {
                    "id": item_id,
                    "quality": self._score(recipe, provided, substitutes, roll),
                    "qty": 2 if roll == ROLL_MAX else 1,
                    "bound": bool(slot.get("bound", False)),
                    "recipe": recipe_id,
                    "slot": index,
                    "seed": seed,
                    "stamp": stamp,
                    "materials": copy.deepcopy(provided),
                }
            )

        for item in planned:
            for materials in item["materials"].values():
                for material in materials:
                    self._consumed[material] = self._consumed.get(material, 0) + 1
            self._produced[item["id"]] = item
        self._batch_count += 1
        return copy.deepcopy(planned)

    def quote(self, recipe_id, slots):
        recipe = self.recipes.get(recipe_id)
        if recipe is None:
            raise ValueError("unknown recipe: %r" % (recipe_id,))

        required = recipe.get("materials", {})
        substitutes = recipe.get("substitutes", {})
        slot_count = len(slots)
        group_totals = {}
        combined = {}
        for slot in slots:
            for group, materials in slot.get("materials", {}).items():
                group_totals[group] = group_totals.get(group, 0) + len(materials)
                combined.setdefault(group, []).extend(materials)

        gaps = {}
        for group, wanted in required.items():
            shortage = wanted * slot_count - group_totals.get(group, 0)
            if shortage > 0:
                gaps[group] = shortage

        mean = self._material_mean(combined, substitutes)
        baseline = recipe["base"] + mean * 0.3 + self.skill * 10
        return {
            "gaps": gaps,
            "quality": {
                "min": round(baseline),
                "max": round(baseline + ROLL_MAX),
            },
        }

    def salvage(self, item_id, stamp):
        item = self._produced.get(item_id)
        if item is None:
            raise ValueError("unknown item: %r" % (item_id,))
        if item["bound"]:
            raise ValueError("bound item cannot be salvaged: %r" % (item_id,))

        totals = {}
        for materials in item["materials"].values():
            for material in materials:
                totals[material] = totals.get(material, 0) + 1
        returned = {
            material: amount // 2
            for material, amount in totals.items()
            if amount // 2 > 0
        }

        del self._produced[item_id]
        self._salvaged.append(
            {
                "item": item_id,
                "stamp": stamp,
                "returned": copy.deepcopy(returned),
            }
        )
        return returned

    def ledger(self):
        return copy.deepcopy(
            {
                "batches": self._batch_count,
                "consumed": self._consumed,
                "produced": self._produced,
                "salvaged": self._salvaged,
            }
        )

    def _score(self, recipe, provided, substitutes, roll):
        mean = self._material_mean(provided, substitutes)
        total = (
            recipe["base"]
            + mean * 0.3
            + self.skill * 10
            + roll
        )
        return round(total)

    def _material_mean(self, provided, substitutes):
        weighted_sum = 0.0
        count = 0
        for group, materials in provided.items():
            table = substitutes.get(group, {})
            for material in materials:
                factor = table.get(material, DIRECT_FACTOR)
                weighted_sum += self.material_quality.get(material, 0) * factor
                count += 1
        if count == 0:
            return 0.0
        return weighted_sum / count
