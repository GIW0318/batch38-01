class ConnectGuard:
    def __init__(self, resolver, policy):
        self.resolver = resolver
        self.policy = policy

    def authorize(self, method, target, headers, policy=None):
        return None

    def release(self, tunnel_id, now):
        return None

    def tunnels(self):
        return {}
