import pytest

import csp_report_ingest as ci


def legacy(document="https://a.example.com/page", blocked="https://evil.example.net/x", directive="script-src"):
    return {"csp-report": {"document-uri": document, "blocked-uri": blocked, "violated-directive": directive}}


def report_to(document="https://a.example.com/page", blocked="https://evil.example.net/x", directive="script-src"):
    return [{"type": "csp-violation", "body": {"document-uri": document, "blocked-uri": blocked, "effective-directive": directive}}]


def sink(limit=100):
    return ci.CspReportSink(per_host_limit=limit)


def test_legacy_report_is_accepted():
    game = sink()
    game.ingest([legacy()], 1000)
    assert game.violations()["received"] == 1


def test_report_to_format_is_accepted():
    game = sink()
    game.ingest(report_to(), 1000)
    assert game.violations()["unique"] == 1


def test_query_string_does_not_defeat_deduplication():
    game = sink()
    game.ingest([legacy(blocked="https://evil.example.net/x?a=1")], 1000)
    game.ingest([legacy(blocked="https://evil.example.net/x?a=2")], 1000)
    assert game.violations()["unique"] == 1


def test_repeated_violation_aggregates_count():
    game = sink()
    game.ingest([legacy()], 1000)
    game.ingest([legacy()], 1000)
    assert game.summary(1)[0]["count"] == 2


def test_missing_field_is_skipped():
    game = sink()
    game.ingest([{"csp-report": {"document-uri": "https://a.example.com"}}], 1000)
    assert game.violations()["dropped"] == 1


def test_oversized_report_is_dropped():
    game = sink()
    game.ingest([legacy(blocked="https://evil.example.net/" + "x" * 9000)], 1000)
    assert game.violations()["dropped"] == 1


def test_future_timestamp_is_dropped():
    game = sink()
    body = legacy()
    body["csp-report"]["timestamp"] = 2000
    game.ingest([body], 1000)
    assert game.violations()["dropped"] == 1


def test_too_old_timestamp_is_dropped():
    game = sink()
    body = legacy()
    body["csp-report"]["timestamp"] = 0
    game.ingest([body], 100000)
    assert game.violations()["dropped"] == 1


def test_directive_aliases_are_merged():
    game = sink()
    game.ingest([legacy(directive="script-src")], 1000)
    game.ingest([report_to(directive="script-src")], 1000)
    assert game.violations()["unique"] == 1


def test_per_host_limit_drops_extra():
    game = sink(limit=1)
    game.ingest([legacy(blocked="https://a.example.net")], 1000)
    game.ingest([legacy(blocked="https://b.example.net")], 1000)
    assert game.violations()["dropped"] == 1


def test_summary_sorts_by_count_then_key():
    game = sink()
    game.ingest([legacy(blocked="https://a.example.net")], 1000)
    game.ingest([legacy(blocked="https://a.example.net")], 1000)
    game.ingest([legacy(blocked="https://b.example.net")], 1000)
    rows = game.summary(2)
    assert rows[0]["count"] == 2


def test_one_bad_record_does_not_drop_batch():
    game = sink()
    game.ingest([legacy(), {"csp-report": {}}], 1000)
    assert game.violations()["unique"] == 1


def test_unknown_fields_are_ignored():
    game = sink()
    body = legacy()
    body["csp-report"]["extra"] = "ignored"
    game.ingest([body], 1000)
    assert game.violations()["unique"] == 1


def test_violations_returns_copy():
    game = sink()
    game.ingest([legacy()], 1000)
    snap = game.violations()
    snap["received"] = 99
    assert game.violations()["received"] == 1


def test_summary_returns_copy():
    game = sink()
    game.ingest([legacy()], 1000)
    rows = game.summary(1)
    rows.clear()
    assert game.summary(1)
