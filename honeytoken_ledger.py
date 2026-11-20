import secrets
import zlib

FAMILIES = {"aws_key": 3, "url": 2, "doc": 2, "db": 3}

_MARK_PREFIX = "cnry"
_FRAGMENT_HEX_LEN = 24
_CHECKSUM_HEX_LEN = 4
_TAIL_HEX_LEN = _FRAGMENT_HEX_LEN + _CHECKSUM_HEX_LEN
_MIN_TTL = 1
_MAX_TTL = 86400
_DEDUP_WINDOW = 600
_ROTATION_GRACE = 600


def _checksum(body):
    return f"{zlib.crc32(body.encode('utf-8')) & 0xFFFF:0{_CHECKSUM_HEX_LEN}x}"


class _Record:
    __slots__ = (
        "family",
        "keeper",
        "ttl",
        "minted_at",
        "expires_at",
        "revoked",
        "grace_end",
        "home_tenant",
        "tenants",
        "last_alert_at",
        "events",
    )

    def __init__(self, family, keeper, ttl, ts):
        self.family = family
        self.keeper = keeper
        self.ttl = ttl
        self.minted_at = ts
        self.expires_at = ts + ttl
        self.revoked = False
        self.grace_end = None
        self.home_tenant = None
        self.tenants = set()
        self.last_alert_at = {}
        self.events = []

    def effective_expiry(self):
        if self.grace_end is None:
            return self.expires_at
        return min(self.expires_at, self.grace_end)


class CanaryLedger:
    def __init__(self):
        self._marks = {}
        self._family_last_params = {}
        self._latest_ts = 0

    def mint(self, family, keeper, ttl, ts):
        if family not in FAMILIES:
            raise ValueError(f"unknown canary family: {family!r}")
        if not _MIN_TTL <= ttl <= _MAX_TTL:
            raise ValueError("ttl must be between 1 and 86400 seconds")

        fragment = secrets.token_hex(_FRAGMENT_HEX_LEN // 2)
        body = f"{_MARK_PREFIX}_{family}_{fragment}"
        mark = body + _checksum(body)

        self._marks[mark] = _Record(family, keeper, ttl, ts)
        self._family_last_params[family] = (keeper, ttl)
        self._latest_ts = max(self._latest_ts, ts)
        return mark

    def rotate(self, family, ts):
        if family not in FAMILIES:
            raise ValueError(f"unknown canary family: {family!r}")
        existing = [r for r in self._marks.values() if r.family == family]
        if not existing:
            raise ValueError(f"no canary to rotate for family: {family!r}")

        grace_end = ts + _ROTATION_GRACE
        for record in existing:
            if record.grace_end is None or grace_end < record.grace_end:
                record.grace_end = grace_end

        keeper, ttl = self._family_last_params[family]
        return self.mint(family, keeper, ttl, ts)

    def touch(self, mark, caller, tenant, ts):
        self._parse(mark)
        record = self._marks.get(mark)
        if record is None:
            raise ValueError("unknown canary mark")
        self._latest_ts = max(self._latest_ts, ts)

        severity = FAMILIES[record.family]
        if record.home_tenant is not None and tenant != record.home_tenant:
            severity += 1

        if record.revoked:
            return {"status": "revoked", "severity": severity, "deduplicated": False}
        if ts >= record.effective_expiry():
            return {"status": "expired", "severity": severity, "deduplicated": False}

        last_alert = record.last_alert_at.get(caller)
        if last_alert is not None and ts - last_alert < _DEDUP_WINDOW:
            return {"status": "alive", "severity": severity, "deduplicated": True}

        if record.home_tenant is None:
            record.home_tenant = tenant
        record.tenants.add(tenant)
        record.last_alert_at[caller] = ts
        record.events.append(
            {"ts": ts, "caller": caller, "tenant": tenant, "severity": severity}
        )
        return {"status": "alive", "severity": severity, "deduplicated": False}

    def revoke(self, mark, ts):
        self._parse(mark)
        record = self._marks.get(mark)
        if record is None:
            raise ValueError("unknown canary mark")
        record.revoked = True
        self._latest_ts = max(self._latest_ts, ts)

    def report(self, window):
        cutoff = self._latest_ts - window
        rows = []
        for mark, record in self._marks.items():
            events = [event for event in record.events if event["ts"] >= cutoff]
            if not events:
                continue
            rows.append(
                {
                    "mark": mark,
                    "count": len(events),
                    "first_ts": events[0]["ts"],
                    "tenants": sorted({event["tenant"] for event in events}),
                    "last_ts": events[-1]["ts"],
                }
            )
        rows.sort(key=lambda row: (row["first_ts"], row["mark"]))
        return rows

    def summary(self):
        family_counts = {}
        alert_count = 0
        for record in self._marks.values():
            family_counts[record.family] = family_counts.get(record.family, 0) + 1
            alert_count += len(record.events)
        return {
            "marks": len(self._marks),
            "families": family_counts,
            "alerts": alert_count,
        }

    def _parse(self, mark):
        if not isinstance(mark, str):
            raise ValueError("malformed canary mark")
        prefix, separator, tail = mark.rpartition("_")
        if (
            not separator
            or not prefix.startswith(f"{_MARK_PREFIX}_")
            or len(tail) != _TAIL_HEX_LEN
        ):
            raise ValueError("malformed canary mark")
        try:
            int(tail, 16)
        except ValueError as exc:
            raise ValueError("malformed canary mark") from exc

        family = prefix[len(_MARK_PREFIX) + 1 :]
        if family not in FAMILIES:
            raise ValueError("malformed canary mark")

        fragment = tail[:_FRAGMENT_HEX_LEN]
        checksum = tail[_FRAGMENT_HEX_LEN:]
        if checksum != _checksum(f"{prefix}_{fragment}"):
            raise ValueError("forged canary mark")
        return family
