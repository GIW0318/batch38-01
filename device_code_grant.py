class DeviceGrant:
    def __init__(self, apps, allowed_perms, ttl=300):
        self.apps = apps
        self.allowed_perms = allowed_perms
        self.ttl = ttl

    def begin(self, app_key, fingerprint, perms, now):
        return None

    def claim(self, short_code, account, now):
        return None

    def redeem(self, handle, fingerprint, now):
        return None

    def revoke_subject(self, account, now):
        return None

    def snapshot(self):
        return {}
