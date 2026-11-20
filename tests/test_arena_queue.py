import pytest

import arena_queue as aq


def team(tid="t1", rating=1500, roles=("tank", "healer", "dps")):
    return {
        "id": tid,
        "rating": rating,
        "players": [{"name": f"{tid}-{index}", "role": role} for index, role in enumerate(roles)],
    }


def queue():
    return aq.ArenaQueue()


def test_enqueue_accepts_team():
    game = queue()
    game.enqueue(team(), 0)
    assert game.queues()["waiting"] == 1


def test_duplicate_team_id_is_rejected():
    game = queue()
    game.enqueue(team(), 0)
    with pytest.raises(ValueError):
        game.enqueue(team(), 1)


def test_empty_team_is_rejected():
    with pytest.raises(ValueError):
        queue().enqueue({"id": "t", "rating": 1500, "players": []}, 0)


def test_duplicate_players_are_rejected():
    bad = {"id": "t", "rating": 1500, "players": [{"name": "a", "role": "dps"}, {"name": "a", "role": "tank"}]}
    with pytest.raises(ValueError):
        queue().enqueue(bad, 0)


def test_cancel_removes_team():
    game = queue()
    game.enqueue(team(), 0)
    game.cancel("t1", 1)
    assert game.queues()["waiting"] == 0


def test_unknown_cancel_is_rejected():
    with pytest.raises(ValueError):
        queue().cancel("ghost", 0)


def test_rating_range_starts_at_one_hundred():
    game = queue()
    game.enqueue(team("a", 1500), 0)
    game.enqueue(team("b", 1650), 10)
    assert game.queues()["waiting"] == 2
    assert game.match(10) is None


def test_range_widens_over_time():
    game = queue()
    game.enqueue(team("a", 1500), 0)
    game.enqueue(team("b", 1650), 0)
    assert game.match(60) is not None


def test_range_caps_at_five_hundred():
    game = queue()
    game.enqueue(team("a", 1000), 0)
    game.enqueue(team("b", 1600), 0)
    assert game.queues()["waiting"] == 2
    assert game.match(1000) is None


def test_premade_only_matches_premade():
    game = queue()
    game.enqueue(team("a", 1500, ("tank", "healer", "dps")), 0)
    game.enqueue(team("b", 1500, ("dps",)), 0)
    assert game.queues()["waiting"] == 2
    assert game.match(60) is None


def test_match_returns_pair_and_removes_them():
    game = queue()
    game.enqueue(team("a", 1500), 0)
    game.enqueue(team("b", 1510), 0)
    result = game.match(60)
    assert result["teams"][0]["id"] in {"a", "b"}
    assert game.queues()["waiting"] == 0


def test_no_match_returns_none():
    game = queue()
    assert game.queues()["waiting"] == 0
    assert game.match(0) is None


def test_role_composition_prefers_matching_teams():
    game = queue()
    game.enqueue(team("a", 1500, ("tank", "healer", "dps")), 0)
    game.enqueue(team("b", 1500, ("dps", "dps", "dps")), 0)
    game.enqueue(team("c", 1500, ("tank", "healer", "dps")), 0)
    result = game.match(60)
    assert {x["id"] for x in result["teams"]} == {"a", "c"}


def test_waiting_over_three_hundred_seconds_is_prioritized():
    game = queue()
    game.enqueue(team("old", 1500), 0)
    game.enqueue(team("new", 1500), 350)
    game.enqueue(team("peer", 1500), 350)
    result = game.match(360)
    assert "old" in {x["id"] for x in result["teams"]}


def test_queues_returns_copy():
    game = queue()
    game.enqueue(team(), 0)
    snap = game.queues()
    snap["waiting"] = 99
    assert game.queues()["waiting"] == 1
