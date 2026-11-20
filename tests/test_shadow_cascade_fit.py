import pytest

import shadow_cascade_fit as sc


def camera(far=100.0, near=0.1, aspect=1.777):
    return {"near": near, "far": far, "fov": 60.0, "aspect": aspect}


def light(direction=(-0.3, -1.0, -0.2)):
    return {"direction": direction}


def fit():
    game = sc.CascadeFit()
    game.fit(light(), camera())
    return game


def test_splits_use_ratios():
    assert sc.CascadeFit().splits(camera()) == pytest.approx([10.0, 30.0, 60.0])


def test_splits_are_increasing():
    values = sc.CascadeFit().splits(camera())
    assert values[0] < values[1] < values[2]


def test_last_cascade_covers_far_plane():
    values = sc.CascadeFit().splits(camera(far=250.0))
    assert values[-1] == 250.0


def test_near_beyond_far_is_rejected():
    with pytest.raises(ValueError):
        sc.CascadeFit().splits(camera(far=1.0, near=2.0))


def test_zero_light_direction_is_rejected():
    with pytest.raises(ValueError):
        sc.CascadeFit().fit(light((0.0, 0.0, 0.0)), camera())


def test_negative_near_is_rejected():
    with pytest.raises(ValueError):
        sc.CascadeFit().splits(camera(near=-1.0))


def test_fit_returns_three_cascades():
    assert len(fit().cascades()) == 3


def test_cascade_centers_are_texel_aligned():
    cascades = fit().cascades()
    assert len(cascades) == 3
    for cascade in cascades:
        texel = cascade["texel"]
        assert abs(cascade["center"][0] / texel - round(cascade["center"][0] / texel)) < 1e-6
        assert abs(cascade["center"][1] / texel - round(cascade["center"][1] / texel)) < 1e-6


def test_light_direction_is_quantized():
    first = sc.CascadeFit()
    first.fit(light((-0.3001, -1.0, -0.2)), camera())
    second = sc.CascadeFit()
    second.fit(light((-0.30011, -1.0, -0.2)), camera())
    assert first.cascades()[0]["size"] == second.cascades()[0]["size"]


def test_adjacent_cascades_overlap():
    cascades = fit().cascades()
    for index in range(2):
        assert cascades[index]["far"] > cascades[index + 1]["near"]


def test_fit_is_deterministic():
    first = fit().cascades()
    second = fit().cascades()
    assert len(first) == 3
    assert first == second


def test_far_plane_changes_splits():
    small = sc.CascadeFit().splits(camera(far=100.0))
    large = sc.CascadeFit().splits(camera(far=200.0))
    assert large[-1] > small[-1]


def test_cascades_returns_copy():
    game = fit()
    snap = game.cascades()
    snap[0]["size"] = 999
    assert game.cascades()[0]["size"] != 999


def test_aspect_changes_bounds():
    wide = sc.CascadeFit()
    wide.fit(light(), camera(aspect=2.0))
    square = sc.CascadeFit()
    square.fit(light(), camera(aspect=1.0))
    assert wide.cascades()[0]["size"] != square.cascades()[0]["size"]


def test_light_from_below_still_fits():
    game = sc.CascadeFit()
    game.fit(light((0.0, 1.0, 0.0)), camera())
    cascades = game.cascades()
    assert len(cascades) == 3
    assert all(x["size"] > 0 for x in cascades)
