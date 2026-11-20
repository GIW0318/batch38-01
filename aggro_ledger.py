class ThreatTable:
    def __init__(self, bosses=None):
        self.bosses = set(bosses or [])

    def add(self, actor, boss, value, kind, now):
        return None

    def taunt(self, actor, boss, now):
        return None

    def drop(self, actor, boss, pct):
        return None

    def link(self, src, dst, pct, until):
        return None

    def phase(self, boss, phase, now):
        return None

    def snapshot(self, boss):
        return None

    def rewind(self, snapshot_id, now):
        return None

    def top(self, boss, n):
        return []

    def tick(self, now):
        return None

    def state(self):
        return {}
