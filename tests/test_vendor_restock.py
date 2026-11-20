import pytest

import vendor_restock as vs

ITEMS = {
    "potion": {"id": "potion", "stock": 10, "max_stock": 10, "base_price": 100, "daily_limit": 2, "bound": False},
    "sword": {"id": "sword", "stock": 10, "max_stock": 10, "base_price": 200, "daily_limit": 1, "bound": True},
}


def vendor(rep=0):
    items = {k: dict(v) for k, v in ITEMS.items()}
    return vs.VendorStock(items, reputation=rep)


def test_quote_returns_price_and_expiry():
    info = vendor().quote("alice", "potion", 1, 0)
    assert info["price"] == 100
    assert info["expires_at"] == 30


def test_quote_expires_after_thirty_seconds():
    game = vendor()
    quote = game.quote("alice", "potion", 1, 0)
    with pytest.raises(ValueError):
        game.buy("alice", "potion", 1, quote["quote_id"], 31)


def test_quote_is_single_use():
    game = vendor()
    quote = game.quote("alice", "potion", 1, 0)
    game.buy("alice", "potion", 1, quote["quote_id"], 1)
    with pytest.raises(ValueError):
        game.buy("alice", "potion", 1, quote["quote_id"], 2)


def test_buy_reduces_stock():
    game = vendor()
    quote = game.quote("alice", "potion", 1, 0)
    game.buy("alice", "potion", 1, quote["quote_id"], 1)
    assert game.shelves()["items"]["potion"]["stock"] == 9


def test_insufficient_stock_is_rejected():
    game = vendor()
    game.items["potion"]["stock"] = 0
    with pytest.raises(ValueError):
        game.quote("alice", "potion", 1, 0)


def test_daily_limit_is_enforced():
    game = vendor()
    for index in range(2):
        quote = game.quote("alice", "potion", 1, index)
        game.buy("alice", "potion", 1, quote["quote_id"], index)
    with pytest.raises(ValueError):
        game.quote("alice", "potion", 1, 100)


def test_low_stock_raises_price():
    game = vendor()
    game.items["potion"]["stock"] = 1
    assert game.quote("alice", "potion", 1, 0)["price"] == 120


def test_high_stock_lowers_price():
    game = vendor()
    game.items["potion"]["stock"] = 9
    assert game.quote("alice", "potion", 1, 0)["price"] == 90


def test_reputation_discount():
    game = vendor(rep=5)
    assert game.quote("alice", "potion", 1, 0)["price"] == 85


def test_sell_returns_half_price():
    game = vendor()
    assert game.sell("alice", "potion", 1, 0)["gold"] == 50


def test_bound_item_cannot_be_sold():
    with pytest.raises(ValueError):
        vendor().sell("alice", "sword", 1, 0)


def test_buyback_keeps_last_twelve():
    game = vendor()
    for index in range(13):
        game.sell("alice", "potion", 1, index)
    assert game.shelves()["buyback"] == 12


def test_buyback_expires_after_five_minutes():
    game = vendor()
    game.sell("alice", "potion", 1, 0)
    with pytest.raises(ValueError):
        game.buyback("alice", 0, 301)


def test_restock_fills_items():
    game = vendor()
    game.items["potion"]["stock"] = 0
    game.restock(0)
    assert game.items["potion"]["stock"] == 10


def test_shelves_returns_copy():
    game = vendor()
    snap = game.shelves()
    snap["items"]["potion"]["stock"] = 99
    assert game.shelves()["items"]["potion"]["stock"] == 10
