HEADER_DEADLINE_SECS = 10
HEADER_MAX_BYTES = 16 * 1024
BODY_GRACE_SECS = 5
BODY_MIN_RATE = 1024
BODY_MAX_BYTES = 1024 * 1024
IDLE_TIMEOUT_SECS = 30
MAX_PIPELINE_REQUESTS = 2


class _ConnState:
    def __init__(self, ip, ts, expect_continue=False):
        self.ip = ip
        self.open_ts = ts
        self.last_ts = ts
        self.phase = "open"
        self.header_bytes = 0
        self.body_bytes = 0
        self.body_start_ts = None
        self.request_count = 0
        self.expect_continue = expect_continue


class RequestBudget:
    def __init__(self, max_per_ip=8, max_total=100):
        self.max_per_ip = max_per_ip
        self.max_total = max_total
        self._conns = {}
        self._reasons = {}

    @staticmethod
    def _ok():
        return {"ok": True, "reason": None}

    def _reject(self, reason):
        self._reasons[reason] = self._reasons.get(reason, 0) + 1
        return {"ok": False, "reason": reason}

    def _lookup(self, conn, ts):
        state = self._conns.get(conn)
        if state is None:
            raise ValueError("unknown connection: %r" % (conn,))
        if ts < state.last_ts:
            raise ValueError(
                "timestamp moved backwards: %r < %r" % (ts, state.last_ts)
            )
        return state

    def _idle_expired(self, state, ts):
        return ts - state.last_ts > IDLE_TIMEOUT_SECS

    def open(self, conn, ip, ts, expect_continue=False):
        if conn in self._conns:
            raise ValueError("connection already open: %r" % (conn,))
        ip_count = sum(1 for s in self._conns.values() if s.ip == ip)
        if ip_count >= self.max_per_ip:
            raise ValueError("per-ip connection limit reached for %r" % (ip,))
        if len(self._conns) >= self.max_total:
            raise ValueError("global connection limit reached")
        self._conns[conn] = _ConnState(ip, ts, expect_continue)
        return self._ok()

    def recv_headers(self, conn, size, ts, expect_continue=None):
        state = self._lookup(conn, ts)

        if self._idle_expired(state, ts):
            del self._conns[conn]
            return self._reject("idle_timeout")

        if state.phase == "body":
            if state.request_count + 1 > MAX_PIPELINE_REQUESTS:
                return self._reject("pipeline_limit")
            state.request_count += 1
            state.phase = "headers"
            state.header_bytes = 0
            state.body_start_ts = None
        elif state.request_count == 0:
            state.request_count = 1

        if expect_continue is not None:
            state.expect_continue = expect_continue

        if ts - state.open_ts > HEADER_DEADLINE_SECS:
            return self._reject("header_timeout")

        if state.header_bytes + size > HEADER_MAX_BYTES:
            return self._reject("header_too_large")

        state.header_bytes += size
        state.last_ts = ts
        state.phase = "headers"
        return self._ok()

    def recv_body(self, conn, size, ts):
        state = self._lookup(conn, ts)

        if self._idle_expired(state, ts):
            del self._conns[conn]
            return self._reject("idle_timeout")

        if state.phase == "open":
            return self._reject("body_without_request")

        if state.body_start_ts is None:
            state.body_start_ts = ts

        if state.body_bytes + size > BODY_MAX_BYTES:
            return self._reject("body_too_large")

        rate_window = ts - state.body_start_ts - BODY_GRACE_SECS
        if rate_window > 0 and state.body_bytes + size < rate_window * BODY_MIN_RATE:
            return self._reject("body_too_slow")

        state.body_bytes += size
        state.last_ts = ts
        state.phase = "body"
        return self._ok()

    def wait_continue(self, conn, ts):
        state = self._lookup(conn, ts)
        if not state.expect_continue:
            return self._reject("continue_not_declared")
        state.last_ts = ts
        return self._ok()

    def finish(self, conn, ts):
        state = self._lookup(conn, ts)
        del self._conns[conn]
        return self._ok()

    def profile(self):
        return {
            "connections": len(self._conns),
            "reasons": dict(self._reasons),
        }
