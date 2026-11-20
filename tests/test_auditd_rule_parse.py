import pytest

import auditd_rule_parse as arp

RULES = """
# basic rules
-w /etc/passwd -p rw -k identity
-a always,exit -F arch=b64 -S openat -k file_open
-a always,exit -F arch=b32 -S openat -k file_open32
"""


def book(text=RULES):
    rules = arp.RuleBook()
    rules.load(text)
    return rules


def event(path=None, perm="r", syscall="openat", arch="b64"):
    return {"path": path, "perm": perm, "syscall": syscall, "arch": arch}


def test_load_returns_rule_count():
    assert book().snapshot()["rules"] == 3


def test_watch_rule_matches_path_and_permission():
    keys = book().match(event(path="/etc/passwd", perm="r", syscall="stat"))
    assert keys == ["identity"]


def test_watch_rule_rejects_unlisted_permission():
    rules = book()
    assert rules.match(event(path="/etc/passwd", perm="r", syscall="stat")) == ["identity"]
    assert rules.match(event(path="/etc/passwd", perm="x", syscall="stat")) == []


def test_syscall_rule_matches_arch_and_syscall():
    keys = book().match(event(path="/tmp/x", perm="r", syscall="openat", arch="b64"))
    assert keys == ["file_open"]


def test_syscall_rule_rejects_wrong_arch():
    keys = book().match(event(path="/tmp/x", perm="r", syscall="openat", arch="b32"))
    assert keys == ["file_open32"]


def test_identical_rule_is_deduplicated():
    text = "-w /etc/passwd -p rw -k identity\n-w /etc/passwd -p rw -k identity\n"
    info = book(text).snapshot()
    assert info["rules"] == 1
    assert info["duplicates"] == 1


def test_unknown_syscall_is_skipped_and_counted():
    text = "-w /etc -p r -k base\n-a always,exit -F arch=b64 -S made_up -k odd\n"
    info = book(text).snapshot()
    assert info["rules"] == 1
    assert info["unknown_syscalls"] == 1


def test_arch_must_be_b64_or_b32():
    text = "-w /etc -p r -k base\n-a always,exit -F arch=arm64 -S openat -k bad\n"
    with pytest.raises(ValueError):
        book(text)


def test_permission_must_use_rwxa():
    with pytest.raises(ValueError):
        book("-w /etc -p rwz -k bad\n")


def test_tag_must_be_simple():
    with pytest.raises(ValueError):
        book("-w /etc -p r -k bad-tag\n")


def test_empty_rule_is_rejected():
    with pytest.raises(ValueError):
        book("-w\n")


def test_comment_and_continuation_are_parsed():
    text = "# comment\n-w /etc/shadow -p w \\\n  -k shadow\n"
    rules = book(text)
    assert rules.snapshot()["rules"] == 1
    assert rules.match(event(path="/etc/shadow", perm="w", syscall="stat")) == ["shadow"]


def test_syscall_rule_before_watch_is_rejected():
    text = "-a always,exit -F arch=b64 -S openat -k early\n-w /etc -p r -k later\n"
    with pytest.raises(ValueError):
        book(text)


def test_exclusion_rule_has_priority():
    text = "-w /etc -p r -k base\n-- -w /etc/secret -p r -k ignore\n"
    rules = book(text)
    assert rules.match(event(path="/etc", perm="r", syscall="stat")) == ["base"]
    assert rules.match(event(path="/etc/secret", perm="r", syscall="stat")) == []


def test_snapshot_reports_all_counters():
    info = book().snapshot()
    assert info["rules"] == 3
    assert info["duplicates"] == 0
    assert info["unknown_syscalls"] == 0
