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
