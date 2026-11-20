class DurabilityBook:
    def __init__(self, items):
        self.items = {item["id"]: item for item in items}

    def wear(self, item_id, hits, cause, now):
        return None

    def quote(self, item_id, points, now):
        return None

    def repair(self, item_id, quote_id, now):
        return None

    def upgrade_max(self, item_id, new_max, now):
        return None

    def set_combat(self, flag):
        return None

    def reconcile(self):
        return {}

    def audit(self):
        return []
