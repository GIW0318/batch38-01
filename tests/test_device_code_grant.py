import re

import pytest

import device_code_grant as dg

APPS = {"car": {"allowed_perms": ["read", "write"]}}
PERMS = ["read", "write"]


def grant():
    return dg.DeviceGrant(APPS, PERMS)


def begun(game=None, fingerprint="fp-1", perms=None, now=0):
    game = game or grant()
    return game, game.begin("car", fingerprint, perms or ["read"], now)


def test_begin_returns_handle_and_short_code():
    _, info = begun()
    assert re.fullmatch(r"[0-9a-f]{32}", info["handle"])
    assert re.fullmatch(r"[0-9]{6}", info["short_code"])
    assert info["expires_at"] == 300


def test_unknown_app_is_rejected():
    with pytest.raises(ValueError):
        grant().begin("ghost", "fp", ["read"], 0)


def test_perms_are_deduplicated():
    _, info = begun(perms=["read", "read", "write"])
    game = grant()
    info = game.begin("car", "fp", ["read", "read", "write"], 0)
    game.claim(info["short_code"], "alice", 0)
    token = game.redeem(info["handle"], "fp", 0)
    assert token["perms"] == ["read", "write"]


def test_perm_outside_whitelist_is_rejected():
    with pytest.raises(ValueError):
        grant().begin("car", "fp", ["admin"], 0)


def test_empty_fingerprint_is_rejected():
    with pytest.raises(ValueError):
        grant().begin("car", "", ["read"], 0)


def test_claim_binds_account():
    game, info = begun()
    game.claim(" " + info["short_code"] + " ", "alice", 0)
    assert game.snapshot()["claimed"] == 1


def test_second_claim_is_rejected():
    game, info = begun()
    game.claim(info["short_code"], "alice", 0)
    with pytest.raises(ValueError):
        game.claim(info["short_code"], "bob", 1)


def test_expired_claim_is_rejected():
    game, info = begun(now=0)
    with pytest.raises(ValueError):
        game.claim(info["short_code"], "alice", 301)


def test_redeem_returns_exact_perms():
    game, info = begun(perms=["read", "write"])
    game.claim(info["short_code"], "alice", 0)
    token = game.redeem(info["handle"], "fp-1", 1)
    assert token["perms"] == ["read", "write"]
    assert token["subject"] == "alice"


def test_redeem_with_wrong_fingerprint_is_rejected():
    game, info = begun()
    game.claim(info["short_code"], "alice", 0)
    with pytest.raises(ValueError):
        game.redeem(info["handle"], "fp-2", 1)


def test_redeem_twice_is_rejected():
    game, info = begun()
    game.claim(info["short_code"], "alice", 0)
    game.redeem(info["handle"], "fp-1", 1)
    with pytest.raises(ValueError):
        game.redeem(info["handle"], "fp-1", 2)


def test_revoke_subject_invalidates_pending_grants():
    game, info = begun()
    game.claim(info["short_code"], "alice", 0)
    game.revoke_subject("alice", 1)
    with pytest.raises(ValueError):
        game.redeem(info["handle"], "fp-1", 2)


def test_unknown_and_revoked_handles_are_indistinguishable():
    game = grant()
    with pytest.raises(ValueError) as first:
        game.redeem("0" * 32, "fp", 0)
    _, info = begun(game)
    game.claim(info["short_code"], "alice", 0)
    game.revoke_subject("alice", 1)
    with pytest.raises(ValueError) as second:
        game.redeem(info["handle"], "fp", 2)
    assert str(first.value) == str(second.value)


def test_pending_limit_per_fingerprint():
    game = grant()
    begun(game, now=0)
    begun(game, now=0)
    begun(game, now=0)
    with pytest.raises(ValueError):
        game.begin("car", "fp-1", ["read"], 0)


def test_snapshot_returns_copy():
    game, info = begun()
    game.claim(info["short_code"], "alice", 0)
    snap = game.snapshot()
    snap["claimed"] = 99
    assert game.snapshot()["claimed"] == 1
