import pytest

import fishing_conditions as fc

SPOTS = {
    "lake": {"weather": "sunny", "season": "spring", "hour": 7, "depth": 2},
}

FISH = [
    {"id": "trash", "rarity": "common", "base": 100, "seasons": ["spring"], "hours": [0, 24], "difficulty": 1},
    {"id": "rare", "rarity": "rare", "base": 10, "seasons": ["spring"], "hours": [6, 18], "difficulty": 5},
]

MULT = {
    "weather": {"sunny": {"trash": 2.0, "rare": 0.5}},
    "bait": {"worm": {"trash": 0.5, "rare": 2.0}},
    "depth": {2: {"trash": 1.0, "rare": 1.0}},
}


def pond(fish=None, multipliers=None, king_limit=1):
    return fc.FishingSpot(SPOTS, fish or FISH, multipliers or MULT, king_limit)


def catch(pond_obj, player, now, bait="worm", rod=10, seed=1):
    cast_id = pond_obj.cast(player, "lake", bait, rod, now)
    return pond_obj.resolve(cast_id, seed)


def test_cast_returns_id_and_counts():
    lake = pond()
    cast_id = lake.cast("alice", "lake", "worm", 10, 0)
    assert cast_id == 1
    assert lake.snapshot()["casts"] == 1


def test_weights_apply_all_multipliers():
    weights = pond().weights("lake", "worm")
    assert weights["trash"] == pytest.approx(100.0)
    assert weights["rare"] == pytest.approx(10.0)


def test_rare_fish_out_of_season_has_zero_weight():
    fish = [dict(FISH[0]), dict(FISH[1], seasons=["winter"])]
    assert pond(fish=fish).weights("lake", "worm")["rare"] == 0


def test_rare_fish_outside_hours_has_zero_weight():
    fish = [dict(FISH[0]), dict(FISH[1], hours=[20, 22])]
    assert pond(fish=fish).weights("lake", "worm")["rare"] == 0


def test_resolve_is_deterministic_for_same_seed():
    lake = pond()
    first = catch(lake, "alice", 0, seed=7)
    second = catch(lake, "bob", 0, seed=7)
    assert first["fish"] == second["fish"]


def test_rare_fish_never_appears_out_of_season():
    fish = [dict(FISH[0]), dict(FISH[1], seasons=["winter"])]
    lake = pond(fish=fish)
    for index in range(20):
        result = catch(lake, f"p{index}", index * 30, seed=index)
        assert result["fish"] != "rare"


def test_pity_forces_rare_after_ten_common_catches():
    fish = [dict(FISH[0]), dict(FISH[1], base=0)]
    lake = pond(fish=fish)
    for index in range(10):
        result = catch(lake, "alice", index * 30, seed=index)
        assert result["fish"] == "trash"
    assert lake.snapshot()["pity"] == 10
    forced = catch(lake, "alice", 300, seed=99)
    assert forced["fish"] == "rare"


def test_pity_resets_after_rare_catch():
    fish = [dict(FISH[0]), dict(FISH[1], base=0)]
    lake = pond(fish=fish)
    for index in range(11):
        catch(lake, "alice", index * 30, seed=index)
    assert lake.snapshot()["pity"] == 0
    after = catch(lake, "alice", 330, seed=5)
    assert after["fish"] == "trash"
    assert lake.snapshot()["pity"] == 1


def test_rod_changes_escape_not_species():
    lake = pond()
    weak = catch(lake, "alice", 0, rod=1, seed=2)
    strong = catch(lake, "bob", 0, rod=10, seed=2)
    assert weak["fish"] == strong["fish"]
    assert weak["escaped"] is True
    assert strong["escaped"] is False


def test_same_spot_cooldown_is_enforced():
    lake = pond()
    lake.cast("alice", "lake", "worm", 10, 0)
    with pytest.raises(ValueError):
        lake.cast("alice", "lake", "worm", 10, 10)


def test_cooldown_expires_after_thirty_seconds():
    lake = pond()
    lake.cast("alice", "lake", "worm", 10, 0)
    assert lake.cast("alice", "lake", "worm", 10, 30) == 2


def test_unknown_bait_is_rejected():
    with pytest.raises(ValueError):
        pond().cast("alice", "lake", "bomb", 10, 0)


def test_invalid_weather_is_rejected():
    bad = {"lake": {"weather": "acid", "season": "spring", "hour": 7, "depth": 2}}
    lake = fc.FishingSpot(bad, FISH, MULT)
    with pytest.raises(ValueError):
        lake.cast("alice", "lake", "worm", 10, 0)


def test_king_fish_is_limited_per_day():
    king = [{"id": "king", "rarity": "king", "base": 100, "seasons": ["spring"], "hours": [0, 24], "difficulty": 1}]
    lake = pond(fish=king, multipliers=MULT, king_limit=1)
    first = catch(lake, "alice", 0, seed=1)
    second = catch(lake, "bob", 10, seed=1)
    third = catch(lake, "carol", 86400, seed=1)
    assert first["fish"] == "king"
    assert second["fish"] is None
    assert third["fish"] == "king"


def test_snapshot_reports_catches_and_pity():
    lake = pond()
    catch(lake, "alice", 0, seed=1)
    catch(lake, "bob", 0, seed=2)
    info = lake.snapshot()
    assert info["catches"]["trash"] == 2
    assert info["pity"] == 2
