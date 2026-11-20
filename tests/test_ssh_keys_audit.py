import base64
import hashlib

import pytest

import ssh_keys_audit as sk

BLOB = base64.b64encode(b"ed25519-key-material").decode()
FP = hashlib.sha256(b"ed25519-key-material").hexdigest()


def line(options="", key_type="ssh-ed25519", comment="alice@host"):
    prefix = options + " " if options else ""
    return f"{prefix}{key_type} {BLOB} {comment}"


def audit(text, policy=None, now=20260101):
    game = sk.KeyAudit()
    game.parse(text)
    game.audit(policy or {}, now)
    return game.findings()


def codes(findings):
    return [x["code"] for x in findings]


def test_parse_simple_key():
    game = sk.KeyAudit()
    assert game.parse(line()) == 1


def test_command_with_spaces_is_quoted():
    text = 'command="echo hello world",no-pty ssh-ed25519 ' + BLOB + " alice@host"
    assert sk.KeyAudit().parse(text) == 1


def test_comma_inside_quotes_does_not_split():
    text = 'command="a,b",no-pty ssh-ed25519 ' + BLOB + " alice@host"
    assert sk.KeyAudit().parse(text) == 1


def test_from_option_is_parsed():
    text = 'from="10.0.0.1,10.0.0.2" ssh-ed25519 ' + BLOB + " alice@host"
    assert sk.KeyAudit().parse(text) == 1


def test_expired_key_is_reported():
    text = 'expiry-time="20200101" ssh-ed25519 ' + BLOB + " alice@host"
    assert "expired" in codes(audit(text))


def test_duplicate_fingerprint_across_users_is_reported():
    text = line(comment="alice@host") + "\n" + line(comment="bob@host") + "\n"
    assert "duplicate" in codes(audit(text))


def test_revoked_fingerprint_is_reported():
    findings = audit(line(), {"revoked": [FP]})
    assert "revoked" in codes(findings)


def test_cert_authority_is_recognized():
    text = 'cert-authority ssh-ed25519 ' + BLOB + " alice@host"
    assert sk.KeyAudit().parse(text) == 1


def test_bad_base64_is_skipped():
    game = sk.KeyAudit()
    assert game.parse("ssh-ed25519 !!! alice@host\n") == 0


def test_blank_and_comment_lines_are_skipped():
    game = sk.KeyAudit()
    assert game.parse("\n# comment\n\n" + line() + "\n") == 1


def test_max_keys_per_user_is_reported():
    text = line() + "\n" + line(comment="alice@second") + "\n" + line(comment="alice@third") + "\n"
    assert "too_many" in codes(audit(text, {"max_keys_per_user": 2}))


def test_disallowed_key_type_is_reported():
    text = "ssh-dss " + BLOB + " alice@host\n"
    assert "bad_type" in codes(audit(text, {"allowed_types": ["ssh-ed25519"]}))


def test_findings_are_sorted_by_severity():
    text = 'expiry-time="20200101" ssh-ed25519 ' + BLOB + " alice@host\n"
    findings = audit(text)
    assert findings[0]["code"] == "expired"


def test_parse_returns_accepted_count():
    text = line() + "\n" + "ssh-ed25519 !!! bad\n"
    assert sk.KeyAudit().parse(text) == 1


def test_findings_returns_copy():
    game = sk.KeyAudit()
    game.parse('expiry-time="20200101" ssh-ed25519 ' + BLOB + " alice@host")
    game.audit({}, 20260101)
    snap = game.findings()
    snap.clear()
    assert game.findings()
