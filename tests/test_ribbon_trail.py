import pytest

import ribbon_trail as rt

CURVE = [1.0, 0.8, 0.6, 0.0]


def pool(**over):
    args = {"lifetime": 1.0, "spacing": 0.1, "width_curve": list(CURVE), "capacity": 32}
    args.update(over)
    return rt.TrailPool(**args)


def camera():
    return {"position": (0.0, 0.0, 5.0), "up": (0.0, 1.0, 0.0)}


def test_emit_starts_a_trail():
    trail = pool()
    trail.start_trail(0)
    trail.emit((0.0, 0.0, 0.0), 0)
    info = trail.snapshot()
    assert info["active"] == 1
    assert info["points"] == 1


def test_spacing_interpolates_points():
    trail = pool()
    trail.start_trail(0)
    trail.emit((0.0, 0.0, 0.0), 0)
    trail.emit((0.25, 0.0, 0.0), 0)
    assert trail.snapshot()["points"] == 4


def test_short_segment_has_no_extra_points():
    trail = pool()
    trail.start_trail(0)
    trail.emit((0.0, 0.0, 0.0), 0)
    trail.emit((0.05, 0.0, 0.0), 0)
    assert trail.snapshot()["points"] == 2


def test_width_curve_hits_both_ends():
    trail = pool()
    tid = trail.start_trail(0)
    trail.emit((0.0, 0.0, 0.0), 0)
    trail.emit((1.0, 0.0, 0.0), 0)
    points = trail.inspect(tid)["points"]
    assert points[0]["width"] == pytest.approx(1.0)
    assert points[-1]["width"] == pytest.approx(0.0)


def test_uv_runs_from_zero_to_one():
    trail = pool()
    tid = trail.start_trail(0)
    trail.emit((0.0, 0.0, 0.0), 0)
    trail.emit((1.0, 0.0, 0.0), 0)
    points = trail.inspect(tid)["points"]
    assert points[0]["v"] == pytest.approx(0.0)
    assert points[-1]["v"] == pytest.approx(1.0)


def test_build_returns_vertex_and_index_counts():
    trail = pool()
    trail.start_trail(0)
    trail.emit((0.0, 0.0, 0.0), 0)
    trail.emit((0.25, 0.0, 0.0), 0)
    built = trail.build(camera())
    assert built["vertices"] == 8
    assert built["indices"] == 18


def test_trail_expires_after_lifetime():
    trail = pool()
    trail.start_trail(0)
    trail.emit((0.0, 0.0, 0.0), 0)
    trail.update(2.0)
    assert trail.snapshot()["active"] == 0


def test_trail_survives_before_lifetime():
    trail = pool()
    trail.start_trail(0)
    trail.emit((0.0, 0.0, 0.0), 0)
    trail.update(0.5)
    assert trail.snapshot()["active"] == 1


def test_pool_evicts_oldest_trail():
    trail = pool(capacity=2)
    first = trail.start_trail(0)
    trail.start_trail(0)
    trail.start_trail(0)
    info = trail.snapshot()
    assert info["active"] == 2
    assert first not in info["trail_ids"]


def test_snapshot_reports_evictions():
    trail = pool(capacity=1)
    trail.start_trail(0)
    trail.start_trail(0)
    assert trail.snapshot()["evicted"] == 1


def test_paused_update_does_not_age_trail():
    trail = pool()
    trail.start_trail(0)
    trail.emit((0.0, 0.0, 0.0), 0)
    trail.update(0)
    trail.update(0)
    assert trail.snapshot()["active"] == 1


def test_width_curve_needs_four_points():
    with pytest.raises(ValueError):
        rt.TrailPool(lifetime=1.0, spacing=0.1, width_curve=[1.0, 0.0], capacity=4)


def test_zero_spacing_is_rejected():
    with pytest.raises(ValueError):
        rt.TrailPool(lifetime=1.0, spacing=0.0, width_curve=list(CURVE), capacity=4)


def test_negative_lifetime_is_rejected():
    with pytest.raises(ValueError):
        rt.TrailPool(lifetime=-1.0, spacing=0.1, width_curve=list(CURVE), capacity=4)


def test_empty_point_is_rejected():
    trail = pool()
    trail.start_trail(0)
    with pytest.raises(ValueError):
        trail.emit((), 0)
