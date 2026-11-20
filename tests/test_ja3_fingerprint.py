import hashlib
import re

import pytest

import ja3_fingerprint as jf


def hello(version=771, ciphers=None, extensions=None, curves=None, point_formats=None):
    return {
        "version": version,
        "ciphers": ciphers or [4865, 4866],
        "extensions": extensions or [0, 10, 11],
        "curves": curves or [29, 23],
        "point_formats": point_formats or [0],
    }


def policy(md5=None, action="deny", min_version=0):
    return [{"md5": md5, "action": action, "min_version": min_version}]


def test_fingerprint_is_lowercase_md5():
    fp = jf.Ja3Index().fingerprint(hello())
    assert re.fullmatch(r"[0-9a-f]{32}", fp)


def test_grease_is_ignored():
    game = jf.Ja3Index()
    plain = game.fingerprint(hello(ciphers=[4865, 0x0a0a, 4866]))
    assert re.fullmatch(r"[0-9a-f]{32}", plain)
    assert plain == game.fingerprint(hello(ciphers=[4865, 4866]))


def test_sni_alpn_padding_are_excluded():
    game = jf.Ja3Index()
    first = game.fingerprint(hello(extensions=[10, 11]))
    second = game.fingerprint(hello(extensions=[0, 10, 16, 11, 21]))
    assert re.fullmatch(r"[0-9a-f]{32}", first)
    assert first == second


def test_duplicate_extensions_keep_first():
    game = jf.Ja3Index()
    first = game.fingerprint(hello(extensions=[10, 11]))
    second = game.fingerprint(hello(extensions=[10, 10, 11, 11]))
    assert re.fullmatch(r"[0-9a-f]{32}", first)
    assert first == second


def test_empty_lists_are_stable():
    game = jf.Ja3Index()
    value = hello(ciphers=[], extensions=[], curves=[], point_formats=[])
    fp = game.fingerprint(value)
    assert re.fullmatch(r"[0-9a-f]{32}", fp)
    assert fp == game.fingerprint(value)


def test_unknown_version_is_rejected():
    with pytest.raises(ValueError):
        jf.Ja3Index().fingerprint(hello(version=700))


def test_negative_cipher_is_rejected():
    with pytest.raises(ValueError):
        jf.Ja3Index().fingerprint(hello(ciphers=[-1]))


def test_allow_policy_matches():
    game = jf.Ja3Index()
    fp = game.fingerprint(hello())
    result = game.match(policy(fp, "allow"))
    assert result["action"] == "allow"


def test_deny_policy_matches():
    game = jf.Ja3Index()
    fp = game.fingerprint(hello())
    assert game.match(policy(fp, "deny"))["action"] == "deny"


def test_challenge_policy_matches():
    game = jf.Ja3Index()
    fp = game.fingerprint(hello())
    assert game.match(policy(fp, "challenge"))["action"] == "challenge"


def test_min_version_must_hold():
    game = jf.Ja3Index()
    fp = game.fingerprint(hello(version=771))
    assert game.match(policy(fp, "allow", 772))["action"] == "default"


def test_duplicate_policy_is_rejected():
    game = jf.Ja3Index()
    fp = game.fingerprint(hello())
    game.add_policy({"md5": fp, "action": "deny", "min_version": 0})
    with pytest.raises(ValueError):
        game.add_policy({"md5": fp, "action": "allow", "min_version": 0})


def test_unknown_action_is_rejected():
    with pytest.raises(ValueError):
        jf.Ja3Index().add_policy({"md5": "0" * 32, "action": "drop", "min_version": 0})


def test_catalog_counts():
    game = jf.Ja3Index()
    fp = game.fingerprint(hello())
    game.match(policy(fp))
    game.add_policy({"md5": fp, "action": "deny", "min_version": 0})
    info = game.catalog()
    assert info["fingerprints"] == 1
    assert info["policies"] == 1


def test_catalog_returns_copy():
    game = jf.Ja3Index()
    game.add_policy({"md5": "0" * 32, "action": "deny", "min_version": 0})
    snap = game.catalog()
    snap["policies"] = 99
    assert game.catalog()["policies"] == 1
