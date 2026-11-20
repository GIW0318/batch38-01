import pytest

import mount_stamina as ms


def mount(max_stamina=100):
    return ms.MountMeter(max_stamina=max_stamina)


def test_walk_consumes_one_per_second():
    game = mount()
    game.ride("walk", "grass", 10)
    assert game.mount_view()["stamina"] == 90


def test_sprint_consumes_fifteen_per_second():
    game = mount()
    game.ride("sprint", "grass", 2)
    assert game.mount_view()["stamina"] == 70


def test_terrain_multiplier_applies():
    game = mount()
    game.ride("walk", "sand", 10)
    assert game.mount_view()["stamina"] == 87


def test_exhaustion_clamps_to_zero():
    game = mount()
    game.ride("sprint", "water", 10)
    assert game.mount_view()["stamina"] == 0
    assert game.mount_view()["status"] == "exhausted"


def test_rest_regenerates_five_per_second():
    game = mount()
    game.ride("walk", "grass", 10)
    game.rest(2)
    assert game.mount_view()["stamina"] == 100


def test_unknown_feed_item_is_rejected():
    with pytest.raises(ValueError):
        mount().feed("rock", 0)


def test_feed_restores_forty():
    game = mount()
    game.ride("walk", "grass", 10)
    game.feed("apple", 0)
    assert game.mount_view()["stamina"] == 100


def test_feed_has_sixty_second_cooldown():
    game = mount()
    game.ride("walk", "grass", 10)
    game.feed("apple", 0)
    with pytest.raises(ValueError):
        game.feed("apple", 10)


def test_jump_consumes_stamina():
    game = mount()
    game.jump(2)
    assert game.mount_view()["stamina"] == 86


def test_high_fall_adds_penalty():
    game = mount()
    game.jump(5)
    assert game.mount_view()["stamina"] == 70


def test_cap_change_truncates_stamina():
    game = mount(50)
    game.ride("walk", "grass", 0)
    assert game.mount_view()["stamina"] == 50


def test_unknown_gait_is_rejected():
    with pytest.raises(ValueError):
        mount().ride("fly", "grass", 1)


def test_unknown_terrain_is_rejected():
    with pytest.raises(ValueError):
        mount().ride("walk", "lava", 1)


def test_negative_time_is_rejected():
    with pytest.raises(ValueError):
        mount().ride("walk", "grass", -1)


def test_mount_view_returns_copy():
    game = mount()
    game.ride("walk", "grass", 10)
    snap = game.mount_view()
    snap["stamina"] = 99
    assert game.mount_view()["stamina"] == 90
