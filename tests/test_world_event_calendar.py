import pytest

import world_event_calendar as we


def event(eid="e1", start=100, end=400, timezone="UTC"):
    return {
        "id": eid,
        "start": start,
        "end": end,
        "timezone": timezone,
        "phases": [
            {"start": start, "end": 200, "name": "open"},
            {"start": 200, "end": 300, "name": "battle"},
            {"start": 300, "end": end, "name": "close"},
        ],
    }


def calendar():
    game = we.EventCalendar()
    game.add(event(), 0)
    return game


def test_add_registers_event():
    assert calendar().snapshot()["events"] == 1


def test_overlapping_events_are_rejected():
    game = calendar()
    with pytest.raises(ValueError):
        game.add(event("e2", 300, 500), 0)


def test_phases_must_cover_interval():
    bad = event()
    bad["phases"] = [{"start": 100, "end": 200, "name": "open"}]
    with pytest.raises(ValueError):
        we.EventCalendar().add(bad, 0)


def test_duplicate_event_id_is_rejected():
    game = calendar()
    with pytest.raises(ValueError):
        game.add(event(), 0)


def test_phase_returns_current_segment():
    assert calendar().phase("e1", 250) == "battle"


def test_cancel_marks_event_cancelled():
    game = calendar()
    game.cancel("e1", 150)
    assert game.phase("e1", 250) == "cancelled"


def test_cancelled_event_cannot_settle():
    game = calendar()
    game.cancel("e1", 150)
    with pytest.raises(ValueError):
        game.settle("e1", 500)


def test_settle_only_after_end_and_once():
    game = calendar()
    assert game.settle("e1", 500)["settled"] is True
    with pytest.raises(ValueError):
        game.settle("e1", 501)


def test_settle_before_end_is_rejected():
    with pytest.raises(ValueError):
        calendar().settle("e1", 399)


def test_cross_day_event_is_kept():
    game = we.EventCalendar()
    game.add({
        "id": "e1",
        "start": 86000,
        "end": 90000,
        "timezone": "UTC",
        "phases": [
            {"start": 86000, "end": 88000, "name": "open"},
            {"start": 88000, "end": 90000, "name": "battle"},
        ],
    }, 0)
    assert game.phase("e1", 88000) == "battle"


def test_start_must_be_before_end():
    with pytest.raises(ValueError):
        we.EventCalendar().add(event(start=500, end=500), 0)


def test_unknown_timezone_is_rejected():
    with pytest.raises(ValueError):
        we.EventCalendar().add(event(timezone="Mars/Base"), 0)


def test_unknown_event_is_rejected():
    with pytest.raises(ValueError):
        calendar().phase("ghost", 150)


def test_snapshot_counts_phases_and_next_event():
    game = calendar()
    info = game.snapshot()
    assert info["phase_counts"]["open"] == 1
    assert info["next_event"] == "e1"


def test_snapshot_returns_copy():
    game = calendar()
    snap = game.snapshot()
    snap["events"] = 99
    assert game.snapshot()["events"] == 1
