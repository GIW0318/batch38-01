import pytest

import keystone_ledger as kl

PARTY = ["alice", "bob", "carol"]
ROUTE = ["start", "mid", "boss"]


def run(level=10, affixes=None, route=None):
    game = kl.KeystoneRun()
    game.start(level, list(PARTY), affixes or [], list(route or ROUTE), 0)
    return game


def test_start_sets_duration():
    game = run(level=10)
    assert game.ledger()["duration"] == 2100


def test_duplicate_start_is_rejected():
    game = run()
    with pytest.raises(ValueError):
        game.start(10, list(PARTY), [], list(ROUTE), 1)


def test_invalid_level_and_party_are_rejected():
    with pytest.raises(ValueError):
        kl.KeystoneRun().start(99, list(PARTY), [], list(ROUTE), 0)
    with pytest.raises(ValueError):
        kl.KeystoneRun().start(10, [], [], list(ROUTE), 0)


def test_checkpoints_must_follow_route():
    game = run()
    with pytest.raises(ValueError):
        game.checkpoint("boss", 10)
    assert game.checkpoint("start", 10)["remaining"] > 0


def test_checkpoint_grants_fifteen_seconds_once():
    game = run()
    first = game.checkpoint("start", 10)
    second = game.checkpoint("start", 20)
    assert first["remaining"] == 2100 - 10 + 15
    assert second["remaining"] == first["remaining"] - 10


def test_death_penalty_escalates():
    game = run()
    game.death("alice", 10)
    game.death("bob", 20)
    info = game.ledger()
    assert info["deaths"] == 2
    assert info["penalty"] == 15


def test_five_deaths_deplete_run():
    game = run()
    for index in range(5):
        game.death(PARTY[index % 3], index * 10)
    assert game.ledger()["status"] == "depleted"


def test_affixes_add_time_without_stacking():
    game = run(affixes=["bloodlust", "bloodlust", "fortified"])
    assert game.ledger()["duration"] == 2100 + 120 + 60


def test_pause_only_at_checkpoint_and_limited():
    game = run()
    with pytest.raises(ValueError):
        game.pause(10)
    game.checkpoint("start", 0)
    game.pause(10)
    with pytest.raises(ValueError):
        game.pause(20)


def test_resume_extends_deadline():
    game = run()
    game.checkpoint("start", 0)
    game.pause(100)
    game.resume(150)
    assert game.ledger()["remaining"] == 2100 + 50


def test_swap_only_while_paused_and_rejects_duplicates():
    game = run()
    game.checkpoint("start", 0)
    with pytest.raises(ValueError):
        game.swap("alice", "dave", 10)
    game.pause(10)
    with pytest.raises(ValueError):
        game.swap("alice", "bob", 20)
    game.swap("alice", "dave", 20)
    assert "dave" in game.ledger()["party"]


def test_finish_upgrades_two_when_remaining_high():
    game = run(level=10)
    result = game.finish(100)
    assert result["status"] == "success"
    assert result["upgrade"] == 2


def test_finish_upgrades_one_or_depletes():
    game = run(level=10)
    game.death("alice", 0)
    game.death("bob", 0)
    game.death("carol", 0)
    game.death("alice", 0)
    result = game.finish(1500)
    assert result["status"] == "success"
    assert result["upgrade"] == 1


def test_finish_after_deadline_is_depleted():
    game = run(level=10)
    result = game.finish(2200)
    assert result["status"] == "depleted"


def test_ledger_returns_copy_and_member_rows():
    game = run()
    game.death("alice", 0)
    snap = game.ledger()
    assert len(snap["members"]) == 3
    snap["deaths"] = 99
    assert game.ledger()["deaths"] == 1
