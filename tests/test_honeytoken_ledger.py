import pytest

import honeytoken_ledger as hl

FAMILIES = {"aws_key": 3, "url": 2, "doc": 2, "db": 3}


def ledger():
    return hl.CanaryLedger()


def minted(game=None, family="aws_key", ttl=600, ts=0):
    game = game or ledger()
    return game, game.mint(family, "alice", ttl, ts)


def test_mark_has_prefix_and_checksum():
    _, mark = minted()
    assert mark.startswith("cnry_aws_key_")
    assert len(mark.rsplit("_", 1)[-1]) == 28


def test_unknown_family_is_rejected():
    with pytest.raises(ValueError):
        ledger().mint("mail", "alice", 60, 0)


def test_ttl_bounds_are_enforced():
    with pytest.raises(ValueError):
        ledger().mint("url", "alice", 0, 0)
    with pytest.raises(ValueError):
        ledger().mint("url", "alice", 86401, 0)


def test_touch_alerts_with_family_severity():
    game, mark = minted()
    result = game.touch(mark, "crawler", "t1", 10)
    assert result["status"] == "alive"
    assert result["severity"] == 3


def test_same_caller_is_deduplicated_within_ten_minutes():
    game, mark = minted()
    game.touch(mark, "crawler", "t1", 10)
    result = game.touch(mark, "crawler", "t1", 20)
    assert result["deduplicated"] is True


def test_cross_tenant_use_raises_severity():
    game, mark = minted()
    first = game.touch(mark, "crawler", "t1", 10)
    second = game.touch(mark, "other", "t2", 700)
    assert second["severity"] == first["severity"] + 1


def test_revoked_mark_returns_revoked():
    game, mark = minted()
    game.revoke(mark, 10)
    assert game.touch(mark, "crawler", "t1", 20)["status"] == "revoked"


def test_expired_mark_returns_expired():
    game, mark = minted(ttl=10)
    assert game.touch(mark, "crawler", "t1", 20)["status"] == "expired"


def test_rotation_has_grace_period():
    game, mark = minted(ttl=3600)
    game.rotate("aws_key", 10)
    assert game.touch(mark, "crawler", "t1", 100)["status"] == "alive"
    assert game.touch(mark, "crawler", "t1", 700)["status"] == "expired"


def test_report_aggregates_by_mark():
    game, mark = minted()
    game.touch(mark, "a", "t1", 10)
    game.touch(mark, "b", "t1", 20)
    rows = game.report(3600)
    assert rows[0]["count"] == 2


def test_summary_has_no_secret_text():
    game, mark = minted()
    game.touch(mark, "crawler", "t1", 10)
    info = game.summary()
    assert info["marks"] == 1
    assert "cnry_" not in str(info)


def test_malformed_mark_is_rejected():
    with pytest.raises(ValueError):
        ledger().touch("cnry_bad", "a", "t1", 0)


def test_unknown_mark_is_rejected():
    game = ledger()
    with pytest.raises(ValueError):
        game.touch("cnry_url_" + "0" * 28, "a", "t1", 0)


def test_report_returns_copy():
    game, mark = minted()
    game.touch(mark, "a", "t1", 0)
    rows = game.report(3600)
    rows.clear()
    assert game.report(3600)


def test_family_severity_mapping():
    game = ledger()
    _, url_mark = minted(game, "url")
    assert game.touch(url_mark, "a", "t1", 0)["severity"] == 2
