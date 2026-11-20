import pytest

import downmix_engine as de


def engine():
    return de.DownmixEngine()


def test_center_is_mixed_at_point_seven_zero_seven():
    m = engine().matrix("5.1", "stereo")
    assert m["L"]["C"] == pytest.approx(0.707, abs=0.001)


def test_front_channels_pass_through():
    m = engine().matrix("5.1", "stereo")
    assert m["L"]["FL"] == pytest.approx(1.0)


def test_lfe_is_half_gain():
    m = engine().matrix("5.1", "stereo")
    assert m["L"]["LFE"] == pytest.approx(0.5)


def test_mono_to_stereo_duplicates():
    m = engine().matrix("mono", "stereo")
    assert m["L"]["M"] == pytest.approx(1.0)
    assert m["R"]["M"] == pytest.approx(1.0)


def test_seven_one_back_channels_are_half():
    m = engine().matrix("7.1", "stereo")
    assert m["L"]["BL"] == pytest.approx(0.5)


def test_matrix_rows_are_normalized():
    m = engine().matrix("5.1", "stereo")
    assert m
    for row in m.values():
        assert all(abs(v) <= 1.0 for v in row.values())


def test_apply_returns_target_channel_count():
    out = engine().apply([0.1] * 6, 48000, 48000)
    assert len(out) == 2


def test_output_is_soft_limited():
    out = engine().apply([2.0] * 6, 48000, 48000)
    assert max(abs(x) for x in out) <= 1.0


def test_sample_rate_change_interpolates():
    out = engine().apply([0.1] * 6, 24000, 48000)
    assert len(out) >= 2


def test_invalid_sample_rate_ratio_is_rejected():
    with pytest.raises(ValueError):
        engine().apply([0.1] * 6, 48000, 100000)


def test_unknown_layout_is_rejected():
    with pytest.raises(ValueError):
        engine().matrix("quad", "stereo")


def test_sample_count_must_match_channels():
    with pytest.raises(ValueError):
        engine().apply([0.1] * 5, 48000, 48000)


def test_latency_is_reported():
    assert engine().latency("5.1", "stereo") >= 0


def test_state_returns_copy():
    game = engine()
    game.matrix("5.1", "stereo")
    snap = game.state()
    snap["matrix"].clear()
    assert game.state()["matrix"]


def test_matrix_returns_copy():
    game = engine()
    first = game.matrix("5.1", "stereo")
    first["L"]["C"] = 99
    assert game.matrix("5.1", "stereo")["L"]["C"] != 99
