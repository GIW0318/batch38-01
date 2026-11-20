import pytest

import slow_request_budget as sb


def budget(**over):
    return sb.RequestBudget(**over)


def opened(game, conn="c1", ip="10.0.0.1", ts=0):
    assert game.open(conn, ip, ts)["ok"] is True
    return game


def test_open_accepts_new_connection():
    result = budget().open("c1", "10.0.0.1", 0)
    assert result["ok"] is True


def test_duplicate_open_is_rejected():
    game = opened(budget())
    with pytest.raises(ValueError):
        game.open("c1", "10.0.0.1", 1)


def test_header_size_limit():
    game = opened(budget())
    result = game.recv_headers("c1", 16385, 1)
    assert result["ok"] is False
    assert result["reason"] == "header_too_large"


def test_header_deadline():
    game = opened(budget())
    result = game.recv_headers("c1", 100, 11)
    assert result["ok"] is False
    assert result["reason"] == "header_timeout"


def test_header_inside_deadline_is_ok():
    game = opened(budget())
    assert game.recv_headers("c1", 1000, 2)["ok"] is True


def test_body_grace_period_is_allowed():
    game = opened(budget())
    game.recv_headers("c1", 100, 1)
    assert game.recv_body("c1", 1, 2)["ok"] is True


def test_body_below_minimum_rate_is_rejected():
    game = opened(budget())
    game.recv_headers("c1", 100, 1)
    game.recv_body("c1", 1, 2)
    result = game.recv_body("c1", 1, 20)
    assert result["ok"] is False
    assert result["reason"] == "body_too_slow"


def test_body_total_limit():
    game = opened(budget())
    game.recv_headers("c1", 100, 1)
    game.recv_body("c1", 1024 * 1024 + 1, 2)
    result = game.recv_body("c1", 1024 * 1024 + 1, 2)
    assert result["ok"] is False
    assert result["reason"] == "body_too_large"


def test_idle_connection_is_reclaimed():
    game = opened(budget())
    result = game.recv_headers("c1", 100, 31)
    assert result["ok"] is False
    assert result["reason"] == "idle_timeout"


def test_per_ip_limit():
    game = budget(max_per_ip=2)
    opened(game, "c1", "10.0.0.1")
    opened(game, "c2", "10.0.0.1")
    with pytest.raises(ValueError):
        game.open("c3", "10.0.0.1", 0)


def test_global_limit():
    game = budget(max_total=2)
    opened(game, "c1", "10.0.0.1")
    opened(game, "c2", "10.0.0.2")
    with pytest.raises(ValueError):
        game.open("c3", "10.0.0.3", 0)


def test_finish_decrements_active_count():
    game = opened(budget())
    game.finish("c1", 1)
    assert game.profile()["connections"] == 0


def test_finish_unknown_connection_is_rejected():
    with pytest.raises(ValueError):
        budget().finish("ghost", 0)


def test_time_backwards_and_unknown_connection_are_rejected():
    game = opened(budget())
    with pytest.raises(ValueError):
        game.recv_headers("c1", 10, -1)
    with pytest.raises(ValueError):
        game.recv_headers("ghost", 10, 1)


def test_profile_counts_reasons_and_returns_copy():
    game = opened(budget())
    game.recv_headers("c1", 16385, 1)
    info = game.profile()
    assert info["connections"] == 1
    assert info["reasons"]["header_too_large"] == 1
    info["reasons"].clear()
    assert game.profile()["reasons"]["header_too_large"] == 1
