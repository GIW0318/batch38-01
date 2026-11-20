ROLE_CATEGORIES = ("tank", "healer", "dps")

BASE_RANGE = 100
RANGE_STEP = 50
RANGE_STEP_SECONDS = 30
MAX_RANGE = 500
PRIORITY_WAIT = 300
MAX_TEAM_SIZE = 3


def _role_counts(team):
    counts = {role: 0 for role in ROLE_CATEGORIES}
    for player in team["players"]:
        role = player.get("role")
        if role in counts:
            counts[role] += 1
    return counts


def _composition_similarity(team_a, team_b):
    counts_a = _role_counts(team_a)
    counts_b = _role_counts(team_b)
    matched = sum(min(counts_a[role], counts_b[role]) for role in ROLE_CATEGORIES)
    if counts_a["healer"] == 0 or counts_b["healer"] == 0:
        matched *= 0.5
    return matched


class ArenaQueue:
    def __init__(self):
        self._entries = []
        self._now = 0

    def enqueue(self, team, now):
        self._now = now
        players = team.get("players") or []
        if not 1 <= len(players) <= MAX_TEAM_SIZE:
            raise ValueError("team must have 1 to 3 players")
        names = [player.get("name") for player in players]
        if len(set(names)) != len(names):
            raise ValueError("duplicate players in team")
        if any(entry["team"]["id"] == team.get("id") for entry in self._entries):
            raise ValueError("team already queued")
        self._entries.append({"team": team, "enqueued_at": now})
        return None

    def cancel(self, team_id, now):
        self._now = now
        for index, entry in enumerate(self._entries):
            if entry["team"]["id"] == team_id:
                del self._entries[index]
                return None
        raise ValueError("unknown team")

    def _allowed_range(self, entry, now):
        waited = max(0, now - entry["enqueued_at"])
        steps = waited // RANGE_STEP_SECONDS
        return min(BASE_RANGE + RANGE_STEP * steps, MAX_RANGE)

    def _compatible(self, entry_a, entry_b, now):
        size_a = len(entry_a["team"]["players"])
        size_b = len(entry_b["team"]["players"])
        if (size_a == MAX_TEAM_SIZE) != (size_b == MAX_TEAM_SIZE):
            return False
        diff = abs(entry_a["team"]["rating"] - entry_b["team"]["rating"])
        allowed = min(self._allowed_range(entry_a, now), self._allowed_range(entry_b, now))
        return diff <= allowed

    def _pair_score(self, entry_a, entry_b, now):
        wait_a = now - entry_a["enqueued_at"]
        wait_b = now - entry_b["enqueued_at"]
        priority = int(wait_a > PRIORITY_WAIT) + int(wait_b > PRIORITY_WAIT)
        similarity = _composition_similarity(entry_a["team"], entry_b["team"])
        diff = abs(entry_a["team"]["rating"] - entry_b["team"]["rating"])
        return (priority, similarity, -diff, wait_a + wait_b)

    def match(self, now):
        self._now = now
        best = None
        best_score = None
        for i in range(len(self._entries)):
            for j in range(i + 1, len(self._entries)):
                entry_a = self._entries[i]
                entry_b = self._entries[j]
                if not self._compatible(entry_a, entry_b, now):
                    continue
                score = self._pair_score(entry_a, entry_b, now)
                if best_score is None or score > best_score:
                    best_score = score
                    best = (i, j)
        if best is None:
            return None
        i, j = best
        entry_b = self._entries.pop(j)
        entry_a = self._entries.pop(i)
        return {"teams": [entry_a["team"], entry_b["team"]]}

    def queues(self):
        segments = {}
        longest_wait = 0
        for entry in self._entries:
            bucket = entry["team"]["rating"] // 100 * 100
            segments[bucket] = segments.get(bucket, 0) + 1
            longest_wait = max(longest_wait, self._now - entry["enqueued_at"])
        return {
            "waiting": len(self._entries),
            "segments": segments,
            "longest_wait": longest_wait,
        }
