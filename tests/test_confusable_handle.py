import pytest

import confusable_handle as ch


def registry():
    return ch.HandleRegistry()


def test_register_ascii_handle():
    game = registry()
    game.register("alice", 10)
    assert game.resolve("alice")["handle"] == "alice"


def test_fullwidth_is_normalized():
    game = registry()
    game.register("ａｌｉｃｅ", 10)
    assert game.resolve("alice") is not None


def test_zero_width_is_stripped():
    game = registry()
    game.register("ali\u200bce", 10)
    assert game.resolve("alice") is not None


def test_bidi_control_is_rejected():
    with pytest.raises(ValueError):
        registry().register("ali\u202ece", 10)


def test_cyrillic_lookalike_collides():
    game = registry()
    game.register("admin", 10)
    with pytest.raises(ValueError):
        game.register("аdmin", 20)


def test_digit_letter_confusion_collides():
    game = registry()
    game.register("bob0", 10)
    with pytest.raises(ValueError):
        game.register("bobo", 20)


def test_reserved_name_is_rejected():
    with pytest.raises(ValueError):
        registry().register("root", 10)


def test_duplicate_skeleton_is_rejected():
    game = registry()
    game.register("alice", 10)
    with pytest.raises(ValueError):
        game.register("аlice", 20)


def test_length_bounds_are_enforced():
    game = registry()
    with pytest.raises(ValueError):
        game.register("ab", 10)
    with pytest.raises(ValueError):
        game.register("a" * 25, 10)


def test_disallowed_character_is_rejected():
    with pytest.raises(ValueError):
        registry().register("ali ce", 10)


def test_empty_and_whitespace_are_rejected():
    game = registry()
    with pytest.raises(ValueError):
        game.register("", 10)
    with pytest.raises(ValueError):
        game.register("   ", 10)


def test_resolve_returns_canonical_fields():
    game = registry()
    game.register("Alice", 10)
    info = game.resolve("alice")
    assert info["handle"] == "alice"
    assert info["skeleton"] == "alice"
    assert info["registered_at"] == 10


def test_unknown_handle_returns_none():
    game = registry()
    assert game.handles()["count"] == 0
    assert game.resolve("nobody") is None


def test_handles_returns_copy():
    game = registry()
    game.register("alice", 10)
    snap = game.handles()
    snap["count"] = 99
    assert game.handles()["count"] == 1


def test_turkish_i_is_casefolded():
    game = registry()
    game.register("İlker", 10)
    assert game.resolve("ilker") is not None
