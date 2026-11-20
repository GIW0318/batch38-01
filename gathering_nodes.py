class NodeField:
    def __init__(self, nodes):
        self.nodes = nodes

    def tap(self, node, player, tool_tier, ts):
        return None

    def respawn(self, ts):
        return None

    def lock(self, node, player, ts):
        return None

    def nodes(self):
        return {}
