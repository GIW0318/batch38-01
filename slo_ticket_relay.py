import secrets


class SloRelay:
    MAX_SPS = 20
    TTL = 120
    MAX_ATTEMPTS = 3

    def __init__(self):
        self._sessions = {}
        self._tickets = {}

    def plan(self, session, idp, sps, now):
        if not session:
            raise ValueError("session must not be empty")
        if not idp:
            raise ValueError("idp must not be empty")
        deduped = []
        seen = set()
        for sp in sps or []:
            if not sp:
                raise ValueError("sp must not be empty")
            if sp not in seen:
                seen.add(sp)
                deduped.append(sp)
        if len(deduped) > self.MAX_SPS:
            raise ValueError("too many sps")
        previous = self._sessions.get(session)
        if previous:
            for record in previous["tickets"].values():
                record["stale"] = True
        records = []
        for sp in deduped:
            record = {
                "ticket_id": secrets.token_hex(16),
                "session": session,
                "idp": idp,
                "sp": sp,
                "nonce": secrets.token_hex(16),
                "issued_at": now,
                "expires_at": now + self.TTL,
                "attempts": 0,
                "acked": False,
                "stale": False,
            }
            records.append(record)
            self._tickets[record["ticket_id"]] = record
        self._sessions[session] = {
            "idp": idp,
            "tickets": {record["ticket_id"]: record for record in records},
        }
        return [self._public_ticket(record) for record in records]

    def dispatch(self, ticket, now):
        record = self._resolve(ticket)
        if record["stale"]:
            raise ValueError("ticket superseded")
        if now >= record["expires_at"]:
            raise ValueError("ticket expired")
        if record["attempts"] >= self.MAX_ATTEMPTS:
            raise ValueError("retry limit reached")
        record["attempts"] += 1
        return {
            "ticket_id": record["ticket_id"],
            "session": record["session"],
            "idp": record["idp"],
            "sp": record["sp"],
            "nonce": record["nonce"],
            "attempts": record["attempts"],
            "expires_at": record["expires_at"],
        }

    def ack(self, ticket, sp, nonce, now):
        record = self._resolve(ticket)
        if record["stale"]:
            return False
        if record["sp"] != sp:
            raise ValueError("sp mismatch")
        if record["nonce"] != nonce:
            raise ValueError("nonce mismatch")
        if record["acked"]:
            return True
        if now >= record["expires_at"]:
            raise ValueError("ticket expired")
        record["acked"] = True
        record["acked_at"] = now
        return True

    def state(self, session):
        if not session:
            raise ValueError("session must not be empty")
        entry = self._sessions.get(session)
        if entry is None:
            raise KeyError(session)
        records = list(entry["tickets"].values())
        if records and all(record["acked"] for record in records):
            status = "success"
        elif any(
            not record["acked"] and record["attempts"] >= self.MAX_ATTEMPTS
            for record in records
        ):
            status = "failed"
        elif any(record["acked"] or record["attempts"] > 0 for record in records):
            status = "partial"
        else:
            status = "pending"
        return {
            "session": session,
            "idp": entry["idp"],
            "status": status,
            "tickets": [self._public_ticket(record) for record in records],
        }

    def _resolve(self, ticket):
        ticket_id = ticket.get("ticket_id") if isinstance(ticket, dict) else ticket
        record = self._tickets.get(ticket_id)
        if record is None:
            raise ValueError("unknown ticket")
        return record

    @staticmethod
    def _public_ticket(record):
        return {key: value for key, value in record.items() if key != "stale"}
