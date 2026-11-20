import pytest

import decal_projection as dp


def decal(iid="d1", size=1.0, priority=0, lifetime=10, normal=(0.0, 0.0, 1.0)):
    return {
        "id": iid,
        "position": (0.0, 0.0, 0.0),
        "normal": normal,
        "size": size,
        "rotation": 0.0,
        "lifetime": lifetime,
        "priority": priority,
    }


def pool(capacity=64):
    return dp.DecalPool(capacity)


def test_add_activates_decal():
    game = pool()
    game.add(decal(), 0)
    assert game.decals()["active"] == 1


def test_backface_is_rejected():
    game = pool()
    game.add(decal(), 0)
    assert game.project((0.0, 0.0, -1.0)) == pytest.approx(0.0)


def test_angle_fades_alpha():
    game = pool()
    game.add(decal(), 0)
    assert 0.0 < game.project((1.0, 0.0, 1.0)) < 1.0


def test_full_pool_evicts_low_priority():
    game = pool(capacity=1)
    game.add(decal("low", priority=0), 0)
    game.add(decal("high", priority=5), 1)
    assert game.decals()["active"] == 1
    assert game.decals()["evicted"] == 1


def test_same_priority_evicts_oldest():
    game = pool(capacity=1)
    game.add(decal("old"), 0)
    game.add(decal("new"), 1)
    assert game.decals()["items"][0]["id"] == "new"


def test_expire_removes_old_decals():
    game = pool()
    game.add(decal(lifetime=5), 0)
    game.expire(6)
    assert game.decals()["active"] == 0


def test_project_inside_is_opaque():
    game = pool()
    game.add(decal(), 0)
    assert game.project((0.0, 0.0, 0.0)) == pytest.approx(1.0)


def test_depth_offset_is_size_based():
    game = pool()
    game.add(decal(size=2.0), 0)
    assert game.decals()["items"][0]["depth_offset"] == pytest.approx(0.002)


def test_zero_size_is_rejected():
    with pytest.raises(ValueError):
        pool().add(decal(size=0.0), 0)


def test_zero_normal_is_rejected():
    with pytest.raises(ValueError):
        pool().add(decal(normal=(0.0, 0.0, 0.0)), 0)


def test_negative_lifetime_is_rejected():
    with pytest.raises(ValueError):
        pool().add(decal(lifetime=-1), 0)


def test_items_are_sorted_by_priority_then_age():
    game = pool()
    game.add(decal("low", priority=0), 0)
    game.add(decal("high", priority=2), 1)
    assert game.decals()["items"][0]["id"] == "high"


def test_expire_reports_removed_count():
    game = pool()
    game.add(decal(lifetime=1), 0)
    assert game.expire(2) == 1


def test_unknown_decal_project_is_safe():
    assert pool().project((0.0, 0.0, 0.0)) == pytest.approx(0.0)


def test_decals_returns_copy():
    game = pool()
    game.add(decal(), 0)
    snap = game.decals()
    snap["items"].clear()
    assert game.decals()["items"]
