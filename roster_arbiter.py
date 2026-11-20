import threading
from copy import deepcopy


MAX_MEMBERS = 5
INVITE_TTL = 60
DISCONNECT_GRACE = 120
ROLE_LIMITS = {"tank": 1, "healer": 1, "dps": 3}
ROLE_ALIASES = {
    "tank": "tank",
    "坦": "tank",
    "坦克": "tank",
    "healer": "healer",
    "heal": "healer",
    "奶": "healer",
    "治疗": "healer",
    "dps": "dps",
    "damage": "dps",
    "输出": "dps",
}


class RosterArbiter:
    def __init__(self):
        self._lock = threading.RLock()
        self._leader = None
        self._members = {}
        self._invites = {}
        self._left_players = set()
        self._join_sequence = 0

    @staticmethod
    def _normalize_role(role):
        if not isinstance(role, str):
            raise ValueError("invalid role")
        normalized = ROLE_ALIASES.get(role.strip().lower())
        if normalized is None:
            raise ValueError("invalid role")
        return normalized

    @staticmethod
    def _check_time(now):
        if now is None:
            raise ValueError("time is required")

    def _expire_disconnected(self, now):
        expired = [
            player
            for player, member in self._members.items()
            if member["grace_until"] is not None
            and now >= member["grace_until"]
        ]
        for player in expired:
            del self._members[player]
        if self._leader in expired:
            self._promote_leader()

    def _expire_invites(self, now):
        expired = [
            player
            for player, invite in self._invites.items()
            if now >= invite["expires_at"]
        ]
        for player in expired:
            del self._invites[player]

    def _promote_leader(self, exclude=None):
        candidates = [
            (member["joined_at"], member["join_sequence"], player)
            for player, member in self._members.items()
            if player != exclude
        ]
        self._leader = min(candidates)[2] if candidates else None

    def _count_role(self, role):
        return sum(
            member["role"] == role for member in self._members.values()
        )

    def invite(self, leader, player, role, now):
        self._check_time(now)
        normalized_role = self._normalize_role(role)

        with self._lock:
            self._expire_disconnected(now)
            self._expire_invites(now)

            if player == leader:
                raise ValueError("leader cannot invite themselves")
            if self._leader is None:
                self._leader = leader
            elif leader != self._leader:
                raise ValueError("only the leader can invite")
            if len(self._members) >= MAX_MEMBERS:
                raise ValueError("party is full")
            if player in self._members:
                raise ValueError("player is already in the party")
            if player in self._invites:
                raise ValueError("player already has a pending invite")

            self._invites[player] = {
                "leader": leader,
                "role": normalized_role,
                "invited_at": now,
                "expires_at": now + INVITE_TTL,
            }

    def accept(self, player, now):
        self._check_time(now)

        with self._lock:
            self._expire_disconnected(now)
            self._expire_invites(now)

            invite = self._invites.get(player)
            if invite is None:
                raise ValueError("no valid invite")
            if player in self._members:
                raise ValueError("player is already in the party")
            if len(self._members) >= MAX_MEMBERS:
                raise ValueError("party is full")

            role = invite["role"]
            if self._count_role(role) >= ROLE_LIMITS[role]:
                raise ValueError("role capacity exceeded")

            self._join_sequence += 1
            self._members[player] = {
                "player": player,
                "role": role,
                "ready": False,
                "joined_at": now,
                "join_sequence": self._join_sequence,
                "grace_until": None,
            }
            self._left_players.discard(player)
            del self._invites[player]

    def decline(self, player, now):
        self._check_time(now)

        with self._lock:
            self._expire_invites(now)
            if player not in self._invites:
                raise ValueError("no valid invite")
            del self._invites[player]

    def kick(self, leader, player):
        with self._lock:
            if self._leader is None or leader != self._leader:
                raise ValueError("only the leader can kick")
            if player == leader:
                raise ValueError("leader cannot kick themselves")
            if player not in self._members:
                raise ValueError("player is not in the party")

            del self._members[player]
            self._invites.pop(player, None)

    def leave(self, player, now):
        self._check_time(now)

        with self._lock:
            self._expire_disconnected(now)

            member = self._members.get(player)
            is_leader = player == self._leader

            if member is None:
                if not is_leader:
                    if player in self._left_players:
                        return
                    raise ValueError("player is not in the party")
                self._promote_leader()
                self._left_players.add(player)
                return

            if member["grace_until"] is not None:
                return

            member["grace_until"] = now + DISCONNECT_GRACE
            member["ready"] = False
            self._left_players.add(player)

            if is_leader:
                self._promote_leader(exclude=player)

    def ready(self, player, flag):
        with self._lock:
            member = self._members.get(player)
            if member is None:
                raise ValueError("player is not in the party")
            if member["grace_until"] is not None:
                raise ValueError("disconnected players cannot ready")
            member["ready"] = bool(flag)

    def start(self, leader, now):
        self._check_time(now)

        with self._lock:
            self._expire_disconnected(now)

            if self._leader is None or leader != self._leader:
                raise ValueError("only the leader can start")
            if not self._members:
                raise ValueError("party has no members")
            if any(
                member["grace_until"] is not None or not member["ready"]
                for member in self._members.values()
            ):
                raise ValueError("all members must be ready")
            return {"ok": True}

    def state(self):
        with self._lock:
            members = []
            roles = {}
            ready = {}
            grace_until = {}
            role_counts = {role: 0 for role in ROLE_LIMITS}

            for player, member in self._members.items():
                members.append(
                    {
                        "player": player,
                        "role": member["role"],
                        "ready": member["ready"],
                        "joined_at": member["joined_at"],
                        "grace_until": member["grace_until"],
                        "disconnected": member["grace_until"] is not None,
                    }
                )
                roles[player] = member["role"]
                ready[player] = member["ready"]
                role_counts[member["role"]] += 1
                if member["grace_until"] is not None:
                    grace_until[player] = member["grace_until"]

            grace = max(grace_until.values(), default=0)
            invites = {
                player: deepcopy(invite)
                for player, invite in self._invites.items()
            }
            return {
                "members": deepcopy(members),
                "roles": deepcopy(roles),
                "role_counts": deepcopy(role_counts),
                "ready": deepcopy(ready),
                "leader": self._leader,
                "grace": grace,
                "grace_until": deepcopy(grace_until),
                "pending": len(self._invites),
                "invites": invites,
            }
