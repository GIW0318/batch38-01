class VaultQuorum:
    def __init__(self, vaults, operators):
        self.vaults = vaults
        self.operators = operators

    def open_request(self, vault, action, operators, ttl, now):
        return None

    def approve(self, request_id, operator, credential, now):
        return None

    def unlock(self, request_id, credential, now):
        return None

    def deny(self, request_id, operator, now):
        return None

    def lockout(self, vault, now):
        return None

    def audit(self):
        return []
