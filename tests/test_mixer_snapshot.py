import pytest

import mixer_snapshot as ms

BUSES = ["master", "music", "sfx"]


def params(**over):
    value = {
        "master": {"gain": 1.0, "send": 0.0, "lowpass": 20000, "parent": None, "locked": False},
        "music": {"gain": 0.8, "send": 0.2, "lowpass": 18000, "parent": "master", "locked": False},
        "sfx": {"gain": 0.9, "send": 0.1, "lowpass": 20000, "parent": "master", "locked": False},
    }
    for key, patch in over.items():
        value[key].update(patch)
    return value


def mixer():
    return ms.MixerRecall()


def captured():
    game = mixer()
    game.capture("scene_a", BUSES, params(), 0)
    return game


def test_capture_creates_version():
    game = captured()
    info = game.detail()
    assert info["versions"] == 1
    assert info["current"] == "scene_a"


def test_same_name_increments_version():
    game = captured()
    game.capture("scene_a", BUSES, params(), 1)
    assert game.detail()["versions"] == 2


def test_linear_blend():
    game = captured()
    game.capture("scene_b", BUSES, params(music={"gain": 0.4}), 1)
    out = game.blend("scene_a", "scene_b", 0.5, "linear")
    assert out["music"]["gain"] == pytest.approx(0.6)


def test_equal_power_blend():
    game = captured()
    game.capture("scene_b", BUSES, params(music={"gain": 0.0}), 1)
    out = game.blend("scene_a", "scene_b", 0.5, "equal_power")
    assert out["music"]["gain"] > 0.4


def test_apply_skips_locked_bus():
    game = captured()
    game.capture("scene_b", BUSES, params(music={"gain": 0.2, "locked": True}), 1)
    game.apply("scene_b", "music", 2)
    assert game.detail()["current_params"]["music"]["gain"] == 0.8


def test_parent_gain_is_multiplied_once():
    game = captured()
    game.capture("scene_b", BUSES, params(master={"gain": 0.5}), 1)
    game.apply("scene_b", "music", 2)
    assert game.detail()["current_params"]["music"]["gain"] == pytest.approx(0.4)


def test_schedule_queues_transition():
    game = captured()
    game.capture("scene_b", BUSES, params(), 1)
    game.schedule("scene_b", 10, "linear")
    assert game.detail()["scheduled"] == "scene_b"


def test_apply_during_transition_queues():
    game = captured()
    game.capture("scene_b", BUSES, params(), 1)
    game.schedule("scene_b", 10, "linear")
    game.apply("scene_b", "music", 2)
    assert game.detail()["pending"] >= 1


def test_rollback_returns_previous_version():
    game = captured()
    game.capture("scene_b", BUSES, params(), 1)
    game.rollback(1)
    assert game.detail()["current"] == "scene_a"


def test_rollback_beyond_start_is_clamped():
    game = captured()
    game.rollback(99)
    assert game.detail()["current"] == "scene_a"


def test_send_is_soft_capped():
    game = captured()
    game.capture("loud", BUSES, params(music={"send": 2.0}), 1)
    game.apply("loud", "music", 2)
    assert game.detail()["current_params"]["music"]["send"] == pytest.approx(1.0)


def test_unknown_snapshot_is_rejected():
    with pytest.raises(ValueError):
        captured().apply("ghost", "music", 1)


def test_parameter_range_is_enforced():
    game = mixer()
    with pytest.raises(ValueError):
        game.capture("bad", BUSES, params(music={"gain": 2.0}), 0)


def test_parent_cycle_is_rejected():
    game = mixer()
    with pytest.raises(ValueError):
        game.capture("cycle", BUSES, params(master={"parent": "music"}), 0)


def test_detail_returns_copy():
    game = captured()
    snap = game.detail()
    snap["current_params"]["music"]["gain"] = 0.0
    assert game.detail()["current_params"]["music"]["gain"] == 0.8
