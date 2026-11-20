import pytest

import midi_quantize as mq


def event(tick, kind, note=60, channel=0, velocity=100):
    return {"tick": tick, "type": kind, "channel": channel, "note": note, "velocity": velocity}


def notes():
    return [event(50, "note_on"), event(100, "note_off")]


def quantized(events=None, ppq=96, grid="1/4", swing=50):
    game = mq.MidiQuantize()
    return game, game.quantize(events or notes(), ppq, grid, swing)


def test_note_on_is_quantized():
    _, out = quantized()
    assert out[0]["tick"] == 96


def test_note_off_keeps_duration():
    _, out = quantized()
    assert out[1]["tick"] - out[0]["tick"] == 50


def test_eighth_grid():
    events = [event(30, "note_on"), event(60, "note_off")]
    _, out = quantized(events, grid="1/8")
    assert out[0]["tick"] == 48


def test_triplet_grid_uses_third():
    events = [event(40, "note_on"), event(80, "note_off")]
    _, out = quantized(events, grid="1/8T")
    assert out[0]["tick"] == 32


def test_swing_fifty_does_not_delay():
    events = [event(96, "note_on"), event(144, "note_off")]
    _, out = quantized(events, grid="1/8", swing=50)
    assert out[0]["tick"] == 96


def test_swing_delays_even_beats():
    events = [event(96, "note_on"), event(144, "note_off")]
    _, out = quantized(events, grid="1/8", swing=66)
    assert out[0]["tick"] > 96


def test_overlap_is_trimmed():
    events = [
        event(0, "note_on"),
        event(100, "note_off"),
        event(50, "note_on"),
        event(150, "note_off"),
    ]
    _, out = quantized(events, grid="1/4")
    ticks = [x["tick"] for x in out if x["type"] == "note_off"]
    assert 47 in ticks


def test_events_are_sorted():
    events = [event(100, "note_off"), event(50, "note_on")]
    _, out = quantized(events)
    assert out[0]["type"] == "note_on"


def test_ppq_zero_is_rejected():
    with pytest.raises(ValueError):
        quantized(ppq=0)


def test_invalid_grid_is_rejected():
    with pytest.raises(ValueError):
        quantized(grid="1/3")


def test_negative_tick_is_rejected():
    with pytest.raises(ValueError):
        quantized([event(-1, "note_on"), event(10, "note_off")])


def test_velocity_bounds_are_enforced():
    with pytest.raises(ValueError):
        quantized([event(0, "note_on", velocity=0), event(10, "note_off")])
    with pytest.raises(ValueError):
        quantized([event(0, "note_on", velocity=128), event(10, "note_off")])


def test_tracks_reports_counts():
    game, _ = quantized()
    info = game.tracks()
    assert info["events"] == 2


def test_tracks_returns_copy():
    game, _ = quantized()
    snap = game.tracks()
    snap["events"] = 99
    assert game.tracks()["events"] == 2


def test_unpaired_note_off_is_rejected():
    with pytest.raises(ValueError):
        quantized([event(10, "note_off")])
