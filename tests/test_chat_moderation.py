import pytest

import chat_moderation as cm


def gate():
    game = cm.ChatGate()
    game.join("alice", guild="red", party="p1")
    game.join("bob", guild="red", party="p1")
    return game


def test_normal_message_is_sent():
    assert gate().send("alice", "say", "hello", 0)["sent"] is True


def test_unknown_channel_is_rejected():
    with pytest.raises(ValueError):
        gate().send("alice", "trade", "hello", 0)


def test_empty_message_is_rejected():
    with pytest.raises(ValueError):
        gate().send("alice", "say", "   ", 0)


def test_too_long_message_is_rejected():
    with pytest.raises(ValueError):
        gate().send("alice", "say", "x" * 501, 0)


def test_blocked_word_is_filtered():
    assert gate().send("alice", "say", "badword", 0)["sent"] is False


def test_fullwidth_text_is_normalized():
    assert gate().send("alice", "say", "ｂａｄｗｏｒｄ", 0)["sent"] is False


def test_spaced_blocked_word_is_filtered():
    assert gate().send("alice", "say", "b a d w o r d", 0)["sent"] is False


def test_say_rate_limit():
    game = gate()
    for index in range(5):
        game.send("alice", "say", "hi", index)
    with pytest.raises(ValueError):
        game.send("alice", "say", "hi", 6)


def test_whisper_rate_limit():
    game = gate()
    for index in range(3):
        game.send("alice", "whisper", "hi", index)
    with pytest.raises(ValueError):
        game.send("alice", "whisper", "hi", 4)


def test_mute_blocks_player_channels():
    game = gate()
    game.mute("alice", 100, "spam")
    with pytest.raises(ValueError):
        game.send("alice", "say", "hello", 10)


def test_system_channel_bypasses_mute_and_filter():
    game = gate()
    game.mute("alice", 100, "spam")
    assert game.send("alice", "system", "badword", 10)["sent"] is True


def test_report_has_cooldown():
    game = gate()
    game.report("alice", "bob", 0)
    with pytest.raises(ValueError):
        game.report("alice", "bob", 10)


def test_guild_channel_requires_guild_membership():
    game = gate()
    game.join("carol")
    with pytest.raises(ValueError):
        game.send("carol", "guild", "hello", 0)


def test_gm_message_is_audited_but_not_filtered():
    game = gate()
    game.set_gm("alice", True)
    result = game.send("alice", "say", "badword", 0)
    assert result["sent"] is True
    assert game.gate_report()["sent"] == 1


def test_gate_report_returns_copy():
    game = gate()
    game.send("alice", "say", "hello", 0)
    snap = game.gate_report()
    snap["sent"] = 99
    assert game.gate_report()["sent"] == 1
