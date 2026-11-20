import pytest

import shamir_split as ss

SECRET = "vault-secret-key"


def sharer():
    return ss.SecretSharer()


def split(secret=SECRET, threshold=3, shares=5, seed=1):
    game = sharer()
    return game, game.split(secret, threshold, shares, seed)


def test_split_returns_requested_shares():
    _, parts = split()
    assert len(parts) == 5
    assert all("." in part for part in parts)


def test_threshold_subset_reconstructs():
    game, parts = split()
    assert game.combine(parts[:3]) == SECRET


def test_any_threshold_subset_works():
    game, parts = split()
    assert game.combine([parts[0], parts[2], parts[4]]) == SECRET


def test_fewer_than_threshold_is_rejected():
    game, parts = split()
    with pytest.raises(ValueError):
        game.combine(parts[:2])


def test_duplicate_share_x_is_rejected():
    game, parts = split()
    with pytest.raises(ValueError):
        game.combine([parts[0], parts[0], parts[1]])


def test_verify_accepts_valid_share():
    game, parts = split()
    assert game.verify(parts[0]) is True


def test_tampered_share_fails_verify_and_combine():
    game, parts = split()
    tampered = parts[0][:-1] + ("0" if parts[0][-1] != "0" else "1")
    assert game.verify(tampered) is False
    with pytest.raises(ValueError):
        game.combine([tampered, parts[1], parts[2]])


def test_seed_is_deterministic():
    _, first = split(seed=7)
    _, second = split(seed=7)
    assert first
    assert first == second


def test_different_seed_changes_shares():
    _, first = split(seed=1)
    _, second = split(seed=2)
    assert first != second


def test_threshold_above_shares_is_rejected():
    with pytest.raises(ValueError):
        sharer().split(SECRET, 4, 3, 1)


def test_too_many_shares_is_rejected():
    with pytest.raises(ValueError):
        sharer().split(SECRET, 2, 256, 1)


def test_empty_secret_is_rejected():
    with pytest.raises(ValueError):
        sharer().split("", 2, 3, 1)


def test_oversized_secret_is_rejected():
    with pytest.raises(ValueError):
        sharer().split("x" * 65, 2, 3, 1)


def test_combine_is_order_independent():
    game, parts = split()
    assert game.combine([parts[2], parts[0], parts[1]]) == SECRET


def test_dump_hides_secret_and_coefficients():
    game, parts = split()
    info = game.dump()
    assert info["threshold"] == 3
    assert info["shares"] == 5
    assert SECRET not in str(info)
