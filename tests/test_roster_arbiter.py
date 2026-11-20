import pytest

import roster_arbiter as ra


def roster():
    game = ra.RosterArbiter()
    game.invite("leader", "tank", "tank", 0)
    game.accept("tank", 1)
    return game


def test_invite_creates_pending():
    game = ra.RosterArbiter()
    game.invite("leader", "alice", "dps", 0)
    assert game.state()["pending"] == 1


def test_leader_cannot_invite_self():
    with pytest.raises(ValueError):
        ra.RosterArbiter().invite("leader", "leader", "tank", 0)


def test_accept_joins_party():
    game = roster()
    assert game.state()["members"][0]["player"] == "tank"


def test_duplicate_accept_is_rejected():
    game = roster()
    with pytest.raises(ValueError):
        game.accept("tank", 2)


def test_role_capacity_is_enforced():
    game = roster()
    game.invite("leader", "tank2", "tank", 0)
    with pytest.raises(ValueError):
        game.accept("tank2", 1)


def test_non_leader_cannot_kick():
    game = roster()
    with pytest.raises(ValueError):
        game.kick("tank", "leader")


def test_leader_can_kick_member():
    game = roster()
    game.kick("leader", "tank")
    assert game.state()["members"] == []


def test_leader_leave_transfers_to_earliest():
    game = roster()
    game.invite("leader", "healer", "healer", 0)
    game.accept("healer", 1)
    game.leave("leader", 2)
    assert game.state()["leader"] == "tank"


def test_ready_check_requires_all():
    game = roster()
    with pytest.raises(ValueError):
        game.start("leader", 0)


def test_start_succeeds_when_ready():
    game = roster()
    game.ready("tank", True)
    assert game.start("leader", 0)["ok"] is True


def test_disconnect_grace_keeps_slot():
    game = roster()
    game.leave("tank", 0)
    info = game.state()
    assert info["grace"] >= 1


def test_invite_expires_after_sixty_seconds():
    game = ra.RosterArbiter()
    game.invite("leader", "alice", "dps", 0)
    with pytest.raises(ValueError):
        game.accept("alice", 61)


def test_decline_removes_invite():
    game = ra.RosterArbiter()
    game.invite("leader", "alice", "dps", 0)
    game.decline("alice", 1)
    assert game.state()["pending"] == 0


def test_state_returns_copy():
    game = roster()
    snap = game.state()
    snap["members"].clear()
    assert game.state()["members"]


def test_unknown_player_actions_are_rejected():
    with pytest.raises(ValueError):
        roster().ready("ghost", True)
