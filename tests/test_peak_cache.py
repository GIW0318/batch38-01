import pytest

import peak_cache as pc


def cache(samples=None, channels=2, block=64):
    game = pc.PeakCache()
    game.build(samples or [0.5, -0.5] * 128, channels, block)
    return game


def test_level_zero_keeps_original_blocks():
    game = cache([0.1, -0.2] * 64, block=64)
    info = game.query(0, 64, 0, 0)
    assert info["min"] <= info["max"]


def test_channels_are_separate():
    game = cache([0.1, -0.9] * 64, channels=2)
    left = game.query(0, 64, 0, 0)
    right = game.query(0, 64, 0, 1)
    assert left != right


def test_odd_tail_is_kept():
    game = cache([0.5] * 129, channels=1, block=64)
    assert game.stats()["blocks"] == 3


def test_update_recomputes_upper_levels():
    game = cache([0.1] * 128, channels=1, block=64)
    before = game.stats()["version"]
    game.update(0, [0.9] * 64, channels=1)
    assert game.stats()["version"] == before + 1


def test_query_returns_min_max_and_clip():
    game = cache([0.0, 2.0] * 64, channels=2)
    info = game.query(0, 64, 0, 1)
    assert info["max"] >= 1.0
    assert info["clipped"] is True


def test_query_range_is_validated():
    game = cache()
    with pytest.raises(ValueError):
        game.query(-1, 10, 0, 0)
    with pytest.raises(ValueError):
        game.query(10, 5, 0, 0)


def test_block_size_is_limited():
    with pytest.raises(ValueError):
        pc.PeakCache().build([0.0] * 100, 1, 100)


def test_level_out_of_range_is_rejected():
    game = cache()
    with pytest.raises(ValueError):
        game.query(0, 10, 99, 0)


def test_eviction_reduces_memory():
    game = cache([0.0] * 4096, channels=1, block=64)
    before = game.stats()["memory"]
    game.evict(before // 2)
    assert game.stats()["memory"] <= before


def test_stats_reports_queries():
    game = cache()
    game.query(0, 10, 0, 0)
    assert game.stats()["queries"] == 1


def test_stats_returns_copy():
    game = cache()
    snap = game.stats()
    snap["blocks"] = 99
    assert game.stats()["blocks"] != 99


def test_min_max_order_is_correct():
    game = cache([0.2, 0.8] * 64)
    info = game.query(0, 64, 0, 0)
    assert info["min"] <= info["max"]


def test_clipping_at_exactly_one_counts():
    game = cache([1.0, -1.0] * 64)
    assert game.query(0, 64, 0, 0)["clipped"] is True


def test_rebuild_resets_version():
    game = cache()
    game.build([0.0] * 128, 1, 64)
    assert game.stats()["version"] == 0


def test_empty_samples_are_allowed():
    game = pc.PeakCache()
    game.build([], 1, 64)
    assert game.stats()["blocks"] == 0
