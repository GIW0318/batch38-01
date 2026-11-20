import pytest

import bank_tab_sort as bs


def item(iid="ore", stack=20, bound=False, category="material"):
    return {"id": iid, "stack": stack, "bound": bound, "category": category}


def vault():
    return bs.VaultSort()


def test_deposit_creates_new_slot():
    game = vault()
    game.deposit(0, item(), 5)
    assert game.detail()["total"] == 5


def test_deposit_merges_partial_stack():
    game = vault()
    game.deposit(0, item(), 5)
    game.deposit(0, item(), 7)
    info = game.detail()
    assert info["total"] == 12
    assert info["tabs"][0]["slots"][0]["count"] == 12


def test_overflow_is_rejected_atomically():
    game = vault()
    game.deposit(0, item(stack=5), 5)
    with pytest.raises(ValueError):
        game.deposit(0, item(stack=5), 1)
    assert game.detail()["total"] == 5


def test_withdraw_reduces_count():
    game = vault()
    game.deposit(0, item(), 10)
    game.withdraw(0, "ore", 4)
    assert game.detail()["total"] == 6


def test_withdraw_more_than_available_is_rejected():
    game = vault()
    game.deposit(0, item(), 3)
    with pytest.raises(ValueError):
        game.withdraw(0, "ore", 4)


def test_invalid_count_is_rejected():
    game = vault()
    with pytest.raises(ValueError):
        game.deposit(0, item(), 0)
    with pytest.raises(ValueError):
        game.deposit(0, item(), -1)


def test_tab_bounds_are_enforced():
    game = vault()
    with pytest.raises(ValueError):
        game.deposit(6, item(), 1)


def test_unknown_item_is_rejected():
    game = vault()
    with pytest.raises(ValueError):
        game.withdraw(0, "ghost", 1)


def test_compact_sorts_by_category_then_id():
    game = vault()
    game.deposit(0, item("zinc", category="metal"), 1)
    game.deposit(0, item("apple", category="food"), 1)
    game.compact(0)
    slots = game.detail()["tabs"][0]["slots"]
    assert slots[0]["id"] == "apple"


def test_compact_skips_locked_slots():
    game = vault()
    game.deposit(0, item("a"), 1)
    game.deposit(0, item("b"), 1)
    game.detail()["tabs"][0]["slots"][0]["locked"] = True
    game.compact(0)
    assert game.detail()["tabs"][0]["slots"][0]["id"] == "a"


def test_bound_and_unbound_do_not_merge():
    game = vault()
    game.deposit(0, item(bound=False), 5)
    game.deposit(0, item(bound=True), 5)
    slots = game.detail()["tabs"][0]["slots"]
    assert len(slots) == 2


def test_stack_limit_is_enforced():
    game = vault()
    game.deposit(0, item(stack=5), 5)
    with pytest.raises(ValueError):
        game.deposit(0, item(stack=5), 1)


def test_total_tracks_all_tabs():
    game = vault()
    game.deposit(0, item(), 3)
    game.deposit(1, item(), 4)
    assert game.detail()["total"] == 7


def test_detail_returns_copy():
    game = vault()
    game.deposit(0, item(), 3)
    snap = game.detail()
    snap["tabs"][0]["slots"].clear()
    assert game.detail()["tabs"][0]["slots"]


def test_compact_merges_same_item():
    game = vault()
    game.deposit(0, item("ore", stack=20), 5)
    game.deposit(0, item("ore", stack=20), 5)
    game.compact(0)
    assert game.detail()["tabs"][0]["slots"][0]["count"] == 10
