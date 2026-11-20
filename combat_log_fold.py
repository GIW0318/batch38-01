class CombatFold:
    def __init__(self, pet_owner=None):
        self.pet_owner = dict(pet_owner or {})

    def ingest(self, events):
        return None

    def summary(self, encounter_id=1):
        return {}

    def totals(self):
        return {}
