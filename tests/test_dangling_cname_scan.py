import pytest

import dangling_cname_scan as dc


def rec(name, typ, value, ttl=300, apex=False):
    return {"name": name, "type": typ, "value": value, "ttl": ttl, "apex": apex}


def audit(records, fingerprints=None):
    game = dc.CnameAudit()
    game.scan(records, fingerprints or [], 0)
    return game


def test_dangling_cname_is_reported():
    game = audit([rec("a.example.com", "CNAME", "bucket.s3.amazonaws.com")])
    info = game.risk("a.example.com")
    assert info["score"] == 60
    assert info["reason"] == "dangling"


def test_chain_ending_in_address_is_clean():
    game = audit([
        rec("a.example.com", "CNAME", "b.example.com"),
        rec("b.example.com", "A", "1.2.3.4"),
    ])
    assert game.digest()["scanned"] == 2
    assert game.risk("a.example.com") is None


def test_cname_loop_is_reported():
    game = audit([
        rec("a.example.com", "CNAME", "b.example.com"),
        rec("b.example.com", "CNAME", "a.example.com"),
    ])
    assert game.risk("a.example.com")["reason"] == "loop"


def test_apex_cname_is_conflict():
    game = audit([rec("example.com", "CNAME", "cdn.example.net", apex=True)])
    assert game.risk("example.com")["reason"] == "conflict"


def test_duplicate_cname_is_conflict():
    game = audit([
        rec("a.example.com", "CNAME", "x.example.net"),
        rec("a.example.com", "CNAME", "y.example.net"),
    ])
    assert game.risk("a.example.com")["reason"] == "conflict"


def test_cname_and_address_are_conflict():
    game = audit([
        rec("a.example.com", "CNAME", "x.example.net"),
        rec("a.example.com", "A", "1.2.3.4"),
    ])
    assert game.risk("a.example.com")["reason"] == "conflict"


def test_fingerprint_adds_weight():
    game = audit(
        [rec("a.example.com", "CNAME", "bucket.s3.amazonaws.com")],
        [{"suffix": "s3.amazonaws.com", "provider": "aws", "weight": 40}],
    )
    info = game.risk("a.example.com")
    assert info["score"] == 100
    assert info["provider"] == "aws"


def test_wildcard_record_is_skipped():
    game = audit([
        rec("*.example.com", "CNAME", "bucket.s3.amazonaws.com"),
        rec("a.example.com", "CNAME", "bucket.s3.amazonaws.com"),
    ])
    assert game.risk("a.example.com")["score"] == 60
    assert game.risk("*.example.com") is None


def test_zero_ttl_adds_risk():
    game = audit([rec("a.example.com", "CNAME", "bucket.s3.amazonaws.com", ttl=0)])
    assert game.risk("a.example.com")["score"] == 70


def test_digest_sorts_by_score_then_host():
    game = audit([
        rec("a.example.com", "CNAME", "bucket.s3.amazonaws.com", ttl=0),
        rec("b.example.com", "CNAME", "bucket.s3.amazonaws.com"),
    ])
    hosts = [x["host"] for x in game.digest()["high_risk"]]
    assert hosts == ["a.example.com", "b.example.com"]


def test_scan_reports_record_count():
    game = dc.CnameAudit()
    assert game.scan([
        rec("a.example.com", "CNAME", "b.example.com"),
        rec("b.example.com", "A", "1.2.3.4"),
        rec("c.example.com", "AAAA", "::1"),
    ], [], 0) == 3


def test_invalid_record_is_rejected():
    with pytest.raises(ValueError):
        audit([{"name": "a.example.com", "type": "CNAME"}])


def test_digest_returns_copy():
    game = audit([rec("a.example.com", "CNAME", "bucket.s3.amazonaws.com")])
    snap = game.digest()
    snap["high_risk"].clear()
    assert len(game.digest()["high_risk"]) == 1


def test_chain_longer_than_eight_is_reported():
    records = []
    for index in range(9):
        records.append(rec(f"n{index}.example.com", "CNAME", f"n{index + 1}.example.com"))
    game = audit(records)
    assert game.risk("n0.example.com")["reason"] == "too_deep"


def test_names_are_normalized():
    game = audit([rec("A.Example.COM.", "CNAME", "Bucket.S3.AmazonAWS.com.")])
    assert game.risk("a.example.com")["score"] == 60
