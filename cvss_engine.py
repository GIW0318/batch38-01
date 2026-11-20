class CvssEngine:
    def __init__(self):
        pass

    def score(self, vector, profile=None):
        return None

    def batch(self, vectors, profile=None):
        return {}

    def severity(self, score):
        return None

    def breakdown(self, vector, profile=None):
        return {}

    def cache_stats(self):
        return {}
