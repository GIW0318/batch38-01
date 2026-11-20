import re
from datetime import datetime, timedelta, timezone

SEVERITY_DAYS = {"critical": 7, "high": 14, "medium": 30, "low": 90}
UNREACHABLE_EXTRA_DAYS = 30
MAX_OPEN_PER_OWNER = 20
DAY_SECONDS = 86400


def _to_date(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).date()


def _version_parts(version):
    return tuple(int(part) for part in re.findall(r"\d+", str(version)))


def _severity_from_cvss(cvss):
    if isinstance(cvss, bool) or not isinstance(cvss, (int, float)):
        raise ValueError("unknown severity: cvss must be a number")
    score = float(cvss)
    if score != score or score < 0 or score > 10:
        raise ValueError("cvss out of range: %r" % (cvss,))
    if score == 0:
        raise ValueError("unknown severity: cvss 0.0")
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"


class VulnTriage:
    def __init__(self, holidays=None):
        self.holidays = {_to_date(h) for h in (holidays or [])}
        self._items = {}
        self._keys = {}
        self._next_id = 1
        self._now = None

    def _touch_clock(self, now):
        if now is not None and (self._now is None or now > self._now):
            self._now = now

    def _get(self, vuln_id):
        try:
            return self._items[vuln_id]
        except KeyError:
            raise KeyError("unknown vuln id: %r" % (vuln_id,))

    def ingest(self, findings, now):
        self._touch_clock(now)
        last_id = None
        for finding in findings:
            last_id = self._ingest_one(finding, now)
        return last_id

    def _ingest_one(self, finding, now):
        cve = finding.get("cve")
        if not isinstance(cve, str) or not cve.strip():
            raise ValueError("cve must be a non-empty string")
        severity = _severity_from_cvss(finding.get("cvss"))
        key = (
            cve.strip().upper(),
            finding.get("package"),
            _version_parts(finding.get("version")),
        )
        existing_id = self._keys.get(key)
        if existing_id is not None:
            item = self._items[existing_id]
            item["cvss"] = finding.get("cvss")
            item["severity"] = severity
            item["reachable"] = bool(finding.get("reachable", True))
            item["kev"] = bool(finding.get("kev", False))
            item["kev_until"] = finding.get("kev_until")
            if item["status"] == "closed":
                item["status"] = "open"
                item["created_at"] = now
                item["closed_at"] = None
                item["close_reason"] = None
                item["exception"] = None
                item["reopen_count"] += 1
            return existing_id
        vuln_id = self._next_id
        self._next_id += 1
        self._keys[key] = vuln_id
        self._items[vuln_id] = {
            "id": vuln_id,
            "key": key,
            "cve": key[0],
            "package": finding.get("package"),
            "version": finding.get("version"),
            "cvss": finding.get("cvss"),
            "severity": severity,
            "reachable": bool(finding.get("reachable", True)),
            "kev": bool(finding.get("kev", False)),
            "kev_until": finding.get("kev_until"),
            "status": "open",
            "created_at": now,
            "closed_at": None,
            "close_reason": None,
            "owner": None,
            "reopen_count": 0,
            "exception": None,
        }
        return vuln_id

    def assign(self, vuln_id, owner, now):
        self._touch_clock(now)
        item = self._get(vuln_id)
        open_for_owner = sum(
            1
            for other in self._items.values()
            if other["owner"] == owner
            and other["status"] == "open"
            and other["id"] != vuln_id
        )
        if open_for_owner >= MAX_OPEN_PER_OWNER:
            raise ValueError(
                "owner %r already has %d open items" % (owner, open_for_owner)
            )
        item["owner"] = owner

    def request_exception(self, vuln_id, until, approver, now):
        self._touch_clock(now)
        item = self._get(vuln_id)
        if until is None or until <= now:
            raise ValueError("exception already expired")
        item["exception"] = {
            "until": until,
            "requester": approver,
            "approved": False,
            "approver": None,
        }

    def approve_exception(self, vuln_id, approver, now):
        self._touch_clock(now)
        item = self._get(vuln_id)
        exc = item["exception"]
        if exc is None or exc["approved"]:
            raise ValueError("no pending exception for vuln %r" % (vuln_id,))
        if exc["until"] <= now:
            raise ValueError("exception already expired")
        if approver == exc["requester"]:
            raise ValueError("exception must be approved by someone else")
        exc["approved"] = True
        exc["approver"] = approver

    def close(self, vuln_id, now, reason):
        self._touch_clock(now)
        item = self._get(vuln_id)
        item["status"] = "closed"
        item["closed_at"] = now
        item["close_reason"] = reason

    def _severity_at(self, item, now):
        if (
            item["kev"]
            and item["kev_until"] is not None
            and item["kev_until"] >= now
        ):
            return "critical"
        return item["severity"]

    def _add_business_days(self, start_ts, days):
        start_date = _to_date(start_ts)
        date = start_date
        added = 0
        while added < days:
            date += timedelta(days=1)
            if date.weekday() < 5 and date not in self.holidays:
                added += 1
        return start_ts + (date - start_date).days * DAY_SECONDS

    def sla(self, vuln_id, now):
        self._touch_clock(now)
        item = self._get(vuln_id)
        severity = self._severity_at(item, now)
        days = SEVERITY_DAYS[severity]
        if not item["reachable"]:
            days += UNREACHABLE_EXTRA_DAYS
        due_at = self._add_business_days(item["created_at"], days)
        exc = item["exception"]
        if exc is not None and exc["approved"] and exc["until"] >= now:
            due_at = max(due_at, exc["until"])
        return {
            "id": vuln_id,
            "severity": severity,
            "days": days,
            "due_at": due_at,
            "reopen_count": item["reopen_count"],
            "status": item["status"],
            "owner": item["owner"],
        }

    def queue(self):
        now = self._now
        open_items = [
            item for item in self._items.values() if item["status"] == "open"
        ]
        by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        overdue = 0
        pending_exceptions = 0
        for item in open_items:
            if now is not None:
                info = self.sla(item["id"], now)
                by_severity[info["severity"]] += 1
                if info["due_at"] < now:
                    overdue += 1
            else:
                by_severity[item["severity"]] += 1
            exc = item["exception"]
            if exc is not None and not exc["approved"]:
                pending_exceptions += 1
        return {
            "open": len(open_items),
            "by_severity": by_severity,
            "overdue": overdue,
            "pending_exceptions": pending_exceptions,
        }
