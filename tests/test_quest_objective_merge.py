import pytest

import quest_objective_merge as qm

QUESTS = {
    "q1": {
        "id": "q1",
        "stages": [
            {"objectives": [{"id": "kill_wolf", "type": "kill", "count": 3, "tag": "wolf"}]},
            {"objectives": [{"id": "collect_herb", "type": "collect", "count": 2}]},
        ],
    }
}


def merge():
    return qm.ObjectiveMerge(QUESTS)


def test_kill_credit_counts():
    game = merge()
    game.credit("q1", "kill_wolf", "alice", 1, 0)
    assert game.progress()["alice"]["q1"]["kill_wolf"] == 1


def test_count_is_capped():
    game = merge()
    game.credit("q1", "kill_wolf", "alice", 5, 0)
    assert game.progress()["alice"]["q1"]["kill_wolf"] == 3


def test_zero_amount_is_rejected():
    with pytest.raises(ValueError):
        merge().credit("q1", "kill_wolf", "alice", 0, 0)


def test_negative_amount_is_rejected():
    with pytest.raises(ValueError):
        merge().credit("q1", "kill_wolf", "alice", -1, 0)


def test_unknown_quest_is_rejected():
    with pytest.raises(ValueError):
        merge().credit("ghost", "kill_wolf", "alice", 1, 0)


def test_unknown_objective_is_rejected():
    with pytest.raises(ValueError):
        merge().credit("q1", "ghost", "alice", 1, 0)


def test_second_stage_is_locked():
    game = merge()
    with pytest.raises(ValueError):
        game.credit("q1", "collect_herb", "alice", 1, 0)


def test_stage_advances_after_completion():
    game = merge()
    game.credit("q1", "kill_wolf", "alice", 3, 0)
    game.credit("q1", "collect_herb", "alice", 1, 1)
    assert game.progress()["alice"]["q1"]["collect_herb"] == 1


def test_players_have_separate_progress():
    game = merge()
    game.credit("q1", "kill_wolf", "alice", 1, 0)
    game.credit("q1", "kill_wolf", "bob", 2, 0)
    assert game.progress()["alice"]["q1"]["kill_wolf"] == 1
    assert game.progress()["bob"]["q1"]["kill_wolf"] == 2


def test_progress_reports_stage_index():
    game = merge()
    game.credit("q1", "kill_wolf", "alice", 3, 0)
    assert game.progress()["alice"]["q1"]["stage"] == 1


def test_collect_objective_accepts_credit():
    game = merge()
    game.credit("q1", "kill_wolf", "alice", 3, 0)
    game.credit("q1", "collect_herb", "alice", 2, 1)
    assert game.progress()["alice"]["q1"]["collect_herb"] == 2


def test_progress_returns_copy():
    game = merge()
    game.credit("q1", "kill_wolf", "alice", 1, 0)
    snap = game.progress()
    snap["alice"]["q1"]["kill_wolf"] = 99
    assert game.progress()["alice"]["q1"]["kill_wolf"] == 1


def test_interact_objective_is_supported():
    quests = {"q2": {"id": "q2", "stages": [{"objectives": [{"id": "use", "type": "interact", "count": 1}]}]}}
    game = qm.ObjectiveMerge(quests)
    game.credit("q2", "use", "alice", 1, 0)
    assert game.progress()["alice"]["q2"]["use"] == 1


def test_unknown_type_is_rejected():
    quests = {"q3": {"id": "q3", "stages": [{"objectives": [{"id": "odd", "type": "magic", "count": 1}]}]}}
    game = qm.ObjectiveMerge(quests)
    with pytest.raises(ValueError):
        game.credit("q3", "odd", "alice", 1, 0)


def test_negative_time_is_rejected():
    with pytest.raises(ValueError):
        merge().credit("q1", "kill_wolf", "alice", 1, -1)
