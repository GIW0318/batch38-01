import pytest

import automation_lane as al


def point(time, value, curve="linear", layer=0):
    return {"time": time, "value": value, "curve": curve, "layer": layer}


def lane_with(points, name="volume"):
    game = al.AutomationLane()
    for item in points:
        game.add(name, item)
    return game


def test_linear_interpolation():
    game = lane_with([point(0, 0.0), point(1, 1.0)])
    assert game.value("volume", 0.5) == pytest.approx(0.5, abs=0.02)


def test_hold_keeps_left_value():
    game = lane_with([point(0, 0.2, "hold"), point(1, 0.8, "hold")])
    assert game.value("volume", 0.5) == pytest.approx(0.2)


def test_exponential_curve():
    game = lane_with([point(0, 0.1, "exponential"), point(1, 0.9, "exponential")])
    assert 0.1 <= game.value("volume", 0.5) <= 0.9


def test_duplicate_time_is_rejected():
    game = al.AutomationLane()
    game.add("volume", point(0, 0.5))
    with pytest.raises(ValueError):
        game.add("volume", point(0, 0.6))


def test_endpoints_are_held():
    game = lane_with([point(1, 0.3), point(2, 0.7)])
    assert game.value("volume", 0) == pytest.approx(0.3)
    assert game.value("volume", 3) == pytest.approx(0.7)


def test_value_is_clamped():
    game = lane_with([point(0, -1.0), point(1, 2.0)])
    assert 0.0 <= game.value("volume", 0.5) <= 1.0


def test_layer_priority():
    game = al.AutomationLane()
    game.add("volume", point(0, 0.1, layer=2))
    game.add("volume", point(0, 0.9, layer=0))
    assert game.value("volume", 0) == pytest.approx(0.9)


def test_same_layer_later_wins():
    game = al.AutomationLane()
    game.add("volume", point(0, 0.2, layer=1))
    game.add("volume", point(0, 0.8, layer=1))
    assert game.value("volume", 0) == pytest.approx(0.8)


def test_blend_uses_equal_power():
    game = lane_with([point(0, 0.0)])
    game.add("music", point(0, 1.0))
    assert game.blend("volume", "music", 0.5) > 0.5


def test_negative_time_is_rejected():
    game = al.AutomationLane()
    with pytest.raises(ValueError):
        game.add("volume", point(-1, 0.5))


def test_invalid_curve_is_rejected():
    game = al.AutomationLane()
    with pytest.raises(ValueError):
        game.add("volume", point(0, 0.5, "bezier"))


def test_nan_value_is_rejected():
    game = al.AutomationLane()
    with pytest.raises(ValueError):
        game.add("volume", point(0, float("nan")))


def test_lanes_returns_copy():
    game = lane_with([point(0, 0.5)])
    snap = game.lanes()
    snap["lanes"].clear()
    assert game.lanes()["lanes"]


def test_sample_accuracy_is_reported():
    game = lane_with([point(0, 0.0), point(1, 1.0)])
    assert game.lanes()["sample_rate"] == 48000


def test_unknown_lane_is_rejected():
    with pytest.raises(ValueError):
        al.AutomationLane().value("ghost", 0)
