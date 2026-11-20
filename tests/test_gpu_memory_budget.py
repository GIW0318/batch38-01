import pytest

import gpu_memory_budget as gb


def budget(limit=4096):
    return gb.GpuBudget(limit)


def test_size_is_rounded_to_power_of_two_class():
    result = budget().alloc(300, "buffer", "x")
    assert result["size"] == 512
    assert result["offset"] == 0


def test_alloc_returns_unique_handles():
    game = budget()
    first = game.alloc(256, "buffer", "a")
    second = game.alloc(256, "buffer", "b")
    assert first["handle"] != second["handle"]


def test_budget_is_enforced():
    game = budget(limit=1024)
    game.alloc(1024, "texture", "big")
    with pytest.raises(ValueError):
        game.alloc(256, "texture", "more")


def test_lower_priority_is_evicted_first():
    game = budget(limit=1024)
    low = game.alloc(512, "transient", "low")
    game.alloc(512, "texture", "high")
    game.alloc(512, "texture", "new")
    with pytest.raises(ValueError):
        game.free(low["handle"])


def test_free_releases_memory():
    game = budget()
    handle = game.alloc(512, "buffer", "x")
    game.free(handle["handle"])
    assert game.usage()["used"] == 0


def test_double_free_is_rejected():
    game = budget()
    handle = game.alloc(256, "buffer", "x")
    game.free(handle["handle"])
    with pytest.raises(ValueError):
        game.free(handle["handle"])


def test_unknown_handle_is_rejected():
    with pytest.raises(ValueError):
        budget().free("ghost")


def test_negative_size_is_rejected():
    with pytest.raises(ValueError):
        budget().alloc(-1, "buffer", "x")


def test_transient_allocs_can_alias():
    game = budget()
    first = game.alloc(512, "transient", "a")
    second = game.alloc(512, "transient", "b")
    assert first["offset"] == second["offset"]
    assert game.usage()["used"] == 512


def test_fragmentation_is_reported():
    game = budget()
    game.alloc(256, "buffer", "a")
    game.alloc(256, "buffer", "b")
    game.free(game.alloc(256, "buffer", "c")["handle"])
    assert 0 <= game.usage()["fragmentation"] <= 1


def test_peak_usage_is_tracked():
    game = budget()
    game.alloc(1024, "texture", "a")
    game.free(game.alloc(512, "texture", "b")["handle"])
    assert game.usage()["peak"] >= 1024


def test_kind_totals_are_reported():
    game = budget()
    game.alloc(256, "texture", "a")
    game.alloc(512, "buffer", "b")
    totals = game.usage()["kinds"]
    assert totals["texture"] == 256
    assert totals["buffer"] == 512


def test_defrag_skips_pinned_blocks():
    game = budget()
    handle = game.alloc(512, "buffer", "pinned")
    game.pin(handle["handle"])
    game.alloc(256, "buffer", "free")
    game.defrag(0)
    assert game.usage()["used"] == 768


def test_defrag_compacts_unpinned_blocks():
    game = budget()
    first = game.alloc(256, "buffer", "a")
    second = game.alloc(256, "buffer", "b")
    game.free(first["handle"])
    game.defrag(0)
    assert game.usage()["fragmentation"] <= 1


def test_usage_returns_copy():
    game = budget()
    game.alloc(256, "buffer", "a")
    snap = game.usage()
    snap["used"] = 999
    assert game.usage()["used"] == 256
