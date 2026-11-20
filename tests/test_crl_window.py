import pytest

import crl_window as cw


def crl(number, this_update, next_update, entries, issuer="CN=CA", critical=None):
    return {
        "issuer": issuer,
        "this_update": this_update,
        "next_update": next_update,
        "crl_number": number,
        "critical_extensions": list(critical or []),
        "entries": entries,
    }


def base(entries=None, issuer="CN=CA"):
    return crl(5, 100, 200, entries or [{"serial": "0A1B", "reason": "keyCompromise"}], issuer)


def test_check_reports_revoked_serial():
    window = cw.RevocationWindow()
    window.load(base(), None, 160)
    result = window.check("0A1B", "CN=CA", 160)
    assert result["revoked"] is True
    assert result["reason"] == "keyCompromise"


def test_serial_comparison_is_case_insensitive():
    window = cw.RevocationWindow()
    window.load(base(), None, 160)
    assert window.check("a1b", "CN=CA", 160)["revoked"] is True


def test_serial_leading_zeroes_are_ignored():
    window = cw.RevocationWindow()
    window.load(base([{"serial": "00FF", "reason": "superseded"}]), None, 160)
    assert window.check("0ff", "CN=CA", 160)["revoked"] is True


def test_remove_from_crl_unrevokes_base_entry():
    window = cw.RevocationWindow()
    delta = crl(6, 150, 250, [{"serial": "0A1B", "reason": "removeFromCRL"}])
    delta["base_number"] = 5
    window.load(base(), delta, 160)
    result = window.check("0A1B", "CN=CA", 160)
    assert result["revoked"] is False
    assert result["reason"] is None


def test_delta_can_add_revocation():
    window = cw.RevocationWindow()
    delta = crl(6, 150, 250, [{"serial": "BEEF", "reason": "cessation"}])
    delta["base_number"] = 5
    window.load(base(), delta, 160)
    assert window.check("beef", "CN=CA", 160)["revoked"] is True


def test_delta_base_number_mismatch_is_rejected():
    window = cw.RevocationWindow()
    delta = crl(6, 150, 250, [{"serial": "BEEF", "reason": "cessation"}])
    delta["base_number"] = 4
    with pytest.raises(ValueError):
        window.load(base(), delta, 160)


def test_delta_older_than_base_is_rejected():
    window = cw.RevocationWindow()
    delta = crl(6, 90, 250, [{"serial": "BEEF", "reason": "cessation"}])
    delta["base_number"] = 5
    with pytest.raises(ValueError):
        window.load(base(), delta, 160)


def test_expired_base_is_not_extended_by_fresh_delta():
    window = cw.RevocationWindow()
    delta = crl(6, 150, 400, [{"serial": "BEEF", "reason": "cessation"}])
    delta["base_number"] = 5
    window.load(base(), delta, 160)
    with pytest.raises(ValueError):
        window.check("BEEF", "CN=CA", 260)


def test_future_this_update_is_rejected():
    window = cw.RevocationWindow()
    window.load(base(), None, 160)
    with pytest.raises(ValueError):
        window.check("0A1B", "CN=CA", 90)


def test_next_update_boundary_is_still_valid():
    window = cw.RevocationWindow()
    window.load(base(), None, 160)
    assert window.check("0A1B", "CN=CA", 200)["revoked"] is True


def test_issuer_must_match_exactly():
    window = cw.RevocationWindow()
    window.load(base(), None, 160)
    with pytest.raises(ValueError):
        window.check("0A1B", "CN=CA-OTHER", 160)


def test_unknown_critical_extension_is_rejected():
    window = cw.RevocationWindow()
    with pytest.raises(ValueError):
        window.load(base(critical=["1.2.3.4"]), None, 160)


def test_conflicting_duplicate_serials_are_rejected():
    window = cw.RevocationWindow()
    entries = [
        {"serial": "0A1B", "reason": "keyCompromise"},
        {"serial": "0a1b", "reason": "superseded"},
    ]
    with pytest.raises(ValueError):
        window.load(base(entries), None, 160)


def test_negative_serial_and_empty_issuer_are_rejected():
    window = cw.RevocationWindow()
    window.load(base(), None, 160)
    with pytest.raises(ValueError):
        window.check("-1", "CN=CA", 160)
    with pytest.raises(ValueError):
        window.check("0A1B", "", 160)


def test_window_reports_entries_and_effective_date():
    window = cw.RevocationWindow()
    window.load(base([{"serial": "CC", "reason": "cessation", "invalidity_date": 150}]), None, 160)
    info = window.window()
    assert info["entries"] == 1
    assert info["this_update"] == 100
    assert info["next_update"] == 200
    assert window.check("CC", "CN=CA", 160)["effective_at"] == 150
