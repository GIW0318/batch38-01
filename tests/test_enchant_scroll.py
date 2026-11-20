import pytest

import enchant_scroll as es


def item(iid="sword", level=100, kind="weapon"):
    return {"id": iid, "level": level, "type": kind, "enchantments": []}


def enchant(eid="fire", group="element", tier=1, curse=False, duration=100):
    return {"id": eid, "group": group, "tier": tier, "curse": curse, "duration": duration}


def stack():
    return es.EnchantStack()


def test_apply_adds_enchant():
    blade = item()
    stack().apply(blade, enchant(), 0)
    assert blade["enchantments"][0]["id"] == "fire"


def test_same_enchant_stacks_to_three():
    blade = item()
    game = stack()
    for _ in range(3):
        game.apply(blade, enchant(), 0)
    assert len(game.item_view(blade)["enchantments"]) == 1
    assert game.item_view(blade)["enchantments"][0]["layers"] == 3


def test_fourth_stack_is_rejected():
    blade = item()
    game = stack()
    for _ in range(3):
        game.apply(blade, enchant(), 0)
    with pytest.raises(ValueError):
        game.apply(blade, enchant(), 0)


def test_group_conflict_is_rejected():
    blade = item()
    game = stack()
    game.apply(blade, enchant("fire", "element"), 0)
    with pytest.raises(ValueError):
        game.apply(blade, enchant("ice", "element"), 0)


def test_gain_diminishes_per_stack():
    blade = item()
    game = stack()
    first = game.apply(blade, enchant(), 0)["gain"]
    second = game.apply(blade, enchant(), 0)["gain"]
    assert second < first


def test_tier_above_level_is_rejected():
    blade = item(level=10)
    with pytest.raises(ValueError):
        stack().apply(blade, enchant(tier=2), 0)


def test_curse_cannot_be_removed():
    blade = item()
    game = stack()
    game.apply(blade, enchant(curse=True), 0)
    with pytest.raises(ValueError):
        game.remove(blade, "fire", 1)


def test_duration_expires_on_tick():
    blade = item()
    game = stack()
    game.apply(blade, enchant(duration=5), 0)
    game.tick(6)
    assert game.item_view(blade)["enchantments"] == []


def test_remove_reduces_layer():
    blade = item()
    game = stack()
    game.apply(blade, enchant(), 0)
    result = game.remove(blade, "fire", 1)
    assert result["layers"] == 0


def test_unknown_item_is_rejected():
    with pytest.raises(ValueError):
        stack().apply(None, enchant(), 0)


def test_remove_missing_enchant_is_rejected():
    with pytest.raises(ValueError):
        stack().remove(item(), "fire", 0)


def test_armor_has_two_slots():
    armor = item("chest", kind="armor")
    game = stack()
    game.apply(armor, enchant("a", "g1"), 0)
    game.apply(armor, enchant("b", "g2"), 0)
    with pytest.raises(ValueError):
        game.apply(armor, enchant("c", "g3"), 0)


def test_total_gain_is_reported():
    blade = item()
    game = stack()
    game.apply(blade, enchant(), 0)
    assert game.item_view(blade)["gain"] > 0


def test_view_returns_copy():
    blade = item()
    game = stack()
    game.apply(blade, enchant(), 0)
    snap = game.item_view(blade)
    snap["enchantments"].clear()
    assert game.item_view(blade)["enchantments"]


def test_duplicate_application_merges_layers():
    blade = item()
    game = stack()
    game.apply(blade, enchant(), 0)
    game.apply(blade, enchant(), 0)
    assert len(game.item_view(blade)["enchantments"]) == 1
