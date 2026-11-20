class CanaryLedger:
    def __init__(self):
        pass

    def mint(self, family, keeper, ttl, ts):
        return None

    def rotate(self, family, ts):
        return None

    def touch(self, mark, caller, tenant, ts):
        return None

    def revoke(self, mark, ts):
        return None

    def report(self, window):
        return []

    def summary(self):
        return {}
