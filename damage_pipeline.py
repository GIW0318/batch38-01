class DamagePipeline:
    def __init__(self, targets):
        self.targets = targets

    def hit(self, target, amount, dtype, source=None):
        return None

    def shield(self, target, amount, until, dtype, priority=0):
        return None

    def redirect(self, target, to, pct, until):
        return None

    def dot(self, target, amount, dtype, ticks, interval, now):
        return None

    def tick(self, ts):
        return None

    def snapshot(self, target):
        return {}
