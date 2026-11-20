import pytest

import bounty_board as bb


def contract(cid="c1", poster="alice", min_level=1, max_claims=2, expires_at=1000, reward=100):
    return {
        "id": cid,
        "poster": poster,
        "target": "wolf",
        "reward": reward,
        "min_level": min_level,
        "max_claims": max_claims,
        "expires_at": expires_at,
    }


def board():
    game = bb.BountyBoard()
    game.post(contract(), 0)
    return game


def test_post_adds_open_contract():
    game = board()
    assert game.board_view()["open"] == 1


def test_claim_marks_in_progress():
    game = board()
    game.claim("bob", "c1", 0)
    assert game.board_view()["in_progress"] == 1


def test_own_contract_cannot_be_claimed():
    game = board()
    with pytest.raises(ValueError):
        game.claim("alice", "c1", 0)


def test_min_level_is_enforced():
    game = bb.BountyBoard()
    game.post(contract(min_level=10), 0)
    with pytest.raises(ValueError):
        game.claim("bob", "c1", 0)


def test_max_claims_is_enforced():
    game = bb.BountyBoard()
    game.post(contract(max_claims=1), 0)
    game.claim("bob", "c1", 0)
    with pytest.raises(ValueError):
        game.claim("carol", "c1", 0)


def test_duplicate_claim_is_rejected():
    game = board()
    game.claim("bob", "c1", 0)
    with pytest.raises(ValueError):
        game.claim("bob", "c1", 1)


def test_player_can_hold_at_most_three():
    game = bb.BountyBoard()
    for index in range(4):
        game.post(contract(f"c{index}"), 0)
    for index in range(3):
        game.claim("bob", f"c{index}", 0)
    with pytest.raises(ValueError):
        game.claim("bob", "c3", 0)


def test_claim_expires_after_ten_minutes():
    game = board()
    game.claim("bob", "c1", 0)
    game.expire(601)
    assert game.board_view()["in_progress"] == 0


def test_complete_returns_reward():
    game = board()
    game.claim("bob", "c1", 0)
    result = game.complete("bob", "c1", 1)
    assert result["reward"] == 100


def test_non_claimant_cannot_complete():
    game = board()
    game.claim("bob", "c1", 0)
    with pytest.raises(ValueError):
        game.complete("carol", "c1", 1)


def test_duplicate_complete_is_rejected():
    game = board()
    game.claim("bob", "c1", 0)
    game.complete("bob", "c1", 1)
    with pytest.raises(ValueError):
        game.complete("bob", "c1", 2)


def test_expired_contract_cannot_be_claimed():
    game = board()
    with pytest.raises(ValueError):
        game.claim("bob", "c1", 1001)


def test_unknown_contract_is_rejected():
    with pytest.raises(ValueError):
        board().claim("bob", "ghost", 0)


def test_board_view_counts_states():
    game = board()
    game.claim("bob", "c1", 0)
    game.complete("bob", "c1", 1)
    info = game.board_view()
    assert info["completed"] == 1


def test_board_view_returns_copy():
    game = board()
    snap = game.board_view()
    snap["open"] = 99
    assert game.board_view()["open"] == 1
