import pytest

import weather_cycle as wc

ALLOWED = {
    ("clear", "cloud"),
    ("cloud", "rain"),
    ("cloud", "clear"),
    ("rain", "storm"),
    ("storm", "cloud"),
    ("cloud", "snow"),
    ("snow", "clear"),
}


def engine(seed=42, biome="forest", temp=10.0):
    return wc.WeatherEngine(seed, biome, temp)


def test_same_seed_is_deterministic():
    first = engine().at(1000)
    second = engine().at(1000)
    assert "weather" in first
    assert first == second


def test_different_seed_changes_weather():
    first = engine(1)
    second = engine(2)
    assert any(first.at(t) != second.at(t) for t in range(0, 100000, 300))


def test_at_reports_required_fields():
    info = engine().at(1000)
    assert info["weather"] in {"clear", "cloud", "rain", "storm", "snow"}
    assert info["remaining"] >= 0
    assert info["front_id"]
    assert isinstance(info["temp"], (int, float))


def test_advance_keeps_time_monotonic():
    game = engine()
    game.advance(100)
    assert game.at(100)["weather"] in {"clear", "cloud", "rain", "storm", "snow"}


def test_forecast_intervals_are_contiguous():
    intervals = engine().forecast(0, 3600)
    assert intervals
    for left, right in zip(intervals, intervals[1:]):
        assert left["end"] == right["start"]


def test_forecast_covers_horizon():
    intervals = engine().forecast(0, 3600)
    assert intervals[0]["start"] == 0
    assert intervals[-1]["end"] == 3600


def test_zero_horizon_is_rejected():
    with pytest.raises(ValueError):
        engine().forecast(0, 0)


def test_negative_horizon_is_rejected():
    with pytest.raises(ValueError):
        engine().forecast(0, -1)


def test_time_going_backwards_is_rejected():
    game = engine()
    game.advance(100)
    with pytest.raises(ValueError):
        game.advance(50)


def test_unknown_biome_is_rejected():
    with pytest.raises(ValueError):
        wc.WeatherEngine(1, "moon", 10.0)


def test_temperature_is_numeric_and_stable():
    assert engine(temp=-5.0).at(0)["temp"] == pytest.approx(-5.0, abs=2.0)


def test_history_transitions_are_allowed():
    states = [x["weather"] for x in engine().history(0, 200000)]
    assert states
    for left, right in zip(states, states[1:]):
        assert left == right or (left, right) in ALLOWED


def test_forecast_returns_copy():
    game = engine()
    intervals = game.forecast(0, 600)
    intervals[0]["weather"] = "hacked"
    assert game.forecast(0, 600)[0]["weather"] != "hacked"


def test_history_matches_at():
    game = engine()
    rows = game.history(0, 3000)
    assert rows
    for row in rows:
        assert row["weather"] == game.at(row["start"])["weather"]


def test_history_returns_copy():
    game = engine()
    rows = game.history(0, 600)
    rows.clear()
    assert game.history(0, 600)
