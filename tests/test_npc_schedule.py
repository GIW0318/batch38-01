import pytest

import npc_schedule as ns

WEEK = 604800
DAY = 86400

BASE = [
    {"start": 0, "end": 3600, "waypoint": "gate", "activity": "patrol"},
    {"start": 3600, "end": 7200, "waypoint": "market", "activity": "trade"},
]


def week(day0=None):
    return [day0 or [] for _ in range(7)]


def board(day0=None, npc="guard"):
    table = ns.ScheduleBoard()
    table.assign_week(npc, week(day0 if day0 is not None else BASE))
    return table


def test_status_reports_base_segment():
    info = board().status("guard", 1000)
    assert info["activity"] == "patrol"
    assert info["waypoint"] == "gate"
    assert info["remaining"] == 2600
    assert info["next_start"] == 3600
    assert info["source"] == "base"


def test_cross_midnight_segment_late_and_early():
    night = [{"start": 82800, "end": 7200, "waypoint": "inn", "activity": "sleep"}]
    table = board(night, "innkeeper")
    late = table.status("innkeeper", 85000)
    early = table.status("innkeeper", DAY + 3600)
    assert late["activity"] == "sleep"
    assert late["remaining"] == 8600
    assert early["activity"] == "sleep"
    assert early["remaining"] == 3600


def test_overlapping_segments_are_rejected():
    bad = [
        {"start": 0, "end": 3600, "waypoint": "a", "activity": "patrol"},
        {"start": 1800, "end": 5400, "waypoint": "b", "activity": "trade"},
    ]
    with pytest.raises(ValueError):
        board(bad)


def test_invalid_activity_is_rejected():
    bad = [{"start": 0, "end": 3600, "waypoint": "a", "activity": "fight"}]
    with pytest.raises(ValueError):
        board(bad)


def test_negative_time_is_rejected():
    with pytest.raises(ValueError):
        board().status("guard", -1)


def test_unknown_npc_is_rejected():
    with pytest.raises(ValueError):
        board().status("ghost", 0)


def test_override_takes_precedence_in_window():
    table = board()
    table.override("guard", (1000, 2000), "trade", 2, 100)
    info = table.status("guard", 1500)
    assert info["activity"] == "trade"
    assert info["source"] == "override"
    assert table.status("guard", 2500)["source"] == "base"


def test_override_priority_and_creation_order():
    table = board()
    table.override("guard", (1000, 2000), "sleep", 1, 100)
    table.override("guard", (1000, 2000), "trade", 3, 200)
    assert table.status("guard", 1500)["activity"] == "trade"
    table.override("guard", (1000, 2000), "eat", 3, 300)
    assert table.status("guard", 1500)["activity"] == "eat"


def test_override_cannot_cross_week_boundary():
    table = board()
    with pytest.raises(ValueError):
        table.override("guard", (WEEK - 800, WEEK + 200), "trade", 1, 0)


def test_interrupt_records_reason_and_remaining():
    info = board().interrupt("guard", "combat", 1000)
    assert info["reason"] == "combat"
    assert info["remaining"] == 2600


def test_status_reports_interrupted_state():
    table = board()
    table.interrupt("guard", "combat", 1000)
    info = table.status("guard", 1000)
    assert info["source"] == "interrupted"
    assert info["reason"] == "combat"


def test_resume_continues_from_breakpoint():
    table = board()
    table.interrupt("guard", "combat", 1000)
    info = table.resume("guard", 1500)
    assert info["activity"] == "patrol"
    assert info["remaining"] == 2100
    assert table.status("guard", 1600)["remaining"] == 2000


def test_resume_past_segment_end_advances():
    table = board()
    table.interrupt("guard", "combat", 3500)
    info = table.resume("guard", 3800)
    assert info["activity"] == "trade"
    assert info["remaining"] == 3400


def test_resume_without_interrupt_is_rejected():
    with pytest.raises(ValueError):
        board().resume("guard", 1000)


def test_export_returns_isolated_copy():
    table = board()
    data = table.export()
    assert data["week"] == 0
    data["plans"]["guard"][0][0]["activity"] = "hacked"
    assert table.export()["plans"]["guard"][0][0]["activity"] == "patrol"
