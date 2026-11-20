class BlendCache:
    def __init__(self, capacity=256):
        self.capacity = capacity

    def get(self, desc):
        return None

    def bind(self, desc, ts):
        return None

    def invalidate(self, pass_id):
        return None

    def stats(self):
        return {}
