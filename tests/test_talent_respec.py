import pytest

import talent_respec as tr

TREE = [
    {"id": "t1a", "tier": 1, "max_rank": 3, "requires": []},
    {"id": "t1b", "tier": 1, "max_rank": 2, "requires": []},
    {"id": "t2a", "tier": 2, "max_rank": 2, "requires": ["t1a"]},
    {"id": "t3a", "tier": 3, "max_rank": 1, "requires": ["t2a"]},
]
DAY = 86400


def grid():
    return tr.TalentGrid(list(TREE))


def test_spend_adds_points():
    game = grid()
    game.spend("a", "t1a", 2)
    assert game.view("a")["spent"] == 2


def test_tier_gate_requires_five_points():
    game = grid()
    with pytest.raises(ValueError):
        game.spend("a", "t2a", 1)


def test_client_max_rank_is_enforced():
    game = grid()
    with pytest.raises(ValueError):
        game.spend("a", "t1a", 4)


def test_prerequisite_must_be_maxed():
    game = grid()
    game.spend("a", "t1a", 2)
    game.spend("a", "t1b", 2)
    with pytest.raises(ValueError):
        game.spend("a", "t2a", 1)


def test_gear_bonus_raises_cap_without_spending():
    game = grid()
    game.set_gear_bonus(10)
    info = game.view("a")
    assert info["cap"] == 61
    assert info["spent"] == 0


def test_specs_are_independent():
    game = grid()
    game.spend("a", "t1a", 3)
    assert game.view("a")["spent"] == 3
    assert game.view("b")["spent"] == 0


def test_respec_refunds_all_points():
    game = grid()
    game.spend("a", "t1a", 3)
    game.spend("a", "t1b", 2)
    game.respec("a", 0, free=True)
    assert game.view("a")["spent"] == 0


def test_respec_cost_is_fifty_per_point():
    game = grid()
    game.spend("a", "t1a", 2)
    assert game.respec("a", 0) == 100


def test_free_window_only_once_per_thirty_days():
    game = grid()
    game.spend("a", "t1a", 1)
    assert game.respec("a", 0, free=True) == 0
    game.spend("a", "t1a", 1)
    with pytest.raises(ValueError):
        game.respec("a", DAY, free=True)
    game.spend("a", "t1a", 1)
    assert game.respec("a", 30 * DAY, free=True) == 0


def test_combat_blocks_respec_and_load():
    game = grid()
    game.spend("a", "t1a", 1)
    game.save_build("pvp", "a")
    game.set_combat(True)
    with pytest.raises(ValueError):
        game.respec("a", 0)
    with pytest.raises(ValueError):
        game.load_build("pvp")


def test_save_and_load_roundtrip():
    game = grid()
    game.spend("a", "t1a", 2)
    game.save_build("pvp", "a")
    game.respec("a", 0, free=True)
    game.load_build("pvp")
    assert game.view("a")["spent"] == 2


def test_load_failure_keeps_current_state():
    game = grid()
    game.spend("a", "t1a", 1)
    with pytest.raises(ValueError):
        game.load_build("ghost")
    assert game.view("a")["spent"] == 1


def test_unknown_spec_and_node_are_rejected():
    game = grid()
    with pytest.raises(ValueError):
        game.spend("x", "t1a", 1)
    with pytest.raises(ValueError):
        game.spend("a", "ghost", 1)


def test_view_returns_copy():
    game = grid()
    game.spend("a", "t1a", 1)
    snap = game.view("a")
    snap["spent"] = 99
    assert game.view("a")["spent"] == 1


def test_negative_points_are_rejected():
    with pytest.raises(ValueError):
        grid().spend("a", "t1a", -1)
