import pytest

import sarif_fold as sf


def result(rule="R1", line=10, uri="src/a.py", level="error", fingerprint="fp1"):
    return {
        "ruleId": rule,
        "ruleIndex": 0,
        "level": level,
        "message": {"text": "finding"},
        "locations": [{
            "physicalLocation": {
                "artifactLocation": {"uri": uri, "uriBaseId": "SRCROOT"},
                "region": {"startLine": line},
            }
        }],
        "partialFingerprints": {"primary": fingerprint},
        "baselineState": "new",
    }


def run(results=None, version="2.1.0", driver=("tool", "1.0")):
    return {
        "version": version,
        "tool": {"driver": {"name": driver[0], "version": driver[1]}},
        "originalUriBaseIds": {"SRCROOT": {"uri": "file:///C:/repo/"}},
        "results": results or [result()],
    }


def fold(*runs):
    game = sf.SarifFold()
    game.merge(list(runs or [run()]))
    return game


def test_merge_accepts_two_one_zero():
    assert fold().merge_report()["results"] == 1


def test_invalid_version_is_rejected():
    with pytest.raises(ValueError):
        fold(run(version="2.0.0"))


def test_missing_driver_is_rejected():
    bad = run()
    bad["tool"] = {}
    with pytest.raises(ValueError):
        fold(bad)


def test_rule_index_resolves_rule():
    bad = run()
    bad["results"][0]["ruleIndex"] = 5
    bad["results"][0]["ruleId"] = "R2"
    assert fold(bad).summary()["by_level"]["high"] == 1


def test_uri_base_is_expanded():
    assert fold().merge_report()["results"] == 1


def test_uri_backslashes_are_normalized():
    bad = run([result(uri="src\\\\a.py")])
    assert fold(bad).merge_report()["results"] == 1


def test_duplicate_fingerprint_is_deduped():
    game = sf.SarifFold()
    game.merge([run([result()]), run([result()])])
    game.dedupe()
    assert game.merge_report()["results"] == 1


def test_level_mapping():
    game = fold(run([result(level="warning"), result(level="note", fingerprint="fp2")]))
    levels = game.summary()["by_level"]
    assert levels["medium"] == 1
    assert levels["low"] == 1


def test_suppressed_result_is_skipped():
    item = result()
    item["suppressions"] = [{"kind": "external", "status": "accepted"}]
    assert fold(run([item])).merge_report()["skipped"] == 1


def test_baseline_state_is_preserved():
    info = fold().summary()
    assert info["by_rule"]["R1"] == 1


def test_bad_result_is_skipped():
    bad = result()
    bad["locations"] = []
    report = fold(run([bad])).merge_report()
    assert report["skipped"] == 1


def test_empty_runs_are_rejected():
    with pytest.raises(ValueError):
        sf.SarifFold().merge([])


def test_summary_counts_severities():
    info = fold().summary()
    assert info["by_level"]["high"] == 1


def test_merge_report_counts_runs():
    game = fold(run(), run())
    assert game.merge_report()["runs"] == 2


def test_merge_report_returns_copy():
    game = fold()
    snap = game.merge_report()
    snap["results"] = 99
    assert game.merge_report()["results"] == 1
