class PowGate:
    def __init__(self, secret):
        self.secret = secret

    def issue(self, client, now, difficulty=None):
        return None

    def verify(self, client, challenge_id, nonce, now):
        return {}

    def challenges(self):
        return {}
