import pytest

import crafting_quality as cq

RECIPES = {
    "sword": {
        "base": 50,
        "materials": {"metal": 2, "wood": 1},
        "substitutes": {"metal": {"iron": 0.8, "steel": 1.0}},
    },
}
MATQ = {"iron": 80, "steel": 80, "oak": 60}


def bench():
    return cq.CraftBench(RECIPES, MATQ, skill=1.0)


def slot(metal="iron", wood="oak", bound=False):
    return {"materials": {"metal": [metal, metal], "wood": [wood]}, "bound": bound}


def test_single_craft_quality_and_quantity():
    items = bench().craft_batch("sword", [slot()], 1, 0)
    assert len(items) == 1
    assert items[0]["quality"] == 80
    assert items[0]["qty"] == 1


def test_same_seed_is_deterministic():
    first = bench().craft_batch("sword", [slot()], 7, 0)
    second = bench().craft_batch("sword", [slot()], 7, 10)
    assert first[0]["quality"] == second[0]["quality"]


def test_roll_twenty_crits_for_double_output():
    items = bench().craft_batch("sword", [slot()], 20, 0)
    assert items[0]["qty"] == 2


def test_batch_is_atomic_on_invalid_slot():
    game = bench()
    with pytest.raises(ValueError):
        game.craft_batch("sword", [slot(), {"materials": {"metal": ["iron", "iron"]}}], 1, 0)
    assert game.ledger()["batches"] == 0


def test_unknown_recipe_is_rejected():
    with pytest.raises(ValueError):
        bench().craft_batch("ghost", [slot()], 1, 0)


def test_missing_material_is_rejected():
    with pytest.raises(ValueError):
        bench().craft_batch("sword", [{"materials": {"metal": ["iron"]}}], 1, 0)


def test_extra_material_is_rejected():
    bad = {"materials": {"metal": ["iron", "iron", "iron"], "wood": ["oak"]}}
    with pytest.raises(ValueError):
        bench().craft_batch("sword", [bad], 1, 0)


def test_substitute_lowers_quality():
    iron = bench().craft_batch("sword", [slot("iron")], 1, 0)
    steel = bench().craft_batch("sword", [slot("steel")], 1, 0)
    assert steel[0]["quality"] > iron[0]["quality"]


def test_item_ids_are_unique():
    items = bench().craft_batch("sword", [slot(), slot()], 3, 0)
    assert len({x["id"] for x in items}) == 2


def test_salvage_returns_half_materials():
    game = bench()
    item = game.craft_batch("sword", [slot()], 1, 0)[0]
    returned = game.salvage(item["id"], 10)
    assert returned == {"iron": 1}


def test_bound_item_cannot_be_salvaged():
    game = bench()
    item = game.craft_batch("sword", [slot(bound=True)], 1, 0)[0]
    with pytest.raises(ValueError):
        game.salvage(item["id"], 10)


def test_unknown_item_cannot_be_salvaged():
    with pytest.raises(ValueError):
        bench().salvage("ghost", 10)


def test_quote_reports_material_gaps():
    info = bench().quote("sword", [{"materials": {"metal": ["iron"]}}])
    assert info["gaps"]["metal"] == 1


def test_ledger_returns_copy():
    game = bench()
    game.craft_batch("sword", [slot()], 1, 0)
    snap = game.ledger()
    snap["batches"] = 99
    assert game.ledger()["batches"] == 1


def test_negative_seed_is_rejected():
    with pytest.raises(ValueError):
        bench().craft_batch("sword", [slot()], -1, 0)
