STARTUP_BUFFER_SECONDS = 0.2
DRIFT_THRESHOLD_SECONDS = 0.04
RESAMPLE_RATIO_MIN = 0.98
RESAMPLE_RATIO_MAX = 1.02
RATE_MIN = 0.5
RATE_MAX = 2.0


class AvClock:
    def __init__(self):
        self._video_pts = None
        self._audio_pts = None
        self._last_now = None
        self._base_now = None
        self._base_pts = 0.0
        self._rate = 1.0
        self._paused = False
        self._drops = 0
        self._repeats = 0

    def push_video(self, pts, now):
        self._validate_pts(pts)
        self._advance_clock(now)
        self._video_pts = float(pts)

    def push_audio(self, pts, now):
        self._validate_pts(pts)
        self._advance_clock(now)
        self._audio_pts = float(pts)

    def tick(self, now):
        self._advance_clock(now)
        drift, buffer_depth, master = self._sync_metrics()
        if self._paused:
            return {
                "action": "paused",
                "master": master,
                "drift": drift,
                "buffer": buffer_depth,
                "ratio": 1.0,
                "drops": self._drops,
            }
        if drift > DRIFT_THRESHOLD_SECONDS:
            action = "drop_video"
            self._drops += 1
        elif drift < -DRIFT_THRESHOLD_SECONDS:
            action = "repeat_video"
            self._repeats += 1
        else:
            action = "none"
        ratio = self._resample_ratio(drift)
        return {
            "action": action,
            "master": master,
            "drift": drift,
            "buffer": buffer_depth,
            "ratio": ratio,
            "drops": self._drops,
        }

    def seek(self, now):
        self._video_pts = None
        self._audio_pts = None
        self._base_pts = 0.0
        self._base_now = now
        self._last_now = now

    def set_rate(self, rate):
        if not RATE_MIN <= rate <= RATE_MAX:
            raise ValueError("unknown playback rate: %r" % (rate,))
        if not self._paused and self._last_now is not None:
            self._base_pts = self._playback_position(self._last_now)
            self._base_now = self._last_now
        self._rate = float(rate)

    def pause(self):
        if not self._paused and self._last_now is not None:
            self._base_pts = self._playback_position(self._last_now)
            self._base_now = self._last_now
        self._paused = True

    def resume(self):
        if self._paused:
            self._paused = False
            self._base_now = self._last_now

    def clock_view(self):
        drift, buffer_depth, master = self._sync_metrics()
        return {
            "master": master,
            "drift": drift,
            "buffer": buffer_depth,
            "drops": self._drops,
            "repeats": self._repeats,
            "video_pts": 0.0 if self._video_pts is None else self._video_pts,
            "audio_pts": 0.0 if self._audio_pts is None else self._audio_pts,
            "rate": self._rate,
            "paused": self._paused,
        }

    def _validate_pts(self, pts):
        if pts < 0:
            raise ValueError("negative pts is not allowed: %r" % (pts,))

    def _advance_clock(self, now):
        if self._last_now is not None and now < self._last_now:
            raise ValueError("wall clock moved backwards: %r < %r" % (now, self._last_now))
        if self._base_now is None:
            self._base_now = now
        self._last_now = now

    def _playback_position(self, now):
        if self._paused or self._base_now is None:
            return self._base_pts
        return self._base_pts + self._rate * (now - self._base_now)

    def _sync_metrics(self):
        if self._video_pts is None or self._audio_pts is None:
            if self._video_pts is not None:
                master = "video"
            elif self._audio_pts is not None:
                master = "audio"
            else:
                master = "video"
            return 0.0, 0.0, master
        drift = self._video_pts - self._audio_pts
        buffer_depth = abs(drift)
        master = (
            "audio"
            if buffer_depth >= STARTUP_BUFFER_SECONDS
            else "video"
        )
        return drift, buffer_depth, master

    def _resample_ratio(self, drift):
        ratio = 1.0 + drift
        return max(RESAMPLE_RATIO_MIN, min(RESAMPLE_RATIO_MAX, ratio))
