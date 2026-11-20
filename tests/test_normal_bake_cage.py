import pytest

import normal_bake_cage as nb


def mesh(count=3, degenerate=False):
    vertices = [(float(i), 0.0, 0.0) for i in range(count)]
    uvs = [(0.0 if degenerate else float(i), 0.0) for i in range(count)]
    return {
        "vertices": vertices,
        "uvs": uvs,
        "normals": [(0.0, 0.0, 1.0) for _ in range(count)],
        "triangles": [[0, 1, 2]] if count >= 3 else [],
    }


def cage(count=3, thickness=0.1):
    return {"vertices": [(float(i), 0.0, -0.1) for i in range(count)], "thickness": thickness}


def baker():
    return nb.NormalBaker(padding=2, green_flip=False)


def test_bake_returns_texture_and_misses():
    result = baker().bake(mesh(), mesh(), cage(), 8)
    assert result["texture"]
    assert result["misses"] >= 0


def test_samples_must_be_between_one_and_sixty_four():
    with pytest.raises(ValueError):
        baker().bake(mesh(), mesh(), cage(), 0)
    with pytest.raises(ValueError):
        baker().bake(mesh(), mesh(), cage(), 65)


def test_empty_mesh_is_rejected():
    empty = {"vertices": [], "uvs": [], "normals": [], "triangles": []}
    with pytest.raises(ValueError):
        baker().bake(empty, mesh(), cage(0), 4)


def test_cage_vertex_count_must_match_low_mesh():
    with pytest.raises(ValueError):
        baker().bake(mesh(), mesh(), cage(4), 4)


def test_degenerate_uv_is_rejected():
    with pytest.raises(ValueError):
        baker().bake(mesh(), mesh(degenerate=True), cage(), 4)


def test_padding_is_configurable():
    game = nb.NormalBaker(padding=4)
    game.bake(mesh(), mesh(), cage(), 4)
    assert game.inspect()["padding"] == 4


def test_green_flip_is_configurable():
    game = nb.NormalBaker(green_flip=True)
    game.bake(mesh(), mesh(), cage(), 4)
    assert game.inspect()["green_flip"] is True


def test_cage_thickness_must_be_positive():
    with pytest.raises(ValueError):
        baker().bake(mesh(), mesh(), cage(thickness=0), 4)


def test_missing_low_normals_is_rejected():
    low = mesh()
    low["normals"] = []
    with pytest.raises(ValueError):
        baker().bake(mesh(), low, cage(), 4)


def test_bake_is_deterministic():
    first = baker().bake(mesh(), mesh(), cage(), 8)
    second = baker().bake(mesh(), mesh(), cage(), 8)
    assert first["texture"]
    assert first == second


def test_inspect_reports_resolution_and_samples():
    game = baker()
    game.bake(mesh(), mesh(), cage(), 16)
    info = game.inspect()
    assert info["samples"] == 16
    assert info["resolution"] > 0


def test_inspect_reports_miss_rate():
    game = baker()
    game.bake(mesh(), mesh(), cage(), 4)
    info = game.inspect()
    assert 0.0 <= info["miss_rate"] <= 1.0


def test_inspect_returns_copy():
    game = baker()
    game.bake(mesh(), mesh(), cage(), 4)
    snap = game.inspect()
    snap["samples"] = 99
    assert game.inspect()["samples"] == 4


def test_texture_is_rectangular():
    result = baker().bake(mesh(), mesh(), cage(), 4)
    assert len(result["texture"][0]) == len(result["texture"][-1])


def test_sixty_four_samples_are_accepted():
    result = baker().bake(mesh(), mesh(), cage(), 64)
    assert result["texture"]
