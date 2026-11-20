import pytest

import damage_pipeline as dp


def target(hp=1000, armor=0, resist=None, invuln_until=0):
    return {"hp": hp, "armor": armor, "resist": dict(resist or {}), "invuln_until": invuln_until}


def game(targets=None):
    return dp.DamagePipeline(targets or {"t1": target(), "t2": target()})


def test_armor_reduces_damage():
    data = {"t1": target(armor=100)}
    dp.DamagePipeline(data).hit("t1", 100, "physical")
    assert data["t1"]["hp"] == 950


def test_resistance_is_capped():
    data = {"t1": target(resist={"fire": 2.0})}
    dp.DamagePipeline(data).hit("t1", 100, "fire")
    assert data["t1"]["hp"] == 970


def test_shield_absorbs_matching_type():
    data = {"t1": target()}
    pipe = dp.DamagePipeline(data)
    pipe.shield("t1", 30, 10, "fire", 1)
    pipe.hit("t1", 100, "fire")
    assert data["t1"]["hp"] == 930


def test_shield_does_not_absorb_other_type():
    data = {"t1": target()}
    pipe = dp.DamagePipeline(data)
    pipe.shield("t1", 30, 10, "fire", 1)
    pipe.hit("t1", 100, "physical")
    assert data["t1"]["hp"] == 900


def test_shields_use_priority_order():
    data = {"t1": target()}
    pipe = dp.DamagePipeline(data)
    pipe.shield("t1", 10, 10, "fire", 1)
    pipe.shield("t1", 20, 10, "fire", 2)
    pipe.hit("t1", 25, "fire")
    assert data["t1"]["hp"] == 990


def test_redirect_is_capped_at_half():
    data = {"t1": target(), "t2": target()}
    pipe = dp.DamagePipeline(data)
    pipe.redirect("t1", "t2", 0.8, 10)
    pipe.hit("t1", 100, "physical")
    assert data["t1"]["hp"] == 950


def test_redirect_chain_is_rejected():
    data = {"t1": target(), "t2": target(), "t3": target()}
    pipe = dp.DamagePipeline(data)
    pipe.redirect("t1", "t2", 0.3, 10)
    with pytest.raises(ValueError):
        pipe.redirect("t2", "t3", 0.3, 10)


def test_dot_snapshots_mitigation_at_application():
    data = {"t1": target(armor=100)}
    pipe = dp.DamagePipeline(data)
    pipe.dot("t1", 10, "physical", 3, 1, 0)
    data["t1"]["armor"] = 0
    pipe.tick(1)
    assert data["t1"]["hp"] == 995


def test_invulnerability_blocks_direct_damage():
    data = {"t1": target(invuln_until=5)}
    pipe = dp.DamagePipeline(data)
    result = pipe.hit("t1", 100, "physical")
    assert result["blocked"] is True
    assert data["t1"]["hp"] == 1000


def test_invulnerability_does_not_block_existing_dot():
    data = {"t1": target(invuln_until=0)}
    pipe = dp.DamagePipeline(data)
    pipe.dot("t1", 10, "fire", 1, 1, 0)
    data["t1"]["invuln_until"] = 10
    pipe.tick(1)
    assert data["t1"]["hp"] == 990


def test_overkill_is_clamped_and_counted():
    data = {"t1": target(hp=50)}
    pipe = dp.DamagePipeline(data)
    result = pipe.hit("t1", 100, "physical")
    assert data["t1"]["hp"] == 0
    assert result["overkill"] == 50


def test_negative_and_zero_damage_are_rejected():
    pipe = game()
    with pytest.raises(ValueError):
        pipe.hit("t1", -1, "physical")
    with pytest.raises(ValueError):
        pipe.hit("t1", 0, "physical")


def test_unknown_dtype_is_rejected():
    with pytest.raises(ValueError):
        game().hit("t1", 1, "holy")


def test_expired_shield_is_removed():
    data = {"t1": target()}
    pipe = dp.DamagePipeline(data)
    pipe.shield("t1", 30, 5, "fire", 1)
    pipe.tick(6)
    pipe.hit("t1", 100, "fire")
    assert data["t1"]["hp"] == 900


def test_snapshot_returns_copy():
    data = {"t1": target()}
    pipe = dp.DamagePipeline(data)
    pipe.shield("t1", 10, 10, "fire", 1)
    snap = pipe.snapshot("t1")
    snap["shields"].clear()
    assert pipe.snapshot("t1")["shields"]
