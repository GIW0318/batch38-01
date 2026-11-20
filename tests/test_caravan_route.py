import pytest

import caravan_route as cr

ROUTE = [
    {"distance": 100.0, "risk": 0.2, "closed": False},
    {"distance": 200.0, "risk": 0.3, "closed": False},
]
CARGO = [
    {"id": "grain", "weight": 100, "value": 1000, "perishable": True},
    {"id": "ore", "weight": 200, "value": 500, "perishable": False},
]


def caravan(route=None, cargo=None, guards=2, insurance=True):
    game = cr.CaravanPlan()
    game.plan(route or ROUTE, cargo or CARGO, guards, insurance, 1)
    return game


def test_plan_sets_duration():
    assert caravan().manifest()["duration"] > 0


def test_empty_cargo_is_rejected():
    with pytest.raises(ValueError):
        cr.CaravanPlan().plan(ROUTE, [], 1, True, 1)


def test_overweight_cargo_is_rejected():
    heavy = [{"id": "rock", "weight": 600, "value": 10, "perishable": False}]
    with pytest.raises(ValueError):
        cr.CaravanPlan().plan(ROUTE, heavy, 1, True, 1)


def test_closed_leg_is_rejected():
    route = [dict(ROUTE[0], closed=True)]
    with pytest.raises(ValueError):
        cr.CaravanPlan().plan(route, CARGO, 1, True, 1)


def test_duplicate_depart_is_rejected():
    game = caravan()
    game.depart(0)
    with pytest.raises(ValueError):
        game.depart(1)


def test_early_arrival_is_rejected():
    game = caravan()
    game.depart(0)
    with pytest.raises(ValueError):
        game.arrive(10)


def test_reroute_changes_unvisited_leg():
    game = caravan()
    game.depart(0)
    game.reroute(1, {"distance": 50.0, "risk": 0.1, "closed": False}, 100)
    assert game.manifest()["duration"] > 0


def test_claim_before_arrival_is_rejected():
    game = caravan()
    game.depart(0)
    with pytest.raises(ValueError):
        game.claim(10)


def test_insurance_premium_is_five_percent():
    info = caravan(insurance=True).manifest()
    assert info["premium"] == pytest.approx(75.0)


def test_claim_is_allowed_once_after_arrival():
    game = caravan(insurance=True)
    game.depart(0)
    game.arrive(game.manifest()["duration"])
    game.claim(game.manifest()["duration"])
    assert game.manifest()["claimed"] is True
    with pytest.raises(ValueError):
        game.claim(game.manifest()["duration"] + 1)


def test_guards_reduce_risk():
    low = caravan(guards=0).manifest()["risk"]
    high = caravan(guards=4).manifest()["risk"]
    assert high < low


def test_perishable_goods_spoil_after_two_days():
    game = caravan()
    game.depart(0)
    game.arrive(49 * 3600)
    assert game.manifest()["loss"] > 0


def test_profit_formula_includes_loss_and_claim():
    info = caravan().manifest()
    expected = 1500 - 1500 - info["guard_cost"] - info["premium"] - info["loss"] + info["claim"]
    assert info["profit"] == pytest.approx(expected)


def test_negative_seed_is_rejected():
    with pytest.raises(ValueError):
        cr.CaravanPlan().plan(ROUTE, CARGO, 1, True, -1)


def test_manifest_returns_copy():
    game = caravan()
    snap = game.manifest()
    snap["loss"] = 999
    assert game.manifest()["loss"] != 999
