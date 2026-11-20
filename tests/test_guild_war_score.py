import pytest

import guild_war_score as gw


def nodes():
    return [
        {"id": "n1", "points": 10, "owner": None},
        {"id": "n2", "points": 10, "owner": None},
    ]


def war(duration=1800):
    return gw.WarLedger(nodes(), duration=duration)


def test_first_capture_sets_owner_and_bonus():
    game = war()
    game.capture("n1", "red", 0)
    assert game.standings()["scores"]["red"] == 50


def test_same_guild_recapture_does_not_pay_bonus():
    game = war()
    game.capture("n1", "red", 0)
    game.capture("n1", "red", 10)
    assert game.standings()["scores"]["red"] == 50


def test_flip_capture_changes_owner_without_bonus():
    game = war()
    game.capture("n1", "red", 0)
    game.capture("n1", "blue", 10)
    assert game.standings()["nodes"]["blue"] == 1
    assert game.standings()["scores"]["blue"] == 0


def test_tick_awards_points_per_minute():
    game = war()
    game.capture("n1", "red", 0)
    game.tick(60)
    assert game.standings()["scores"]["red"] == 60


def test_tick_is_idempotent_for_same_minute():
    game = war()
    game.capture("n1", "red", 0)
    game.tick(60)
    game.tick(60)
    assert game.standings()["scores"]["red"] == 60


def test_last_ten_minutes_are_doubled():
    game = war(duration=1200)
    game.capture("n1", "red", 0)
    game.tick(660)
    assert game.standings()["scores"]["red"] == 170


def test_surrender_stops_future_ticks():
    game = war()
    game.capture("n1", "red", 0)
    game.tick(60)
    game.surrender("red", 70)
    game.tick(180)
    assert game.standings()["scores"]["red"] == 60
    assert game.standings()["ended"] is True


def test_winner_is_highest_score():
    game = war()
    game.capture("n1", "red", 0)
    game.capture("n2", "red", 0)
    game.tick(120)
    assert game.standings()["winner"] == "red"


def test_tie_breaks_by_node_count():
    game = war()
    game.capture("n1", "red", 0)
    game.capture("n2", "blue", 0)
    game.capture("n1", "blue", 10)
    game.surrender("red", 20)
    assert game.standings()["winner"] == "blue"


def test_tie_breaks_by_earliest_capture():
    game = war()
    game.capture("n1", "red", 0)
    game.capture("n2", "blue", 10)
    game.surrender("red", 20)
    assert game.standings()["winner"] == "red"


def test_unknown_node_is_rejected():
    with pytest.raises(ValueError):
        war().capture("ghost", "red", 0)


def test_empty_guild_is_rejected():
    with pytest.raises(ValueError):
        war().capture("n1", "", 0)


def test_negative_and_reversed_time_are_rejected():
    game = war()
    game.capture("n1", "red", 10)
    with pytest.raises(ValueError):
        game.tick(-1)
    with pytest.raises(ValueError):
        game.capture("n2", "blue", 5)


def test_standings_returns_copy():
    game = war()
    game.capture("n1", "red", 0)
    snap = game.standings()
    snap["scores"]["red"] = 999
    assert game.standings()["scores"]["red"] == 50


def test_standings_reports_remaining_and_end_flag():
    game = war(duration=1800)
    game.capture("n1", "red", 0)
    game.tick(60)
    info = game.standings()
    assert info["remaining"] == 1740
    assert info["ended"] is False
