import pytest

import arena_draft as ad

HEROES = [
    {"id": "h1", "role": "tank"},
    {"id": "h2", "role": "tank"},
    {"id": "h3", "role": "healer"},
    {"id": "h4", "role": "healer"},
] + [{"id": f"h{i}", "role": "dps"} for i in range(5, 14)]


def room():
    return ad.DraftRoom([dict(h) for h in HEROES])


def test_ban_removes_hero():
    game = room()
    game.ban("A", "h1", 0)
    assert "h1" in game.draft_view()["bans"]["A"]


def test_duplicate_ban_is_rejected():
    game = room()
    game.ban("A", "h1", 0)
    with pytest.raises(ValueError):
        game.ban("B", "h1", 1)


def test_banned_hero_cannot_be_picked():
    game = room()
    game.ban("A", "h1", 0)
    game.ban("B", "h2", 1)
    with pytest.raises(ValueError):
        game.pick("A", "h1", 2)


def test_pick_order_is_enforced():
    game = room()
    with pytest.raises(ValueError):
        game.pick("A", "h3", 0)


def test_same_hero_cannot_be_picked_twice():
    game = room()
    game.ban("A", "h1", 0)
    game.ban("B", "h2", 1)
    game.pick("A", "h3", 2)
    with pytest.raises(ValueError):
        game.pick("B", "h3", 3)


def test_timeout_auto_selects_first_available():
    game = room()
    game.timeout(31)
    view = game.draft_view()
    assert view["bans"]["A"] or view["picks"]["A"]


def test_simultaneous_submissions_conflict():
    game = room()
    game.ban("A", "h1", 0)
    with pytest.raises(ValueError):
        game.ban("B", "h2", 0)


def test_unknown_hero_is_rejected():
    with pytest.raises(ValueError):
        room().ban("A", "ghost", 0)


def test_pick_out_of_turn_is_rejected():
    game = room()
    game.ban("A", "h11", 0)
    game.ban("B", "h12", 1)
    game.ban("A", "h13", 2)
    game.pick("A", "h1", 3)
    with pytest.raises(ValueError):
        game.pick("A", "h3", 4)


def test_start_requires_tank_and_healer():
    game = room()
    with pytest.raises(ValueError):
        game.start()


def test_start_succeeds_with_roles():
    game = room()
    clock = 0
    for index, hero in enumerate(["h11", "h12", "h13"]):
        game.ban("A" if index % 2 == 0 else "B", hero, clock)
        clock += 1
    picks = ["h1", "h2", "h3", "h4", "h5", "h8", "h6", "h9", "h7", "h10"]
    for index, hero in enumerate(picks):
        game.pick("A" if index % 2 == 0 else "B", hero, clock)
        clock += 1
    assert game.start()["ok"] is True


def test_rematch_resets_state():
    game = room()
    game.ban("A", "h1", 0)
    game.rematch()
    assert game.draft_view()["bans"]["A"] == []


def test_ban_phase_completes_before_pick():
    game = room()
    for index, hero in enumerate(["h11", "h12", "h13"]):
        game.ban("A" if index % 2 == 0 else "B", hero, index)
    assert game.draft_view()["step"] == 3


def test_view_reports_step_and_timer():
    info = room().draft_view()
    assert info["step"] == 0
    assert info["remaining"] == 30


def test_view_returns_copy():
    game = room()
    game.ban("A", "h1", 0)
    snap = game.draft_view()
    snap["bans"]["A"].clear()
    assert game.draft_view()["bans"]["A"]
