import re

import pytest

import slo_ticket_relay as sr


def relay():
    return sr.SloRelay()


def planned(session="s1", sps=None, now=0):
    game = relay()
    tickets = game.plan(session, "idp1", sps or ["sp1", "sp2"], now)
    return game, tickets


def test_plan_deduplicates_sps():
    _, tickets = planned(sps=["sp1", "sp1", "sp2"])
    assert len(tickets) == 2
    assert [x["sp"] for x in tickets] == ["sp1", "sp2"]


def test_ticket_format_and_binding():
    _, tickets = planned()
    ticket = tickets[0]
    assert re.fullmatch(r"[0-9a-f]{32}", ticket["ticket_id"])
    assert ticket["session"] == "s1"
    assert ticket["idp"] == "idp1"
    assert ticket["expires_at"] == 120


def test_more_than_twenty_sps_is_rejected():
    with pytest.raises(ValueError):
        relay().plan("s1", "idp1", [f"sp{i}" for i in range(21)], 0)


def test_empty_session_is_rejected():
    with pytest.raises(ValueError):
        relay().plan("", "idp1", ["sp1"], 0)


def test_dispatch_returns_bound_payload():
    game, tickets = planned()
    payload = game.dispatch(tickets[0], 1)
    assert payload["sp"] == "sp1"
    assert payload["attempts"] == 1


def test_expired_ticket_cannot_be_dispatched():
    game, tickets = planned(now=0)
    with pytest.raises(ValueError):
        game.dispatch(tickets[0], 121)


def test_dispatch_is_limited_to_three_attempts():
    game, tickets = planned()
    for index in range(3):
        game.dispatch(tickets[0], index)
    with pytest.raises(ValueError):
        game.dispatch(tickets[0], 4)


def test_ack_rejects_wrong_sp():
    game, tickets = planned()
    with pytest.raises(ValueError):
        game.ack(tickets[0], "sp2", tickets[0]["nonce"], 1)


def test_ack_rejects_wrong_nonce():
    game, tickets = planned()
    with pytest.raises(ValueError):
        game.ack(tickets[0], "sp1", "0" * 32, 1)


def test_duplicate_ack_is_idempotent():
    game, tickets = planned()
    assert game.ack(tickets[0], "sp1", tickets[0]["nonce"], 1) is True
    assert game.ack(tickets[0], "sp1", tickets[0]["nonce"], 2) is True


def test_state_is_partial_with_pending_sp():
    game, tickets = planned()
    game.ack(tickets[0], "sp1", tickets[0]["nonce"], 1)
    assert game.state("s1")["status"] == "partial"


def test_state_is_success_when_all_ack():
    game, tickets = planned()
    for ticket in tickets:
        game.ack(ticket, ticket["sp"], ticket["nonce"], 1)
    assert game.state("s1")["status"] == "success"


def test_state_is_failed_after_retry_exhaustion():
    game, tickets = planned()
    for index in range(3):
        game.dispatch(tickets[0], index)
    assert game.state("s1")["status"] == "failed"


def test_old_ack_does_not_override_success():
    game, tickets = planned()
    for ticket in tickets:
        game.ack(ticket, ticket["sp"], ticket["nonce"], 1)
    game.ack(tickets[0], "sp1", tickets[0]["nonce"], 100)
    assert game.state("s1")["status"] == "success"


def test_state_returns_copy():
    game, tickets = planned()
    snap = game.state("s1")
    snap["tickets"].clear()
    assert game.state("s1")["tickets"]
