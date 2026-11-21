import hashlib


DEFAULT_DIFFICULTY = 16
MIN_DIFFICULTY = 12
MAX_DIFFICULTY = 24
HARDEST_DIFFICULTY = 32
CHALLENGE_TTL = 120
MAX_OUTSTANDING = 3
NONCE_MIN = 0
NONCE_MAX = 2 ** 32 - 1


def _leading_zero_bits(digest):
    bits = 0
    for byte in digest:
        if byte == 0:
            bits += 8
            continue
        for shift in range(7, -1, -1):
            if byte & (1 << shift):
                return bits
            bits += 1
    return bits


class PowGate:
    def __init__(self, secret):
        self.secret = secret
        self._seq = 0
        self._clients = {}

    def _state(self, client):
        state = self._clients.get(client)
        if state is None:
            state = {"difficulty": DEFAULT_DIFFICULTY, "challenges": [], "seen": False}
            self._clients[client] = state
        return state

    def _adjust_difficulty(self, difficulty, delta):
        value = difficulty + delta
        if MIN_DIFFICULTY <= difficulty <= MAX_DIFFICULTY:
            return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, value))
        if difficulty < MIN_DIFFICULTY:
            return min(MAX_DIFFICULTY, value)
        return max(MIN_DIFFICULTY, value)

    def _prune_expired(self, state, now):
        state["challenges"] = [
            record
            for record in state["challenges"]
            if now - record["issued_at"] < CHALLENGE_TTL
        ]

    def issue(self, client, now, difficulty=None):
        if difficulty is not None:
            if difficulty < 0:
                raise ValueError("difficulty must not be negative")
            if difficulty > HARDEST_DIFFICULTY:
                raise ValueError("difficulty must not exceed %d" % HARDEST_DIFFICULTY)
        requested = None if difficulty in (None, 0) else difficulty

        state = self._state(client)
        self._prune_expired(state, now)
        if len(state["challenges"]) >= MAX_OUTSTANDING:
            raise ValueError(
                "client %s already has %d outstanding challenges"
                % (client, MAX_OUTSTANDING)
            )

        if not state["seen"]:
            state["difficulty"] = (
                requested if requested is not None else DEFAULT_DIFFICULTY
            )
            state["seen"] = True

        self._seq += 1
        material = "%s:%s:%d:%s" % (self.secret, client, self._seq, now)
        challenge = hashlib.sha256(material.encode()).hexdigest()
        challenge_id = hashlib.sha256(("id:" + material).encode()).hexdigest()[:32]

        state["challenges"].append(
            {
                "challenge_id": challenge_id,
                "challenge": challenge,
                "difficulty": state["difficulty"],
                "issued_at": now,
            }
        )

        return {
            "challenge_id": challenge_id,
            "challenge": challenge,
            "expires_at": CHALLENGE_TTL,
            "difficulty": state["difficulty"],
        }

    def verify(self, client, challenge_id, nonce, now):
        state = self._state(client)
        record = None
        for candidate in state["challenges"]:
            if candidate["challenge_id"] == challenge_id:
                record = candidate
                break
        if record is None:
            raise ValueError("unknown or already consumed challenge %s" % challenge_id)

        if now - record["issued_at"] >= CHALLENGE_TTL:
            raise ValueError("challenge %s has expired" % challenge_id)

        if isinstance(nonce, bool) or not isinstance(nonce, int):
            raise ValueError("nonce must be an integer")
        if nonce < NONCE_MIN or nonce > NONCE_MAX:
            raise ValueError("nonce must be between 0 and 2^32-1")

        digest = hashlib.sha256(
            (record["challenge"] + ":" + str(nonce)).encode()
        ).digest()
        elapsed = now - record["issued_at"]

        if _leading_zero_bits(digest) < record["difficulty"]:
            state["difficulty"] = self._adjust_difficulty(state["difficulty"], 2)
            return {
                "ok": False,
                "reason": "hash does not meet the required leading zero bits",
            }

        state["challenges"].remove(record)
        state["difficulty"] = self._adjust_difficulty(state["difficulty"], -1)
        return {
            "ok": True,
            "remaining": len(state["challenges"]),
            "elapsed": elapsed,
        }

    def challenges(self):
        return {
            client: {
                "outstanding": len(state["challenges"]),
                "difficulty": state["difficulty"],
            }
            for client, state in self._clients.items()
        }
