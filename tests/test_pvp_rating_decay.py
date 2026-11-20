import pytest

import pvp_rating_decay as pr

DAY = 86400


def book():
    game = pr.RatingBook()
    game.register("alice", 0)
    game.register("bob", 0)
    return game


def test_register_adds_player():
    game = book()
    assert game.rating("alice") == 1500


def test_report_changes_ratings():
    game = book()
    game.report(["alice"], ["bob"], 0)
    assert game.rating("alice") > 1500
    assert game.rating("bob") < 1500


def test_duplicate_player_across_teams_is_rejected():
    game = book()
    with pytest.raises(ValueError):
        game.report(["alice", "bob"], ["alice"], 0)


def test_same_match_is_idempotent():
    game = book()
    game.report(["alice"], ["bob"], 0)
    after = game.rating("alice")
    assert isinstance(after, int)
    game.report(["alice"], ["bob"], 0)
    assert game.rating("alice") == after


def test_placement_games_use_larger_k():
    game = book()
    game.report(["alice"], ["bob"], 0)
    first_gain = game.rating("alice") - 1500
    fresh = book()
    for index in range(10):
        fresh.report(["alice"], ["bob"], index)
    late_gain = fresh.rating("alice") - fresh.rating("bob")
    assert late_gain >= 0


def test_higher_rated_winner_gains_less():
    low = book()
    low.report(["alice"], ["bob"], 0)
    high = book()
    high.players["alice"] = 1900
    high.report(["alice"], ["bob"], 0)
    assert high.rating("alice") - 1900 < low.rating("alice") - 1500


def test_decay_after_thirty_days():
    game = book()
    game.decay(30 * DAY)
    assert game.rating("alice") == 1475


def test_decay_is_capped():
    game = book()
    game.decay(100 * DAY)
    assert game.rating("alice") >= 1300


def test_decay_never_goes_negative():
    game = book()
    game.players["alice"] = 10
    game.decay(100 * DAY)
    assert game.rating("alice") == 0


def test_decay_is_idempotent_per_week():
    game = book()
    game.decay(30 * DAY)
    first = game.rating("alice")
    assert isinstance(first, int)
    game.decay(30 * DAY)
    assert game.rating("alice") == first


def test_unknown_player_rating_is_none():
    game = book()
    assert game.rating("alice") == 1500
    assert game.rating("ghost") is None


def test_invalid_teams_are_rejected():
    game = book()
    with pytest.raises(ValueError):
        game.report([], ["bob"], 0)
    with pytest.raises(ValueError):
        game.report(["alice"], ["bob"], -1)


def test_book_returns_copy():
    game = book()
    snap = game.book()
    snap["players"] = {}
    assert game.book()["players"]


def test_team_average_is_used():
    game = pr.RatingBook()
    for name in ("a", "b", "c", "d"):
        game.register(name, 0)
    game.report(["a", "b"], ["c", "d"], 0)
    assert game.rating("a") > 1500


def test_time_backwards_is_rejected():
    game = book()
    game.report(["alice"], ["bob"], 10)
    with pytest.raises(ValueError):
        game.report(["alice"], ["bob"], 5)
