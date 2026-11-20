import pytest

import blend_state_cache as bc


def desc(**over):
    value = {
        "blend_src": "src_alpha",
        "blend_dst": "one_minus_src_alpha",
        "blend_op": "add",
        "depth_test": True,
        "depth_write": True,
        "depth_func": "less",
        "cull": "back",
        "color_mask": "rgba",
    }
    value.update(over)
    return value


def cache(capacity=256):
    return bc.BlendCache(capacity=capacity)


def test_get_returns_handle():
    assert isinstance(cache().get(desc()), int)


def test_same_desc_returns_same_handle():
    game = cache()
    first = game.get(desc())
    assert isinstance(first, int)
    assert first == game.get(desc())


def test_blend_factor_changes_handle():
    game = cache()
    assert game.get(desc()) != game.get(desc(blend_src="one"))


def test_depth_write_changes_handle():
    game = cache()
    assert game.get(desc()) != game.get(desc(depth_write=False))


def test_cull_changes_handle():
    game = cache()
    assert game.get(desc()) != game.get(desc(cull="none"))


def test_color_mask_changes_handle():
    game = cache()
    assert game.get(desc()) != game.get(desc(color_mask="rgb"))


def test_redundant_bind_is_counted():
    game = cache()
    game.bind(desc(), 0)
    game.bind(desc(), 1)
    assert game.stats()["redundant"] == 1


def test_bind_switches_state():
    game = cache()
    assert game.bind(desc(), 0) is True


def test_invalidate_reports_entries():
    game = cache()
    game.bind(desc(), 0)
    game.invalidate(1)
    assert "entries" in game.stats()


def test_capacity_evicts_lru():
    game = cache(capacity=1)
    game.bind(desc(), 0)
    game.bind(desc(blend_src="one"), 1)
    assert game.stats()["evicted"] >= 1


def test_unknown_enum_is_rejected():
    with pytest.raises(ValueError):
        cache().get(desc(blend_op="magic"))


def test_missing_field_is_rejected():
    bad = desc()
    del bad["cull"]
    with pytest.raises(ValueError):
        cache().get(bad)


def test_negative_capacity_is_rejected():
    with pytest.raises(ValueError):
        bc.BlendCache(capacity=-1)


def test_stats_records_hits_and_misses():
    game = cache()
    game.get(desc())
    game.get(desc())
    info = game.stats()
    assert info["hits"] + info["misses"] >= 2


def test_stats_returns_copy():
    game = cache()
    game.get(desc())
    snap = game.stats()
    snap["hits"] = 99
    assert game.stats()["hits"] != 99
