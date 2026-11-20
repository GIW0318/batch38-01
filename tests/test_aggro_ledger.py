import pytest

import aggro_ledger as al


def table():
    game = al.ThreatTable(["boss"])
    game.add("alice", "boss", 100, "damage", 0)
    game.add("bob", "boss", 50, "damage", 0)
    return game


def test_damage_threat_is_added():
    game = table()
    assert game.top("boss", 1)[0]["actor"] == "alice"


def test_heal_threat_uses_half_coefficient():
    game = al.ThreatTable(["boss"])
    game.add("healer", "boss", 100, "heal", 0)
    assert game.state()["boss"]["healer"] == 50


def test_taunt_sets_110_percent_of_highest():
    game = table()
    game.taunt("bob", "boss", 1)
    assert game.state()["boss"]["bob"] == pytest.approx(110.0)


def test_second_taunt_within_ten_seconds_uses_105_percent():
    game = table()
    game.taunt("bob", "boss", 1)
    game.taunt("alice", "boss", 5)
    assert game.state()["boss"]["alice"] == pytest.approx(110.0 * 1.05)


def test_drop_reduces_threat_but_not_below_zero():
    game = table()
    game.drop("alice", "boss", 0.5)
    assert game.state()["boss"]["alice"] == 50
    game.drop("alice", "boss", 2.0)
    assert game.state()["boss"]["alice"] == 0


def test_link_records_redirect():
    game = table()
    game.link("alice", "bob", 0.3, 10)
    assert game.state()["links"][0]["dst"] == "bob"


def test_link_cannot_chain_or_cycle():
    game = table()
    game.link("alice", "bob", 0.3, 10)
    with pytest.raises(ValueError):
        game.link("bob", "carol", 0.2, 10)
    with pytest.raises(ValueError):
        game.link("bob", "alice", 0.2, 10)


def test_air_phase_freezes_threat():
    game = table()
    game.phase("boss", "air", 1)
    game.add("alice", "boss", 100, "damage", 2)
    assert game.state()["boss"]["alice"] == 100


def test_ground_phase_resumes_growth():
    game = table()
    game.phase("boss", "air", 1)
    game.phase("boss", "ground", 2)
    game.add("alice", "boss", 10, "damage", 3)
    assert game.state()["boss"]["alice"] == 110


def test_threat_decays_after_ten_seconds():
    game = al.ThreatTable(["boss"])
    game.add("alice", "boss", 100, "damage", 0)
    game.tick(21)
    assert game.state()["boss"]["alice"] < 100


def test_top_orders_by_threat_then_earliest():
    game = al.ThreatTable(["boss"])
    game.add("bob", "boss", 10, "damage", 0)
    game.add("alice", "boss", 10, "damage", 0)
    assert [x["actor"] for x in game.top("boss", 2)] == ["bob", "alice"]


def test_top_n_is_bounded():
    with pytest.raises(ValueError):
        table().top("boss", 0)
    with pytest.raises(ValueError):
        table().top("boss", 9)


def test_snapshot_and_rewind_restore_vector():
    game = table()
    snap = game.snapshot("boss")
    game.add("alice", "boss", 100, "damage", 1)
    game.rewind(snap["snapshot_id"], 2)
    assert game.state()["boss"]["alice"] == 100


def test_rewind_rejects_other_phase_and_expired_snapshot():
    game = table()
    snap = game.snapshot("boss")
    game.phase("boss", "air", 1)
    with pytest.raises(ValueError):
        game.rewind(snap["snapshot_id"], 2)
    game.phase("boss", "ground", 3)
    with pytest.raises(ValueError):
        game.rewind(snap["snapshot_id"], 20)


def test_unknown_boss_negative_value_and_backwards_time_are_rejected():
    game = table()
    with pytest.raises(ValueError):
        game.add("alice", "ghost", 1, "damage", 0)
    with pytest.raises(ValueError):
        game.add("alice", "boss", -1, "damage", 1)
    with pytest.raises(ValueError):
        game.add("alice", "boss", 1, "damage", -1)
