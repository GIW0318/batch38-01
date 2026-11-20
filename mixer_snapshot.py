class MixerRecall:
    def __init__(self):
        pass

    def capture(self, name, buses, params, now):
        return None

    def blend(self, a, b, t, curve):
        return {}

    def apply(self, name, bus, now):
        return None

    def schedule(self, name, at, curve):
        return None

    def rollback(self, steps):
        return None

    def detail(self):
        return {}
