class PeakCache:
    def __init__(self):
        pass

    def build(self, samples, channels, block):
        return None

    def update(self, start, samples, channels):
        return None

    def query(self, start, end, level, channel):
        return {}

    def evict(self, budget_bytes):
        return None

    def stats(self):
        return {}
