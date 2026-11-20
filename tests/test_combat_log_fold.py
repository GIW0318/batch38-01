import pytest

import combat_log_fold as clf


def ev(eid, t, source, target, ability, amount, kind="damage", crit=False, overkill=0):
    return {
        "id": eid,
        "t": t,
        "source": source,
        "target": target,
        "ability": ability,
        "amount": amount,
        "type": kind,
        "crit": crit,
        "overkill": overkill,
    }


def control(eid, t, kind):
    return ev(eid, t, "boss", "party", kind, 0, kind=kind)


def test_ingest_counts_events():
    fold = clf.CombatFold()
    assert fold.ingest([ev(1, 0, "alice", "boss", "hit", 10)]) == 1
    assert fold.totals()["events"] == 1


def test_duplicate_event_id_is_ignored():
    fold = clf.CombatFold()
    events = [ev(1, 0, "alice", "boss", "hit", 10), ev(1, 0, "alice", "boss", "hit", 10)]
    assert fold.ingest(events) == 1
    assert fold.summary(1)["total_damage"] == 10


def test_pet_damage_is_credited_to_owner():
    fold = clf.CombatFold({"pet": "alice"})
    fold.ingest([ev(1, 0, "pet", "boss", "bite", 12)])
    assert fold.summary(1)["sources"]["alice"] == 12


def test_dot_damage_keeps_original_caster():
    fold = clf.CombatFold()
    fold.ingest([
        ev(1, 0, "alice", "boss", "dot", 7, kind="dot"),
        ev(2, 1, "bob", "boss", "dot", 9, kind="dot"),
    ])
    sources = fold.summary(1)["sources"]
    assert sources["alice"] == 7
    assert sources["bob"] == 9


def test_absorb_is_not_counted_as_damage():
    fold = clf.CombatFold()
    fold.ingest([ev(1, 0, "alice", "tank", "shield", 50, kind="absorb")])
    summary = fold.summary(1)
    assert summary["total_damage"] == 0
    assert summary["absorbed"] == 50


def test_summary_total_damage():
    fold = clf.CombatFold()
    fold.ingest([
        ev(1, 0, "alice", "boss", "hit", 10),
        ev(2, 1, "bob", "boss", "hit", 15),
        ev(3, 2, "alice", "boss", "dot", 5, kind="dot"),
    ])
    assert fold.summary(1)["total_damage"] == 30


def test_ability_breakdown():
    fold = clf.CombatFold()
    fold.ingest([
        ev(1, 0, "alice", "boss", "slash", 10),
        ev(2, 1, "alice", "boss", "slash", 5),
        ev(3, 2, "alice", "boss", "kick", 7),
    ])
    abilities = fold.summary(1)["abilities"]
    assert abilities == {"slash": 15, "kick": 7}


def test_crit_rate_only_counts_direct_damage():
    fold = clf.CombatFold()
    fold.ingest([
        ev(1, 0, "alice", "boss", "hit", 10, crit=True),
        ev(2, 1, "alice", "boss", "hit", 10, crit=False),
        ev(3, 2, "alice", "boss", "dot", 10, kind="dot", crit=True),
    ])
    assert fold.summary(1)["crit_rate"] == pytest.approx(0.5)


def test_overkill_is_summed():
    fold = clf.CombatFold()
    fold.ingest([
        ev(1, 0, "alice", "boss", "hit", 10, overkill=3),
        ev(2, 1, "bob", "boss", "hit", 10, overkill=4),
    ])
    assert fold.summary(1)["overkill"] == 7


def test_dps_uses_encounter_duration():
    fold = clf.CombatFold()
    fold.ingest([
        ev(1, 0, "alice", "boss", "hit", 60),
        ev(2, 10, "alice", "boss", "hit", 40),
    ])
    summary = fold.summary(1)
    assert summary["dps"] == pytest.approx(10.0)
    assert summary["uptime"] == 10


def test_wipe_and_kill_start_new_encounters():
    fold = clf.CombatFold()
    fold.ingest([
        control(1, 0, "engage"),
        ev(2, 5, "alice", "boss", "hit", 10),
        control(3, 10, "wipe"),
        control(4, 20, "engage"),
        ev(5, 25, "bob", "boss", "hit", 20),
        control(6, 30, "kill"),
    ])
    assert fold.summary(1)["total_damage"] == 10
    assert fold.summary(2)["total_damage"] == 20
    assert fold.totals()["encounters"] == 2


def test_negative_damage_is_rejected():
    fold = clf.CombatFold()
    with pytest.raises(ValueError):
        fold.ingest([ev(1, 0, "alice", "boss", "hit", -1)])


def test_time_going_backwards_is_rejected():
    fold = clf.CombatFold()
    with pytest.raises(ValueError):
        fold.ingest([ev(1, 10, "alice", "boss", "hit", 1), ev(2, 9, "alice", "boss", "hit", 1)])


def test_unknown_event_type_is_rejected():
    fold = clf.CombatFold()
    with pytest.raises(ValueError):
        fold.ingest([ev(1, 0, "alice", "boss", "hit", 1, kind="heal")])


def test_totals_reports_events_and_segments():
    fold = clf.CombatFold()
    fold.ingest([
        control(1, 0, "engage"),
        ev(2, 1, "alice", "boss", "hit", 5),
        control(3, 2, "kill"),
    ])
    totals = fold.totals()
    assert totals["events"] == 3
    assert totals["encounters"] == 1
