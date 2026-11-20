import hashlib
import re

import pytest

import pow_challenge_gate as pg

SECRET = "test-secret"


def gate():
    return pg.PowGate(SECRET)


def leading_zero_bits(data):
    bits = 0
    for byte in data:
        if byte == 0:
            bits += 8
            continue
        for shift in range(7, -1, -1):
            if byte & (1 << shift):
                return bits
            bits += 1
    return bits


def solve(challenge, difficulty):
    for nonce in range(1000000):
        digest = hashlib.sha256((challenge + ":" + str(nonce)).encode()).digest()
        if leading_zero_bits(digest) >= difficulty:
            return nonce
    raise AssertionError("no solution")


def issued(game=None, client="alice", now=0, difficulty=4):
    game = game or gate()
    return game, game.issue(client, now, difficulty)


def test_issue_returns_required_fields():
    _, info = issued()
    assert re.fullmatch(r"[0-9a-f]{32}", info["challenge_id"])
    assert re.fullmatch(r"[0-9a-f]{64}", info["challenge"])
    assert info["expires_at"] == 120


def test_valid_solution_passes():
    game, info = issued()
    nonce = solve(info["challenge"], 4)
    result = game.verify("alice", info["challenge_id"], nonce, 1)
    assert result["ok"] is True


def test_wrong_solution_fails():
    game, info = issued()
    result = game.verify("alice", info["challenge_id"], 1, 1)
    assert result["ok"] is False


def test_replay_is_rejected():
    game, info = issued()
    nonce = solve(info["challenge"], 4)
    game.verify("alice", info["challenge_id"], nonce, 1)
    with pytest.raises(ValueError):
        game.verify("alice", info["challenge_id"], nonce, 2)


def test_expired_challenge_is_rejected():
    game, info = issued(now=0)
    nonce = solve(info["challenge"], 4)
    with pytest.raises(ValueError):
        game.verify("alice", info["challenge_id"], nonce, 121)


def test_negative_difficulty_is_rejected():
    with pytest.raises(ValueError):
        gate().issue("alice", 0, -1)


def test_difficulty_above_32_is_rejected():
    with pytest.raises(ValueError):
        gate().issue("alice", 0, 33)


def test_default_difficulty_is_sixteen():
    info = gate().issue("alice", 0)
    assert info["difficulty"] == 16


def test_failures_raise_next_difficulty():
    game, first = issued(difficulty=10)
    game.verify("alice", first["challenge_id"], 0, 1)
    second = game.issue("alice", 2, 10)
    assert second["difficulty"] == 12


def test_success_lowers_difficulty():
    game, first = issued(difficulty=10)
    nonce = solve(first["challenge"], 10)
    game.verify("alice", first["challenge_id"], nonce, 1)
    second = game.issue("alice", 2, 10)
    assert second["difficulty"] == 9


def test_outstanding_challenge_limit():
    game = gate()
    issued(game, difficulty=4)
    issued(game, difficulty=4)
    issued(game, difficulty=4)
    with pytest.raises(ValueError):
        game.issue("alice", 0, 4)


def test_unknown_challenge_is_rejected():
    with pytest.raises(ValueError):
        gate().verify("alice", "0" * 32, 0, 0)


def test_challenges_returns_copy():
    game = gate()
    issued(game, difficulty=4)
    snap = game.challenges()
    snap.clear()
    assert game.challenges()


def test_nonce_bounds_are_checked():
    game, info = issued()
    with pytest.raises(ValueError):
        game.verify("alice", info["challenge_id"], -1, 1)
    with pytest.raises(ValueError):
        game.verify("alice", info["challenge_id"], "1", 1)
    with pytest.raises(ValueError):
        game.verify("alice", info["challenge_id"], 2 ** 32, 1)


def test_difficulty_is_clamped_to_twelve():
    game, first = issued(difficulty=12)
    nonce = solve(first["challenge"], 12)
    game.verify("alice", first["challenge_id"], nonce, 1)
    assert game.issue("alice", 2, 12)["difficulty"] == 12
