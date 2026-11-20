class SloRelay:
    def __init__(self):
        pass

    def plan(self, session, idp, sps, now):
        return None

    def dispatch(self, ticket, now):
        return None

    def ack(self, ticket, sp, nonce, now):
        return None

    def state(self, session):
        return {}
