import pytest

import housing_plot_grid as hg


def item(iid="chair", w=1, h=1, door="south"):
    return {"id": iid, "w": w, "h": h, "door": door}


def grid():
    return hg.PlotGrid()


def test_place_adds_item():
    game = grid()
    game.place("p1", item(), 0, 0, 0)
    assert game.plot_view("p1")["items"]


def test_rotation_swaps_width_and_height():
    game = grid()
    game.place("p1", item(w=2, h=1), 0, 0, 90)
    assert game.plot_view("p1")["items"][0]["w"] == 1
    assert game.plot_view("p1")["items"][0]["h"] == 2


def test_overlap_is_rejected():
    game = grid()
    game.place("p1", item("a"), 0, 0, 0)
    with pytest.raises(ValueError):
        game.place("p1", item("b"), 0, 0, 0)


def test_out_of_bounds_is_rejected():
    with pytest.raises(ValueError):
        grid().place("p1", item(), 8, 0, 0)


def test_door_must_face_empty_cell():
    game = grid()
    game.place("p1", item(door="north"), 0, 0, 0)
    with pytest.raises(ValueError):
        game.place("p1", item("blocker", door="south"), 0, -1, 0)


def test_move_is_atomic():
    game = grid()
    game.place("p1", item(), 0, 0, 0)
    with pytest.raises(ValueError):
        game.move("p1", "chair", 100, 100)
    assert game.plot_view("p1")["items"][0]["x"] == 0


def test_remove_unknown_is_rejected():
    with pytest.raises(ValueError):
        grid().remove("p1", "ghost")


def test_expand_east_increases_width():
    game = grid()
    game.expand("p1", "east")
    assert game.plot_view("p1")["width"] > 8


def test_expand_south_increases_height():
    game = grid()
    game.expand("p1", "south")
    assert game.plot_view("p1")["height"] > 8


def test_expand_stops_at_sixteen():
    game = grid()
    for _ in range(20):
        game.expand("p1", "east")
    assert game.plot_view("p1")["width"] == 16


def test_capacity_is_fifty_items():
    game = grid()
    for index in range(50):
        game.place("p1", item(f"i{index}"), index % 8, index // 8, 0)
    with pytest.raises(ValueError):
        game.place("p1", item("extra"), 0, 7, 0)


def test_invalid_rotation_is_rejected():
    with pytest.raises(ValueError):
        grid().place("p1", item(), 0, 0, 45)


def test_unknown_plot_is_rejected():
    with pytest.raises(ValueError):
        grid().plot_view("ghost")


def test_plot_view_reports_occupancy():
    game = grid()
    game.place("p1", item(), 0, 0, 0)
    assert game.plot_view("p1")["occupied"] == 1


def test_plot_view_returns_copy():
    game = grid()
    game.place("p1", item(), 0, 0, 0)
    snap = game.plot_view("p1")
    snap["items"].clear()
    assert game.plot_view("p1")["items"]
