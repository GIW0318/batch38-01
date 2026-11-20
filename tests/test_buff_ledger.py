import pytest

import buff_ledger as bl

GROUPS = {
    f"g{index}": [
        {"name": f"p{index}-{j}", "class": "warrior" if j == 0 else "mage", "distance": 10}
        for j in range(5)
    ]
    for index in range(5)
}


def buff(bid, category="attack", rank=1, totem=False, cls="warrior", rng=40, duration=600):
    return {
        "id": bid,
        "category": category,
        "duration": duration,
        "range": rng,
        "class": cls,
        "totem": totem,
        "rank": rank,
    }


def ledger():
    return bl.BuffLedger({k: [dict(m) for m in v] for k, v in GROUPS.items()})


def test_place_applies_buff():
    game = ledger()
    game.place("g0", [buff("might")])
    assert game.coverage(0)["groups"]["g0"]["buffs"]


def test_same_category_only_one_survives():
    game = ledger()
    game.place("g0", [buff("might", rank=1), buff("blessing", rank=2)])
    buffs = game.coverage(0)["groups"]["g0"]["buffs"]
    assert len(buffs) == 1
    assert buffs[0]["id"] == "blessing"


def test_higher_rank_wins():
    game = ledger()
    game.place("g0", [buff("low", rank=1), buff("high", rank=3)])
    assert game.coverage(0)["groups"]["g0"]["buffs"][0]["id"] == "high"


def test_totem_slots_are_limited():
    game = ledger()
    game.place("g0", [buff(f"t{i}", category=f"c{i}", totem=True) for i in range(5)])
    with pytest.raises(ValueError):
        game.place("g0", [buff("t5", category="c5", totem=True)])


def test_refresh_extends_near_expiry():
    game = ledger()
    game.place("g0", [buff("might")])
    game.refresh(570)
    assert game.coverage(570)["groups"]["g0"]["buffs"][0]["remaining"] == 600


def test_refresh_outside_window_does_not_stack():
    game = ledger()
    game.place("g0", [buff("might")])
    game.refresh(100)
    assert game.coverage(100)["groups"]["g0"]["buffs"][0]["remaining"] == 500


def test_range_limits_coverage():
    game = ledger()
    game.place("g0", [buff("might", rng=5)])
    assert game.coverage(0)["groups"]["g0"]["covered"] == 1


def test_missing_class_uses_fallback():
    game = ledger()
    game.place("g0", [buff("mage_only", cls="druid")])
    assert game.coverage(0)["groups"]["g0"]["covered"] >= 0


def test_remove_recomputes():
    game = ledger()
    game.place("g0", [buff("might")])
    game.remove("g0", "might")
    assert game.coverage(0)["groups"]["g0"]["buffs"] == []


def test_unknown_class_is_rejected():
    game = ledger()
    with pytest.raises(ValueError):
        game.place("g0", [buff("odd", cls="ghost")])


def test_negative_time_is_rejected():
    with pytest.raises(ValueError):
        ledger().coverage(-1)


def test_recompute_is_idempotent():
    game = ledger()
    game.place("g0", [buff("might")])
    first = game.coverage(0)
    assert first["groups"]
    game.recompute(0)
    assert game.coverage(0) == first


def test_coverage_returns_copy():
    game = ledger()
    game.place("g0", [buff("might")])
    snap = game.coverage(0)
    snap["groups"].clear()
    assert game.coverage(0)["groups"]


def test_duplicate_buff_is_rejected():
    game = ledger()
    game.place("g0", [buff("might")])
    with pytest.raises(ValueError):
        game.place("g0", [buff("might")])


def test_unknown_group_is_rejected():
    with pytest.raises(ValueError):
        ledger().place("ghost", [buff("might")])
