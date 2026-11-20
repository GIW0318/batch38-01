class AvClock:
    def __init__(self):
        pass

    def push_video(self, pts, now):
        return None

    def push_audio(self, pts, now):
        return None

    def tick(self, now):
        return None

    def seek(self, now):
        return None

    def set_rate(self, rate):
        return None

    def pause(self):
        return None

    def resume(self):
        return None

    def clock_view(self):
        return {}
