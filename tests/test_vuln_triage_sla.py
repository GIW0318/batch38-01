import pytest

import vuln_triage_sla as vts

MONDAY = 1704067200
DAY = 86400
JAN2 = MONDAY + DAY


def finding(cve="CVE-2024-0001", package="pkg", version="1.0.0", cvss=9.8,
            reachable=True, kev=False, kev_until=None):
    return {
        "cve": cve,
        "package": package,
        "version": version,
        "cvss": cvss,
        "reachable": reachable,
        "kev": kev,
        "kev_until": kev_until,
    }


def triage(holidays=None):
    return vts.VulnTriage(holidays)


def test_ingest_returns_id_and_opens_item():
    book = triage()
    assert book.ingest([finding()], MONDAY) == 1
    assert book.queue()["open"] == 1


def test_duplicate_key_returns_same_id():
    book = triage()
    first = book.ingest([finding()], MONDAY)
    second = book.ingest([finding()], MONDAY)
    assert first == 1
    assert second == 1
    assert book.queue()["open"] == 1


def test_cve_is_normalized_to_uppercase():
    book = triage()
    assert book.ingest([finding(cve="cve-2024-0001")], MONDAY) == 1
    assert book.ingest([finding(cve="CVE-2024-0001")], MONDAY) == 1


def test_same_cve_in_different_package_is_kept_separate():
    book = triage()
    book.ingest([finding(package="openssl")], MONDAY)
    book.ingest([finding(package="libcurl")], MONDAY)
    assert book.queue()["open"] == 2


def test_critical_sla_is_seven_business_days():
    book = triage()
    vuln_id = book.ingest([finding(cvss=9.8)], MONDAY)
    info = book.sla(vuln_id, MONDAY)
    assert info["severity"] == "critical"
    assert info["days"] == 7
    assert info["due_at"] == MONDAY + 9 * DAY


def test_cvss_bands_map_to_severities():
    book = triage()
    high = book.ingest([finding(cve="CVE-A", cvss=7.5)], MONDAY)
    medium = book.ingest([finding(cve="CVE-B", cvss=5.0)], MONDAY)
    low = book.ingest([finding(cve="CVE-C", cvss=3.0)], MONDAY)
    assert book.sla(high, MONDAY)["severity"] == "high"
    assert book.sla(medium, MONDAY)["severity"] == "medium"
    assert book.sla(low, MONDAY)["severity"] == "low"


def test_active_kev_forces_critical():
    book = triage()
    vuln_id = book.ingest([finding(cvss=3.0, kev=True, kev_until=MONDAY + DAY)], MONDAY)
    assert book.sla(vuln_id, MONDAY)["severity"] == "critical"


def test_expired_kev_does_not_force_critical():
    book = triage()
    vuln_id = book.ingest([finding(cvss=3.0, kev=True, kev_until=MONDAY - DAY)], MONDAY)
    assert book.sla(vuln_id, MONDAY)["severity"] == "low"


def test_unreachable_adds_thirty_days():
    book = triage()
    vuln_id = book.ingest([finding(cvss=7.5, reachable=False)], MONDAY)
    assert book.sla(vuln_id, MONDAY)["days"] == 44


def test_holiday_is_skipped_in_business_days():
    book = triage([JAN2])
    vuln_id = book.ingest([finding(cvss=9.8)], MONDAY)
    assert book.sla(vuln_id, MONDAY)["due_at"] == MONDAY + 10 * DAY


def test_exception_needs_another_approver_and_extends_due():
    book = triage()
    vuln_id = book.ingest([finding(cvss=9.8)], MONDAY)
    until = MONDAY + 100 * DAY
    book.request_exception(vuln_id, until, "alice", MONDAY)
    with pytest.raises(ValueError):
        book.approve_exception(vuln_id, "alice", MONDAY)
    book.approve_exception(vuln_id, "bob", MONDAY)
    assert book.sla(vuln_id, MONDAY)["due_at"] == until


def test_expired_exception_restores_original_sla():
    book = triage()
    vuln_id = book.ingest([finding(cvss=9.8)], MONDAY)
    until = MONDAY + 20 * DAY
    book.request_exception(vuln_id, until, "alice", MONDAY)
    book.approve_exception(vuln_id, "bob", MONDAY)
    assert book.sla(vuln_id, MONDAY)["due_at"] == until
    assert book.sla(vuln_id, MONDAY + 21 * DAY)["due_at"] == MONDAY + 9 * DAY


def test_close_then_reingest_reopens():
    book = triage()
    vuln_id = book.ingest([finding()], MONDAY)
    book.close(vuln_id, MONDAY, "fixed")
    assert book.queue()["open"] == 0
    again = book.ingest([finding()], MONDAY)
    assert again == vuln_id
    assert book.sla(vuln_id, MONDAY)["reopen_count"] == 1


def test_assignee_cap_is_twenty_open_items():
    book = triage()
    for index in range(20):
        vuln_id = book.ingest([finding(cve=f"CVE-{index:04d}")], MONDAY)
        book.assign(vuln_id, "bob", MONDAY)
    extra = book.ingest([finding(cve="CVE-9999")], MONDAY)
    with pytest.raises(ValueError):
        book.assign(extra, "bob", MONDAY)


def test_queue_counts_and_invalid_findings():
    book = triage()
    critical = book.ingest([finding(cve="CVE-A", cvss=9.8)], MONDAY)
    book.ingest([finding(cve="CVE-B", cvss=7.5)], MONDAY)
    book.request_exception(critical, MONDAY + 10 * DAY, "alice", MONDAY)
    queue = book.queue()
    assert queue["by_severity"]["critical"] == 1
    assert queue["by_severity"]["high"] == 1
    assert queue["pending_exceptions"] == 1
    with pytest.raises(ValueError):
        book.ingest([finding(cve="")], MONDAY)
    with pytest.raises(ValueError):
        book.ingest([finding(cvss=-1)], MONDAY)
    with pytest.raises(ValueError):
        book.ingest([finding(cvss="high")], MONDAY)
