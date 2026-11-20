import pytest

import durability_wear as dw


def make(iid="sword", quality=3, maximum=100, current=100, blessed=False, set_id=None):
    return {
        "id": iid,
        "quality": quality,
        "max": maximum,
        "current": current,
        "blessed": blessed,
        "set_id": set_id,
    }


def book(*items):
    return dw.DurabilityBook(list(items))


def test_quality_one_wears_full_amount():
    item = make(quality=1)
    book(item).wear("sword", 10, "melee", 0)
    assert item["current"] == 90


def test_quality_five_wears_sixty_percent():
    item = make(quality=5)
    book(item).wear("sword", 10, "melee", 0)
    assert item["current"] == 94


def test_environment_damage_takes_half():
    item = make(quality=1)
    book(item).wear("sword", 10, "environment", 0)
    assert item["current"] == 95


def test_death_penalty_takes_ten_percent_of_max():
    item = make(quality=2)
    book(item).wear("sword", 0, "death", 0)
    assert item["current"] == 90


def test_blessing_saves_once_per_day():
    item = make(quality=1, current=1, blessed=True)
    game = book(item)
    game.wear("sword", 1, "melee", 0)
    assert item["current"] == 1
    assert item["blessed"] is False
    game.wear("sword", 1, "melee", 0)
    assert item["current"] == 0


def test_blessing_can_come_back_next_day():
    item = make(quality=1, current=1, blessed=True)
    game = book(item)
    game.wear("sword", 1, "melee", 0)
    game.wear("sword", 1, "melee", 0)
    assert item["current"] == 0
    item["current"] = 1
    item["blessed"] = True
    game.wear("sword", 1, "melee", 86400)
    assert item["current"] == 1


def test_broken_set_piece_disables_bonus():
    items = [
        make("a", set_id="warrior"),
        make("b", set_id="warrior"),
        make("c", set_id="warrior"),
        make("d", set_id="warrior", current=0),
    ]
    active = book(*items).reconcile()
    assert active["warrior"] == 3


def test_quote_locks_price_and_checks_durability():
    item = make(quality=4, current=50)
    game = book(item)
    q = game.quote("sword", 10, 0)
    assert q["cost"] == 80
    game.wear("sword", 5, "melee", 0)
    with pytest.raises(ValueError):
        game.repair("sword", q["quote_id"], 10)


def test_quote_expires_after_sixty_seconds():
    item = make(quality=4, current=50)
    game = book(item)
    q = game.quote("sword", 10, 0)
    with pytest.raises(ValueError):
        game.repair("sword", q["quote_id"], 61)


def test_quote_can_only_be_used_once():
    item = make(quality=4, current=50)
    game = book(item)
    q = game.quote("sword", 10, 0)
    game.repair("sword", q["quote_id"], 10)
    with pytest.raises(ValueError):
        game.repair("sword", q["quote_id"], 11)


def test_repair_is_blocked_in_combat():
    item = make(quality=4, current=50)
    game = book(item)
    q = game.quote("sword", 10, 0)
    game.set_combat(True)
    with pytest.raises(ValueError):
        game.repair("sword", q["quote_id"], 10)


def test_repair_cannot_exceed_missing_points():
    item = make(quality=4, current=90)
    game = book(item)
    q = game.quote("sword", 20, 0)
    with pytest.raises(ValueError):
        game.repair("sword", q["quote_id"], 10)


def test_upgrade_preserves_percentage_and_voids_quote():
    item = make(quality=4, maximum=100, current=50)
    game = book(item)
    q = game.quote("sword", 10, 0)
    game.upgrade_max("sword", 200, 0)
    assert item["current"] == 100
    with pytest.raises(ValueError):
        game.repair("sword", q["quote_id"], 10)


def test_unknown_item_and_negative_wear_are_rejected():
    game = book(make())
    with pytest.raises(ValueError):
        game.wear("ghost", 1, "melee", 0)
    with pytest.raises(ValueError):
        game.wear("sword", -1, "melee", 0)


def test_audit_records_ordered_events():
    item = make(quality=4, current=50)
    game = book(item)
    game.wear("sword", 1, "melee", 0)
    q = game.quote("sword", 10, 0)
    game.repair("sword", q["quote_id"], 1)
    log = game.audit()
    assert len(log) == 3
    assert [x["seq"] for x in log] == [1, 2, 3]
    assert [x["type"] for x in log] == ["wear", "quote", "repair"]
    log.append({"seq": 99})
    assert len(game.audit()) == 3
