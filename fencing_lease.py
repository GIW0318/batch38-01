class FenceLease:
    def __init__(self):
        self._state = {}
        self._clock = None

    @staticmethod
    def _normalize(resource):
        if not isinstance(resource, str) or not resource.strip():
            raise ValueError("resource name must be a non-empty string")
        return resource.casefold()

    def _check_clock(self, now):
        if not isinstance(now, (int, float)) or isinstance(now, bool):
            raise ValueError("now must be a numeric timestamp")
        if self._clock is not None and now < self._clock:
            raise ValueError("clock moved backwards")

    @staticmethod
    def _check_ttl(ttl):
        if not isinstance(ttl, int) or isinstance(ttl, bool) or not 1 <= ttl <= 3600:
            raise ValueError("ttl must be an integer between 1 and 3600 seconds")

    @staticmethod
    def _format_token(epoch, seq):
        return f"{epoch:08x}-{seq:04x}"

    def _snapshot(self, state):
        return {
            "token": state["token"],
            "epoch": state["epoch"],
            "seq": state["seq"],
            "owner": state["owner"],
            "expires_at": state["expires_at"],
        }

    def _find(self, token):
        for name, state in self._state.items():
            if state["token"] == token:
                return name, state
        return None, None

    def acquire(self, resource, owner, now, ttl):
        name = self._normalize(resource)
        self._check_clock(now)
        self._check_ttl(ttl)
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("owner must be a non-empty string")
        self._clock = now

        state = self._state.get(name)
        if state is not None and state["owner"] is not None and state["expires_at"] > now:
            if state["owner"] != owner:
                raise ValueError("resource is already held by another owner")
            return self._snapshot(state)

        if state is None:
            state = {"epoch": 1, "seq": 0, "owner": None, "expires_at": None,
                     "token": None, "ttl": None}
            self._state[name] = state

        if state["owner"] is not None:
            state["epoch"] += 1
        state["seq"] += 1
        state["owner"] = owner
        state["expires_at"] = now + ttl
        state["ttl"] = ttl
        state["token"] = self._format_token(state["epoch"], state["seq"])
        return self._snapshot(state)

    def renew(self, token, now, ttl=None):
        self._check_clock(now)
        name, state = self._find(token)
        if state is None or state["owner"] is None or state["token"] != token:
            raise ValueError("unknown token")
        if state["expires_at"] <= now:
            raise ValueError("lease has expired")
        if ttl is None:
            ttl = state["ttl"]
        self._check_ttl(ttl)
        self._clock = now
        state["ttl"] = ttl
        state["expires_at"] = now + ttl
        return self._snapshot(state)

    def release(self, token):
        name, state = self._find(token)
        if state is None or state["owner"] is None or state["token"] != token:
            raise ValueError("unknown token")
        state["owner"] = None
        state["expires_at"] = None
        state["ttl"] = None

    def validate(self, resource, token, now):
        name = self._normalize(resource)
        self._check_clock(now)
        self._clock = now
        state = self._state.get(name)
        if state is None or state["owner"] is None:
            return False
        if state["token"] != token or state["expires_at"] <= now:
            return False
        return True

    def leases(self):
        return {
            name: {
                "epoch": state["epoch"],
                "owner": state["owner"],
                "expires_at": state["expires_at"],
            }
            for name, state in self._state.items()
            if state["owner"] is not None
        }
