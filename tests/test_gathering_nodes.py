import pytest

import gathering_nodes as gn

NODES = {
    "ore": {"id": "ore", "charges": 3, "tier": 1, "respawn_at": 0},
}


def field():
    return gn.NodeField({k: dict(v) for k, v in NODES.items()})


def test_tap_reduces_charges():
    game = field()
    game.tap("ore", "alice", 1, 0)
    assert game.nodes()["ore"]["charges"] == 2


def test_same_player_cannot_tap_twice():
    game = field()
    game.tap("ore", "alice", 1, 0)
    with pytest.raises(ValueError):
        game.tap("ore", "alice", 1, 1)


def test_tool_tier_is_required():
    with pytest.raises(ValueError):
        field().tap("ore", "alice", 0, 0)


def test_depleted_node_enters_cooldown():
    game = field()
    for index in range(3):
        game.tap("ore", f"p{index}", 1, 0)
    assert game.nodes()["ore"]["cooldown"] == 300


def test_respawn_refills_depleted_node():
    game = field()
    for index in range(3):
        game.tap("ore", f"p{index}", 1, 0)
    game.respawn(301)
    assert game.nodes()["ore"]["charges"] == 3


def test_lock_reserves_node():
    game = field()
    game.lock("ore", "alice", 0)
    with pytest.raises(ValueError):
        game.tap("ore", "bob", 1, 1)


def test_lock_expires_after_thirty_seconds():
    game = field()
    game.lock("ore", "alice", 0)
    game.tap("ore", "bob", 1, 31)
    assert game.nodes()["ore"]["charges"] == 2


def test_lock_owner_can_tap():
    game = field()
    game.lock("ore", "alice", 0)
    game.tap("ore", "alice", 1, 1)
    assert game.nodes()["ore"]["charges"] == 2


def test_yield_bonus_scales_with_tool():
    game = field()
    result = game.tap("ore", "alice", 3, 0)
    assert result["yield"] == 1.2


def test_concurrent_taps_must_not_overspend():
    game = field()
    for index in range(3):
        game.tap("ore", f"p{index}", 1, 0)
    with pytest.raises(ValueError):
        game.tap("ore", "p4", 1, 0)


def test_unknown_node_is_rejected():
    with pytest.raises(ValueError):
        field().tap("ghost", "alice", 1, 0)


def test_time_backwards_is_rejected():
    game = field()
    game.tap("ore", "alice", 1, 10)
    with pytest.raises(ValueError):
        game.respawn(5)


def test_nodes_returns_copy():
    game = field()
    snap = game.nodes()
    snap["ore"]["charges"] = 99
    assert game.nodes()["ore"]["charges"] == 3


def test_charges_are_reported():
    game = field()
    game.tap("ore", "alice", 1, 0)
    assert game.nodes()["ore"]["charges"] == 2


def test_cooldown_remaining_is_reported():
    game = field()
    for index in range(3):
        game.tap("ore", f"p{index}", 1, 0)
    assert game.nodes()["ore"]["cooldown"] == 300
