import math

import pytest

import foliage_scatter as fs


def area(width=10, height=10, height_value=0.0, water=1, road=1):
    return {
        "width": width,
        "height": height,
        "heights": [[height_value for _ in range(width)] for _ in range(height)],
        "water": [[water for _ in range(width)] for _ in range(height)],
        "road": [[road for _ in range(width)] for _ in range(height)],
    }


def scattered(area_value=None, density=1.0, seed=1):
    game = fs.FoliageScatter()
    result = game.scatter(area_value or area(), density, seed)
    return game, result


def test_scatter_is_deterministic():
    _, first = scattered(seed=7)
    _, second = scattered(seed=7)
    assert first["instances"] >= 0
    assert first == second


def test_density_is_per_square_meter():
    _, low = scattered(density=1.0)
    _, high = scattered(density=4.0)
    assert high["instances"] > low["instances"]


def test_steep_slope_is_filtered():
    terrain = area()
    for y in range(10):
        for x in range(10):
            terrain["heights"][y][x] = 10.0 if x % 2 else 0.0
    _, result = scattered(terrain)
    assert result["filtered"] > 0


def test_water_mask_skips_cells():
    _, result = scattered(area(water=0))
    assert result["instances"] == 0


def test_road_mask_skips_cells():
    _, result = scattered(area(road=0))
    assert result["instances"] == 0


def test_minimum_spacing_is_respected():
    _, result = scattered(density=3.0)
    positions = [(x["x"], x["y"]) for x in result["instances"]]
    for index, (x, y) in enumerate(positions):
        for other_x, other_y in positions[index + 1:]:
            assert math.dist((x, y), (other_x, other_y)) >= 0.5 - 1e-9


def test_instance_budget_is_capped():
    _, result = scattered(area(width=200, height=200), density=1.0)
    assert result["instances"] <= 10000


def test_cull_reports_three_levels():
    game, _ = scattered()
    info = game.cull({"position": (0.0, 0.0), "far": 200.0})
    assert len(info["levels"]) == 3


def test_far_instances_are_removed():
    game, _ = scattered()
    near = game.cull({"position": (0.0, 0.0), "far": 100.0})
    far = game.cull({"position": (0.0, 0.0), "far": 200.0})
    assert near["visible"] <= far["visible"]


def test_wind_phase_is_deterministic():
    game, first = scattered(seed=3)
    _, second = scattered(seed=3)
    assert first["instances"][0]["phase"] == second["instances"][0]["phase"]
    assert 0 <= first["instances"][0]["phase"] <= 2 * math.pi


def test_negative_density_is_rejected():
    with pytest.raises(ValueError):
        fs.FoliageScatter().scatter(area(), -1.0, 1)


def test_empty_mask_is_rejected():
    bad = area()
    bad["water"] = []
    with pytest.raises(ValueError):
        fs.FoliageScatter().scatter(bad, 1.0, 1)


def test_size_mismatch_is_rejected():
    bad = area()
    bad["road"] = [[1 for _ in range(3)]]
    with pytest.raises(ValueError):
        fs.FoliageScatter().scatter(bad, 1.0, 1)


def test_scatter_returns_counts():
    _, result = scattered()
    assert result["instances"] > 0
    assert result["filtered"] >= 0


def test_ledger_returns_copy():
    game, _ = scattered()
    game.cull({"position": (0.0, 0.0), "far": 200.0})
    snap = game.ledger()
    snap["levels"][0] = 99
    assert game.ledger()["levels"][0] != 99
