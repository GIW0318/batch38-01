import pytest

import frame_budget_governor as fbg


def gov():
    return fbg.FrameGovernor()


def frame(governor, number, render=10.0, logic=5.0, other=1.0):
    governor.record("render", render, number)
    governor.record("logic", logic, number)
    governor.record("other", other, number)


def test_mean_uses_recent_frames():
    engine = gov()
    for number in range(3):
        engine.record("render", 10.0, number)
    assert engine.budget()["passes"]["render"]["mean"] == pytest.approx(10.0)


def test_p95_is_not_the_maximum():
    engine = gov()
    for number in range(1, 21):
        engine.record("render", float(number), number)
    assert engine.budget()["passes"]["render"]["p95"] == pytest.approx(19.0)


def test_three_consecutive_spikes_are_counted():
    engine = gov()
    for number in range(5):
        engine.record("render", 5.0, number)
    for number in range(5, 8):
        engine.record("render", 100.0, number)
    assert engine.budget()["passes"]["render"]["spikes"] == 1


def test_two_spike_frames_are_not_enough():
    engine = gov()
    for number in range(5):
        engine.record("render", 5.0, number)
    for number in range(5, 7):
        engine.record("render", 100.0, number)
    assert engine.budget()["passes"]["render"]["spikes"] == 0


def test_duplicate_pass_frame_is_rejected():
    engine = gov()
    engine.record("render", 10.0, 1)
    with pytest.raises(ValueError):
        engine.record("render", 11.0, 1)


def test_negative_duration_is_rejected():
    with pytest.raises(ValueError):
        gov().record("render", -1.0, 1)


def test_unknown_pass_is_rejected():
    with pytest.raises(ValueError):
        gov().record("physics", 10.0, 1)


def test_three_over_budget_frames_downscale():
    engine = gov()
    for number in range(3):
        frame(engine, number, render=10.0, logic=5.0, other=3.0)
    assert engine.target(0)["scale"] == pytest.approx(0.9)


def test_two_over_budget_frames_do_not_downscale():
    engine = gov()
    for number in range(2):
        frame(engine, number, render=10.0, logic=5.0, other=3.0)
    assert engine.target(0)["scale"] == pytest.approx(1.0)


def test_scale_never_goes_below_half():
    engine = gov()
    for number in range(30):
        frame(engine, number, render=10.0, logic=5.0, other=3.0)
    assert engine.target(0)["scale"] == pytest.approx(0.5)


def test_one_hundred_twenty_stable_frames_upscale():
    engine = gov()
    for number in range(10):
        frame(engine, number, render=10.0, logic=5.0, other=3.0)
    for number in range(10, 130):
        frame(engine, number, render=10.0, logic=5.0, other=1.0)
    assert engine.target(0)["scale"] == pytest.approx(0.8)


def test_target_cuts_low_priority_pass_first():
    engine = gov()
    for number in range(3):
        frame(engine, number, render=10.0, logic=5.0, other=3.0)
    assert "other" in engine.target(0)["cut"]


def test_budget_reports_all_passes():
    engine = gov()
    frame(engine, 1)
    passes = engine.budget()["passes"]
    assert set(passes) == {"render", "logic", "other"}


def test_budget_starts_at_full_scale():
    assert gov().target(0)["scale"] == pytest.approx(1.0)


def test_exact_budget_is_not_over_budget():
    engine = gov()
    for number in range(3):
        frame(engine, number, render=10.0, logic=5.0, other=1.6)
    assert engine.target(0)["scale"] == pytest.approx(1.0)
