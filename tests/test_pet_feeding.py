import pytest

import pet_feeding as pf

PETS = {
    "rex": {"id": "rex", "hunger": 50, "happiness": 50, "alive": True, "diet": "meat"},
}
MEALS = {
    "steak": {"id": "steak", "nutrition": 20, "quality": 4, "cooldown": 60, "buff": "well_fed", "category": "meat"},
    "grass": {"id": "grass", "nutrition": 10, "quality": 1, "cooldown": 60, "buff": "green", "category": "veg"},
}


def bowl():
    return pf.FeedBowl({k: dict(v) for k, v in PETS.items()}, {k: dict(v) for k, v in MEALS.items()})


def test_give_increases_hunger():
    game = bowl()
    game.give("rex", "steak", 0)
    assert game.pet_view("rex")["hunger"] == 70


def test_hunger_is_capped_at_one_hundred():
    game = bowl()
    game.pets["rex"]["hunger"] = 90
    with pytest.raises(ValueError):
        game.give("rex", "steak", 0)


def test_same_meal_has_cooldown():
    game = bowl()
    game.give("rex", "steak", 0)
    with pytest.raises(ValueError):
        game.give("rex", "steak", 10)


def test_quality_controls_happiness():
    game = bowl()
    game.give("rex", "steak", 0)
    assert game.pet_view("rex")["happiness"] == 55


def test_tick_decays_hunger():
    game = bowl()
    game.tick(600)
    assert game.pet_view("rex")["hunger"] == 45


def test_low_hunger_decays_happiness():
    game = bowl()
    game.pets["rex"]["hunger"] = 10
    game.tick(60)
    assert game.pet_view("rex")["happiness"] < 50


def test_play_changes_values():
    game = bowl()
    game.play("rex", 0)
    info = game.pet_view("rex")
    assert info["happiness"] == 60
    assert info["hunger"] == 45


def test_play_has_cooldown():
    game = bowl()
    game.play("rex", 0)
    with pytest.raises(ValueError):
        game.play("rex", 10)


def test_buff_is_applied():
    game = bowl()
    game.give("rex", "steak", 0)
    assert game.pet_view("rex")["buffs"][0]["id"] == "well_fed"


def test_same_buff_refreshes_not_stacks():
    game = bowl()
    game.meals["steak"]["cooldown"] = 0
    game.give("rex", "steak", 0)
    game.give("rex", "steak", 1)
    assert len(game.pet_view("rex")["buffs"]) == 1


def test_third_distinct_buff_is_rejected():
    game = bowl()
    for name in ("a", "b"):
        game.meals[name] = {"id": name, "nutrition": 1, "quality": 1, "cooldown": 0, "buff": name, "category": "meat"}
        game.give("rex", name, 0)
    game.meals["c"] = {"id": "c", "nutrition": 1, "quality": 1, "cooldown": 0, "buff": "c", "category": "meat"}
    with pytest.raises(ValueError):
        game.give("rex", "c", 1)


def test_wrong_category_gives_half_nutrition():
    game = bowl()
    game.give("rex", "grass", 0)
    assert game.pet_view("rex")["hunger"] == 55


def test_dead_pet_rejects_all_actions():
    game = bowl()
    game.pets["rex"]["alive"] = False
    with pytest.raises(ValueError):
        game.give("rex", "steak", 0)
    with pytest.raises(ValueError):
        game.play("rex", 0)


def test_unknown_pet_meal_and_negative_time_are_rejected():
    game = bowl()
    with pytest.raises(ValueError):
        game.give("ghost", "steak", 0)
    with pytest.raises(ValueError):
        game.give("rex", "ghost", 0)
    with pytest.raises(ValueError):
        game.tick(-1)


def test_pet_view_returns_copy():
    game = bowl()
    game.give("rex", "steak", 0)
    snap = game.pet_view("rex")
    snap["buffs"].clear()
    assert game.pet_view("rex")["buffs"]
