import pytest

import cvss_engine as ce

BASE = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
TEMPORAL = BASE + "/E:U/RL:O/RC:C"
ENV = BASE + "/MAV:L/MAC:H"


def test_base_vector_scores_nine_point_eight():
    assert ce.CvssEngine().score(BASE) == pytest.approx(9.8)


def test_severity_bands():
    game = ce.CvssEngine()
    assert game.severity(9.8) == "critical"
    assert game.severity(7.5) == "high"
    assert game.severity(5.0) == "medium"
    assert game.severity(2.0) == "low"
    assert game.severity(0.0) == "none"


def test_temporal_score_does_not_exceed_base():
    game = ce.CvssEngine()
    assert game.score(TEMPORAL) <= game.score(BASE)


def test_environmental_override_recalculates_base():
    game = ce.CvssEngine()
    assert game.score(ENV) < game.score(BASE)


def test_duplicate_metric_is_rejected():
    with pytest.raises(ValueError):
        ce.CvssEngine().score(BASE + "/AV:L")


def test_missing_metric_is_rejected():
    with pytest.raises(ValueError):
        ce.CvssEngine().score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H")


def test_unknown_metric_is_rejected():
    with pytest.raises(ValueError):
        ce.CvssEngine().score(BASE + "/ZZ:X")


def test_metric_order_does_not_change_score():
    game = ce.CvssEngine()
    first = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    second = "CVSS:3.1/A:H/I:H/C:H/S:U/UI:N/PR:N/AC:L/AV:N"
    score = game.score(first)
    assert isinstance(score, (int, float))
    assert score == game.score(second)


def test_score_has_one_decimal():
    score = ce.CvssEngine().score(BASE)
    assert round(score, 1) == score


def test_batch_deduplicates_but_keeps_total():
    result = ce.CvssEngine().batch([BASE, BASE, TEMPORAL])
    assert result["unique"] == 2
    assert result["total"] == 3


def test_batch_returns_one_score_per_unique_vector():
    result = ce.CvssEngine().batch([BASE, TEMPORAL])
    assert len(result["scores"]) == 2


def test_profile_change_invalidates_cache():
    game = ce.CvssEngine()
    game.score(TEMPORAL, {"temporal": True})
    before = game.cache_stats()["misses"]
    game.score(TEMPORAL, {"temporal": False})
    assert game.cache_stats()["misses"] == before + 1


def test_cache_records_hits():
    game = ce.CvssEngine()
    game.score(BASE)
    game.score(BASE)
    assert game.cache_stats()["hits"] == 1


def test_breakdown_returns_sub_scores():
    info = ce.CvssEngine().breakdown(ENV)
    assert set(info) == {"exploitability", "impact", "temporal", "environmental"}


def test_malformed_vector_is_rejected():
    with pytest.raises(ValueError):
        ce.CvssEngine().score("not-a-vector")
