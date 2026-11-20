class TrailPool:
    def __init__(self, lifetime=2.0, spacing=0.1, width_curve=None, capacity=32):
        pass

    def start_trail(self, now):
        return None

    def emit(self, point, now):
        return None

    def update(self, now):
        return None

    def build(self, camera):
        return {}

    def inspect(self, trail_id):
        return {}

    def snapshot(self):
        return {}
