import pytest

import lod_dither as ld


def test_near_distance_is_lod_zero():
    assert ld.LodDither().select(10.0, 0)["level"] == 0


def test_mid_distance_is_lod_one():
    assert ld.LodDither().select(45.0, 0)["level"] == 1


def test_far_distance_is_lod_two():
    assert ld.LodDither().select(90.0, 0)["level"] == 2


def test_very_far_distance_is_lod_three():
    assert ld.LodDither().select(200.0, 0)["level"] == 3


def test_hysteresis_prevents_boundary_flapping():
    game = ld.LodDither()
    assert game.select(10.0, 0)["level"] == 0
    assert game.select(29.0, 0)["level"] == 0
    assert game.select(31.0, 0)["level"] == 1
    assert game.select(29.0, 0)["level"] == 1
    assert game.select(27.0, 0)["level"] == 0


def test_bias_is_clamped():
    high = ld.LodDither().select(45.0, 5)
    normal = ld.LodDither().select(45.0, 2)
    assert high["level"] == normal["level"]
    assert high["blend"] == pytest.approx(normal["blend"])


def test_pattern_returns_binary_bayer_cells():
    game = ld.LodDither()
    values = [game.pattern(x, y, 0) for x in range(4) for y in range(4)]
    assert set(values) <= {0, 1}
    assert 0 < sum(values) < 16


def test_pattern_rotates_with_frame():
    game = ld.LodDither()
    first = [game.pattern(x, y, 0) for x in range(4) for y in range(4)]
    second = [game.pattern(x, y, 1) for x in range(4) for y in range(4)]
    assert first != second


def test_pattern_is_stable_for_same_frame():
    game = ld.LodDither()
    value = game.pattern(1, 2, 3)
    assert value in (0, 1)
    assert value == game.pattern(1, 2, 3)


def test_crossfade_band_has_blend():
    info = ld.LodDither().select(30.0, 0)
    assert 0.0 < info["blend"] < 1.0


def test_negative_distance_is_rejected():
    with pytest.raises(ValueError):
        ld.LodDither().select(-1.0, 0)


def test_negative_frame_is_rejected():
    with pytest.raises(ValueError):
        ld.LodDither().pattern(0, 0, -1)


def test_detail_counts_switches():
    game = ld.LodDither()
    for distance in (10.0, 45.0, 90.0, 200.0):
        game.select(distance, 0)
    info = game.detail()
    assert info["switches"] == [1, 1, 1, 1]


def test_detail_returns_copy():
    game = ld.LodDither()
    game.select(45.0, 1)
    snap = game.detail()
    snap["switches"][0] = 99
    assert game.detail()["switches"][0] == 0


def test_selected_level_stays_in_range():
    game = ld.LodDither()
    for distance in (0.0, 30.0, 60.0, 120.0, 1000.0):
        level = game.select(distance, -5)["level"]
        assert 0 <= level <= 3
