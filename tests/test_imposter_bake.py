import pytest

import imposter_bake as ib


def mesh(count=8):
    return {
        "vertices": [(float(i), 0.0, 0.0) for i in range(count)],
        "bounds": {"radius": 2.0},
    }


def atlas(size=512):
    return {"width": size, "height": size}


def camera(height=0.2):
    return {"screen_height": height, "position": (0.0, 0.0, 10.0)}


def baker():
    game = ib.ImposterBaker()
    game.render_views(mesh(), 8, atlas())
    return game


def test_eight_views_are_accepted():
    info = baker().atlas_view()
    assert info["frames"] == 8


def test_sixteen_views_are_accepted():
    game = ib.ImposterBaker()
    game.render_views(mesh(), 16, atlas(1024))
    assert game.atlas_view()["frames"] == 16


def test_invalid_view_count_is_rejected():
    with pytest.raises(ValueError):
        ib.ImposterBaker().render_views(mesh(), 12, atlas())


def test_empty_mesh_is_rejected():
    with pytest.raises(ValueError):
        ib.ImposterBaker().render_views({"vertices": [], "bounds": {"radius": 1.0}}, 8, atlas())


def test_too_small_atlas_is_rejected():
    with pytest.raises(ValueError):
        ib.ImposterBaker().render_views(mesh(), 16, atlas(64))


def test_select_returns_frame():
    info = baker().select(camera(0.2))
    assert 0 <= info["frame"] < 8


def test_select_without_views_returns_minus_one():
    assert ib.ImposterBaker().select(camera())["frame"] == -1


def test_atlas_grid_uses_square_cells():
    info = baker().atlas_view()
    assert info["grid"] == 3


def test_padding_is_recorded():
    assert baker().atlas_view()["padding"] == 2


def test_alpha_threshold_is_recorded():
    assert baker().atlas_view()["alpha_threshold"] == pytest.approx(0.1)


def test_normals_are_octahedral():
    assert baker().atlas_view()["normal_encoding"] == "octahedral"


def test_lod_switch_has_hysteresis():
    game = baker()
    first = game.select(camera(0.25))["frame"]
    second = game.select(camera(0.24))["frame"]
    assert first == second


def test_depth_offset_is_radius_based():
    assert baker().atlas_view()["depth_offset"] == pytest.approx(0.02)


def test_atlas_view_returns_copy():
    game = baker()
    snap = game.atlas_view()
    snap["frames"] = 99
    assert game.atlas_view()["frames"] == 8


def test_version_increments_on_rebake():
    game = baker()
    before = game.atlas_view()["version"]
    game.render_views(mesh(), 8, atlas())
    assert game.atlas_view()["version"] == before + 1
