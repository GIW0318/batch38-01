class WarLedger:
    def __init__(self, nodes, duration=1800, start=0):
        self.nodes = {node["id"]: node for node in nodes}
        self.duration = duration
        self.start = start

    def capture(self, node, guild, now):
        return None

    def tick(self, now):
        return None

    def surrender(self, guild, now):
        return None

    def standings(self):
        return {}
