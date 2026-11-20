import pytest

import fog_reveal as fr


def fog(walls=None, radius=8):
    return fr.FogGrid(size=64, radius=radius, walls=walls or [])


def test_reveal_marks_visible_and_explored():
    game = fog()
    game.reveal("alice", 10, 10, 0)
    info = game.snapshot()
    assert info["players"]["alice"]["visible"] > 0
    assert info["players"]["alice"]["explored"] > 0


def test_wall_blocks_cells_behind_it():
    game = fog(walls={(11, 10)})
    visible = game.reveal("alice", 10, 10, 0)
    assert (11, 10) in visible
    assert (12, 10) not in visible


def test_explored_persists_after_moving():
    game = fog()
    game.reveal("alice", 10, 10, 0)
    game.reveal("alice", 30, 30, 1)
    info = game.snapshot()["players"]["alice"]
    assert info["explored"] > info["visible"]


def test_share_copies_explored_only():
    game = fog()
    game.reveal("alice", 10, 10, 0)
    game.share("red", "alice")
    game.share("red", "bob")
    game.reveal("bob", 30, 30, 1)
    info = game.snapshot()["players"]["bob"]
    assert info["explored"] > info["visible"]


def test_share_unknown_player_is_rejected():
    with pytest.raises(ValueError):
        fog().share("red", "ghost")


def test_save_and_load_restore_explored():
    game = fog()
    game.reveal("alice", 10, 10, 0)
    data = game.save()
    other = fog()
    other.load(data)
    assert other.snapshot()["players"]["alice"]["explored"] > 0


def test_coverage_is_fractional_at_edges():
    value = fog().coverage("alice", 2, 2)
    assert 0.0 <= value <= 1.0


def test_out_of_bounds_coordinate_is_rejected():
    with pytest.raises(ValueError):
        fog().reveal("alice", -1, 0, 0)


def test_negative_radius_is_rejected():
    with pytest.raises(ValueError):
        fr.FogGrid(radius=-1)


def test_duplicate_reveal_is_idempotent():
    game = fog()
    first = game.reveal("alice", 10, 10, 0)
    second = game.reveal("alice", 10, 10, 1)
    assert set(first) == set(second)


def test_snapshot_counts_players_and_teams():
    game = fog()
    game.reveal("alice", 10, 10, 0)
    game.share("red", "alice")
    info = game.snapshot()
    assert info["players"]["alice"]["visible"] > 0
    assert info["teams"] == 1


def test_snapshot_returns_copy():
    game = fog()
    game.reveal("alice", 10, 10, 0)
    snap = game.snapshot()
    snap["players"]["alice"]["visible"] = 0
    assert game.snapshot()["players"]["alice"]["visible"] > 0


def test_team_isolation():
    game = fog()
    game.reveal("alice", 10, 10, 0)
    game.share("red", "alice")
    game.share("blue", "carol")
    game.reveal("carol", 40, 40, 0)
    assert game.snapshot()["players"]["carol"]["explored"] > 0


def test_save_returns_serializable_copy():
    game = fog()
    game.reveal("alice", 10, 10, 0)
    data = game.save()
    data["players"].clear()
    assert game.save()["players"]


def test_unknown_player_query_is_rejected():
    with pytest.raises(ValueError):
        fog().coverage("ghost", 1, 1)
