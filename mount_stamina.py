class MountMeter:
    def __init__(self, max_stamina=100):
        self.max_stamina = max_stamina

    def ride(self, gait, terrain, seconds):
        return None

    def rest(self, seconds):
        return None

    def feed(self, item, ts):
        return None

    def jump(self, height):
        return None

    def mount_view(self):
        return {}
