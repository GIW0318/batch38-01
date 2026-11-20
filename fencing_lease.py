class FenceLease:
    def __init__(self):
        pass

    def acquire(self, resource, owner, now, ttl):
        return None

    def renew(self, token, now, ttl=None):
        return None

    def release(self, token):
        return None

    def validate(self, resource, token, now):
        return None

    def leases(self):
        return {}
