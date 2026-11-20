import pytest

import wallet_ledger as wl


def wallet():
    return wl.WalletLedger()


def test_earn_increases_balance():
    game = wallet()
    game.earn("alice", "gold", 100, 0, "quest")
    info = game.balance_check()
    assert info["balances"]["alice"]["gold"] == 100


def test_spend_decreases_balance():
    game = wallet()
    game.earn("alice", "gold", 100, 0, "quest")
    game.spend("alice", "gold", 40, 1)
    assert game.balance_check()["balances"]["alice"]["gold"] == 60


def test_transfer_moves_funds():
    game = wallet()
    game.earn("alice", "gold", 100, 0, "quest")
    game.transfer("alice", "bob", "gold", 30, 1)
    assert game.balance_check()["balances"]["bob"]["gold"] == 30


def test_transfer_daily_limit():
    game = wallet()
    game.earn("alice", "gold", 20000, 0, "quest")
    with pytest.raises(ValueError):
        game.transfer("alice", "bob", "gold", 10001, 1)


def test_escrow_freezes_funds():
    game = wallet()
    game.earn("alice", "gold", 100, 0, "quest")
    game.escrow("alice", "gold", 40, "order1", 1)
    info = game.balance_check()["balances"]["alice"]
    assert info["gold"] == 60
    assert info["frozen"] == 40


def test_settle_consumes_frozen_funds_once():
    game = wallet()
    game.earn("alice", "gold", 100, 0, "quest")
    game.escrow("alice", "gold", 40, "order1", 1)
    game.settle("order1", 2)
    with pytest.raises(ValueError):
        game.settle("order1", 3)


def test_refund_returns_frozen_funds():
    game = wallet()
    game.earn("alice", "gold", 100, 0, "quest")
    game.escrow("alice", "gold", 40, "order1", 1)
    game.refund("order1", 2)
    assert game.balance_check()["balances"]["alice"]["gold"] == 100


def test_refund_twice_is_rejected():
    game = wallet()
    game.earn("alice", "gold", 100, 0, "quest")
    game.escrow("alice", "gold", 40, "order1", 1)
    game.refund("order1", 2)
    with pytest.raises(ValueError):
        game.refund("order1", 3)


def test_refund_after_settle_is_rejected():
    game = wallet()
    game.earn("alice", "gold", 100, 0, "quest")
    game.escrow("alice", "gold", 40, "order1", 1)
    game.settle("order1", 2)
    with pytest.raises(ValueError):
        game.refund("order1", 3)


def test_rollover_is_idempotent():
    game = wallet()
    game.earn("alice", "valor", 100, 0, "quest")
    game.rollover(0)
    first = game.balance_check()["balances"]
    game.rollover(0)
    assert game.balance_check()["balances"] == first


def test_balance_check_reports_difference():
    game = wallet()
    game.earn("alice", "gold", 100, 0, "quest")
    info = game.balance_check()
    assert info["difference"] == 0


def test_journal_records_entries():
    game = wallet()
    game.earn("alice", "gold", 100, 0, "quest")
    entries = game.journal()
    assert entries[0]["seq"] == 1


def test_invalid_amounts_and_currency_are_rejected():
    game = wallet()
    with pytest.raises(ValueError):
        game.earn("alice", "gold", -1, 0, "quest")
    with pytest.raises(ValueError):
        game.earn("alice", "silver", 1, 0, "quest")


def test_time_backwards_is_rejected():
    game = wallet()
    game.earn("alice", "gold", 10, 10, "quest")
    with pytest.raises(ValueError):
        game.earn("alice", "gold", 10, 5, "quest")


def test_journal_returns_copy():
    game = wallet()
    game.earn("alice", "gold", 10, 0, "quest")
    entries = game.journal()
    entries.clear()
    assert game.journal()
