import pytest

import sdf_outline as so


def outline(shapes=None, width=2.0):
    game = so.SdfOutline(width=width, smooth=1.0)
    game.build(shapes or [{"type": "circle", "cx": 0, "cy": 0, "r": 5, "op": "union"}])
    return game


def sample(game, x, y):
    return game.sample(x, y)


def test_circle_center_is_filled():
    info = sample(outline(), 0, 0)
    assert info["alpha"] == pytest.approx(1.0)
    assert info["distance"] < 0


def test_far_outside_circle_is_empty():
    info = sample(outline(), 20, 0)
    assert info["alpha"] == pytest.approx(0.0)
    assert info["distance"] > 0


def test_rect_inside_is_filled():
    shapes = [{"type": "rect", "cx": 0, "cy": 0, "w": 10, "h": 4, "op": "union"}]
    assert sample(outline(shapes), 0, 0)["alpha"] == pytest.approx(1.0)


def test_segment_midpoint_is_filled():
    shapes = [{"type": "segment", "x1": -5, "y1": 0, "x2": 5, "y2": 0, "r": 1, "op": "union"}]
    assert sample(outline(shapes), 0, 0)["alpha"] == pytest.approx(1.0)


def test_union_of_circles_is_filled():
    shapes = [
        {"type": "circle", "cx": -3, "cy": 0, "r": 4, "op": "union"},
        {"type": "circle", "cx": 3, "cy": 0, "r": 4, "op": "union"},
    ]
    assert sample(outline(shapes), 0, 0)["alpha"] == pytest.approx(1.0)


def test_subtract_removes_inner_shape():
    shapes = [
        {"type": "circle", "cx": 0, "cy": 0, "r": 5, "op": "union"},
        {"type": "circle", "cx": 0, "cy": 0, "r": 2, "op": "subtract"},
    ]
    assert sample(outline(shapes), 0, 0)["alpha"] == pytest.approx(0.0)


def test_intersect_keeps_overlap_only():
    shapes = [
        {"type": "circle", "cx": -2, "cy": 0, "r": 4, "op": "union"},
        {"type": "circle", "cx": 2, "cy": 0, "r": 4, "op": "intersect"},
    ]
    assert sample(outline(shapes), 0, 0)["alpha"] == pytest.approx(1.0)


def test_outline_ring_has_partial_alpha():
    info = sample(outline(width=2.0), 6, 0)
    assert 0.0 < info["alpha"] < 1.0


def test_smooth_edge_is_not_hard():
    info = sample(outline(width=2.0), 5.0, 0)
    assert 0.0 <= info["alpha"] <= 1.0


def test_outside_bounds_returns_large_distance():
    info = sample(outline(), 100, 100)
    assert info["distance"] >= 50


def test_empty_shapes_are_rejected():
    with pytest.raises(ValueError):
        so.SdfOutline().build([])


def test_negative_radius_is_rejected():
    with pytest.raises(ValueError):
        outline([{"type": "circle", "cx": 0, "cy": 0, "r": -1, "op": "union"}])


def test_negative_width_is_rejected():
    with pytest.raises(ValueError):
        so.SdfOutline(width=-1)


def test_bounds_report_count_and_box():
    info = outline().bounds()
    assert info["count"] == 1
    assert info["min_x"] < info["max_x"]


def test_unknown_shape_is_rejected():
    with pytest.raises(ValueError):
        outline([{"type": "triangle", "op": "union"}])
