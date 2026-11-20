class DownmixEngine:
    def __init__(self):
        pass

    def matrix(self, source, target):
        return {}

    def apply(self, samples, source_rate, target_rate):
        return None

    def latency(self, source, target):
        return None

    def state(self):
        return {}
