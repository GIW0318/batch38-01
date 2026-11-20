import re

import pytest

import vault_quorum_lock as vq

VAULTS = {"v1": {"threshold": 3}, "v2": {"threshold": 3}}
OPERATORS = {
    "alice": {"revoked": False, "credential": "ka", "vaults": ["v1"], "actions": ["open"]},
    "bob": {"revoked": False, "credential": "kb", "vaults": ["v1"], "actions": ["open"]},
    "carol": {"revoked": False, "credential": "kc", "vaults": ["v1"], "actions": ["open"]},
    "dave": {"revoked": False, "credential": "kd", "vaults": ["v2"], "actions": ["open"]},
}


def vault():
    return vq.VaultQuorum(VAULTS, {k: dict(v) for k, v in OPERATORS.items()})


def opened(game=None, ttl=120):
    game = game or vault()
    request = game.open_request("v1", "open", ["alice", "bob", "carol"], ttl, 0)
    return game, request


def quorum(game, request, now=10):
    for name in ("alice", "bob", "carol"):
        game.approve(request["request_id"], name, OPERATORS[name]["credential"], now)


def test_open_returns_request_id():
    request = opened()[1]
    assert re.fullmatch(r"[0-9a-f]{32}", request["request_id"])
    assert request["threshold"] == 3


def test_unknown_operator_cannot_open():
    with pytest.raises(ValueError):
        vault().open_request("v1", "open", ["alice", "ghost", "carol"], 120, 0)


def test_three_approvals_reach_quorum():
    game, request = opened()
    for index, name in enumerate(("alice", "bob", "carol"), start=1):
        result = game.approve(request["request_id"], name, OPERATORS[name]["credential"], 10)
        assert result["approvals"] == index
    assert result["remaining"] == 0


def test_duplicate_approval_is_rejected():
    game, request = opened()
    game.approve(request["request_id"], "alice", "ka", 10)
    with pytest.raises(ValueError):
        game.approve(request["request_id"], "alice", "ka", 11)


def test_expired_approval_cannot_unlock():
    game, request = opened()
    quorum(game, request, 0)
    with pytest.raises(ValueError):
        game.unlock(request["request_id"], "ka", 61)


def test_wrong_credential_is_rejected():
    game, request = opened()
    with pytest.raises(ValueError):
        game.approve(request["request_id"], "alice", "wrong", 10)


def test_revoked_operator_is_rejected():
    game, request = opened()
    game.operators["alice"]["revoked"] = True
    with pytest.raises(ValueError):
        game.approve(request["request_id"], "alice", "ka", 10)


def test_operator_without_action_scope_is_rejected():
    game, request = opened()
    game.operators["bob"]["actions"] = ["audit"]
    with pytest.raises(ValueError):
        game.approve(request["request_id"], "bob", "kb", 10)


def test_unlock_succeeds_with_quorum():
    game, request = opened()
    quorum(game, request, 10)
    result = game.unlock(request["request_id"], "ka", 20)
    assert result["ok"] is True
    assert result["vault"] == "v1"


def test_unlock_fails_with_two_approvals():
    game, request = opened()
    game.approve(request["request_id"], "alice", "ka", 10)
    game.approve(request["request_id"], "bob", "kb", 10)
    with pytest.raises(ValueError):
        game.unlock(request["request_id"], "ka", 20)


def test_unlock_after_request_expiry_fails():
    game, request = opened(ttl=120)
    quorum(game, request, 0)
    with pytest.raises(ValueError):
        game.unlock(request["request_id"], "ka", 121)


def test_five_failed_unlocks_lock_vault():
    game, request = opened()
    game.approve(request["request_id"], "alice", "ka", 10)
    game.approve(request["request_id"], "bob", "kb", 10)
    for _ in range(5):
        with pytest.raises(ValueError):
            game.unlock(request["request_id"], "ka", 20)
    info = game.lockout("v1", 20)
    assert info["locked"] is True
    assert info["until"] == 320


def test_open_is_rejected_during_lockout():
    game, request = opened()
    game.approve(request["request_id"], "alice", "ka", 10)
    game.approve(request["request_id"], "bob", "kb", 10)
    for _ in range(5):
        with pytest.raises(ValueError):
            game.unlock(request["request_id"], "ka", 20)
    with pytest.raises(ValueError):
        game.open_request("v1", "open", ["alice", "bob", "carol"], 120, 30)


def test_successful_unlock_consumes_request():
    game, request = opened()
    quorum(game, request, 10)
    game.unlock(request["request_id"], "ka", 20)
    with pytest.raises(ValueError):
        game.unlock(request["request_id"], "ka", 21)


def test_audit_records_events_and_rejects_unknown_request():
    game, request = opened()
    quorum(game, request, 10)
    game.unlock(request["request_id"], "ka", 20)
    log = game.audit()
    assert len(log) >= 5
    assert [x["seq"] for x in log] == list(range(1, len(log) + 1))
    assert "open" in [x["type"] for x in log]
    assert "unlock" in [x["type"] for x in log]
    with pytest.raises(ValueError):
        game.approve("0" * 32, "alice", "ka", 30)
    with pytest.raises(ValueError):
        game.open_request("v1", "open", [], 120, 30)
