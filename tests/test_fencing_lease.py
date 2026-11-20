import re

import pytest

import fencing_lease as fl


def lease():
    return fl.FenceLease()


def test_acquire_returns_monotonic_token():
    info = lease().acquire("db", "alice", 0, 60)
    assert re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}", info["token"])
    assert info["expires_at"] == 60


def test_same_owner_gets_same_token():
    game = lease()
    first = game.acquire("db", "alice", 0, 60)
    second = game.acquire("db", "alice", 10, 60)
    assert second["token"] == first["token"]


def test_other_owner_cannot_steal_valid_lease():
    game = lease()
    game.acquire("db", "alice", 0, 60)
    with pytest.raises(ValueError):
        game.acquire("db", "bob", 10, 60)


def test_expired_lease_can_be_reacquired_with_new_epoch():
    game = lease()
    first = game.acquire("db", "alice", 0, 60)
    second = game.acquire("db", "bob", 61, 60)
    assert second["token"] != first["token"]
    assert second["epoch"] == first["epoch"] + 1


def test_renew_extends_expiry():
    game = lease()
    info = game.acquire("db", "alice", 0, 60)
    renewed = game.renew(info["token"], 30, 120)
    assert renewed["expires_at"] == 150


def test_renew_by_old_token_is_rejected():
    game = lease()
    old = game.acquire("db", "alice", 0, 60)
    game.acquire("db", "bob", 61, 60)
    with pytest.raises(ValueError):
        game.renew(old["token"], 62, 60)


def test_release_frees_resource():
    game = lease()
    info = game.acquire("db", "alice", 0, 60)
    game.release(info["token"])
    assert game.acquire("db", "bob", 1, 60)["owner"] == "bob"


def test_validate_accepts_current_token():
    game = lease()
    info = game.acquire("db", "alice", 0, 60)
    assert game.validate("db", info["token"], 30) is True


def test_validate_rejects_expired_token():
    game = lease()
    info = game.acquire("db", "alice", 0, 60)
    assert game.validate("db", info["token"], 61) is False


def test_validate_rejects_old_token_after_reacquire():
    game = lease()
    old = game.acquire("db", "alice", 0, 60)
    game.acquire("db", "bob", 61, 60)
    assert game.validate("db", old["token"], 62) is False


def test_validate_rejects_wrong_resource():
    game = lease()
    info = game.acquire("db", "alice", 0, 60)
    assert game.validate("cache", info["token"], 30) is False


def test_ttl_bounds_are_enforced():
    game = lease()
    with pytest.raises(ValueError):
        game.acquire("db", "alice", 0, 0)
    with pytest.raises(ValueError):
        game.acquire("db", "alice", 0, 3601)


def test_time_backwards_is_rejected():
    game = lease()
    game.acquire("db", "alice", 10, 60)
    with pytest.raises(ValueError):
        game.acquire("db", "bob", 5, 60)


def test_empty_resource_and_unknown_token_are_rejected():
    game = lease()
    with pytest.raises(ValueError):
        game.acquire("", "alice", 0, 60)
    with pytest.raises(ValueError):
        game.release("0" * 8 + "-0000")


def test_leases_returns_copy():
    game = lease()
    game.acquire("db", "alice", 0, 60)
    snap = game.leases()
    snap["db"]["owner"] = "mallory"
    assert game.leases()["db"]["owner"] == "alice"
