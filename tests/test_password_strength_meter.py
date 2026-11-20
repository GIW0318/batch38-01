import hashlib

import pytest

import password_strength_meter as ps


def meter():
    return ps.StrengthMeter()


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def test_strong_password_scores_four():
    assert meter().score("Tr0ub4dor&3x!", ["alice"]) == 4


def test_short_password_scores_low():
    assert meter().score("abc") <= 1


def test_repeated_characters_are_penalized():
    repeated = meter().score("aaaaaaaaaaaaaaaa")
    varied = meter().score("Ab3!xY7@qW9#")
    assert repeated < varied


def test_keyboard_sequence_is_penalized():
    assert meter().score("qwertyuiop") <= 1


def test_common_password_is_penalized():
    assert meter().score("password") <= 1


def test_l33t_is_normalized_before_scoring():
    assert meter().score("p@ssw0rd") <= 1


def test_year_is_penalized():
    assert meter().score("Summer2024!") <= 3


def test_user_input_substring_is_penalized():
    assert meter().score("alice2024!", ["alice@example.com"]) <= 2


def test_breach_hash_forces_zero():
    assert meter().score("CorrectHorse!42", [], {sha("CorrectHorse!42")}) == 0


def test_unicode_is_normalized():
    wide = meter().score("Ｐａｓｓｗｏｒｄ1!")
    plain = meter().score("Password1!")
    assert isinstance(wide, int)
    assert wide == plain


def test_rotation_rejects_similar_password():
    with pytest.raises(ValueError):
        meter().check_rotation("Password1!", "Password2!")


def test_rotation_accepts_different_password():
    assert meter().check_rotation("Password1!", "N3w!Vault#42") is True


def test_feedback_is_deterministic_and_capped():
    game = meter()
    first = game.feedback("qwerty123", ["alice"])
    second = game.feedback("qwerty123", ["alice"])
    assert first == second
    assert 0 < len(first) <= 5


def test_empty_password_is_rejected():
    with pytest.raises(ValueError):
        meter().score("")
    with pytest.raises(ValueError):
        meter().score("   ")
    with pytest.raises(ValueError):
        meter().score(None)


def test_report_counts_without_storing_plaintext():
    game = meter()
    game.score("Tr0ub4dor&3x!")
    game.score("abc")
    with pytest.raises(ValueError):
        game.check_rotation("Password1!", "Password2!")
    info = game.report()
    assert info["evaluations"] == 2
    assert info["rejections"] == 1
    assert "Tr0ub4dor&3x!" not in str(info)
