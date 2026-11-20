import pytest

import av_sync_clock as ac


def clock():
    return ac.AvClock()


def primed(video=1.0, audio=1.0, now=0.0):
    game = clock()
    game.push_video(video, now)
    game.push_audio(audio, now)
    return game


def test_push_video_is_accepted():
    game = clock()
    game.push_video(1.0, 0.0)
    assert game.clock_view()["video_pts"] == 1.0


def test_push_audio_is_accepted():
    game = clock()
    game.push_audio(1.0, 0.0)
    assert game.clock_view()["audio_pts"] == 1.0


def test_audio_master_when_buffer_is_healthy():
    game = primed(video=1.0, audio=0.7)
    assert game.tick(0.0)["master"] == "audio"


def test_video_fallback_when_buffer_is_low():
    game = primed(video=1.0, audio=0.95)
    assert game.tick(0.0)["master"] == "video"


def test_small_drift_does_not_change_action():
    game = primed(video=1.02, audio=1.0)
    assert game.tick(0.0)["action"] == "none"


def test_positive_drift_drops_video():
    game = primed(video=1.2, audio=1.0)
    assert game.tick(0.0)["action"] == "drop_video"


def test_negative_drift_repeats_video():
    game = primed(video=0.8, audio=1.0)
    assert game.tick(0.0)["action"] == "repeat_video"


def test_resample_ratio_is_clamped():
    game = primed(video=1.3, audio=1.0)
    assert 0.98 <= game.tick(0.0)["ratio"] <= 1.02


def test_pause_freezes_clock():
    game = primed()
    game.pause()
    assert game.tick(1.0)["action"] == "paused"


def test_seek_resets_buffer():
    game = primed()
    game.seek(2.0)
    assert game.clock_view()["buffer"] == pytest.approx(0.0)


def test_negative_pts_is_rejected():
    with pytest.raises(ValueError):
        clock().push_video(-1.0, 0.0)


def test_time_going_backwards_is_rejected():
    game = primed()
    with pytest.raises(ValueError):
        game.push_video(2.0, -1.0)


def test_unknown_rate_is_rejected():
    with pytest.raises(ValueError):
        clock().set_rate(0.1)


def test_rate_applies_to_both_streams():
    game = primed()
    game.set_rate(2.0)
    assert game.clock_view()["rate"] == 2.0


def test_clock_view_returns_copy():
    game = primed()
    snap = game.clock_view()
    snap["drops"] = 99
    assert game.clock_view()["drops"] != 99
