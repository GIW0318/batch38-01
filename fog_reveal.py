class FogGrid:
    def __init__(self, size=64, radius=8, walls=None):
        self.size = size
        self.radius = radius
        self.walls = set(walls or [])

    def reveal(self, player, x, y, now):
        return None

    def share(self, team, player):
        return None

    def coverage(self, player, x, y):
        return None

    def save(self):
        return {}

    def load(self, data):
        return None

    def snapshot(self):
        return {}
