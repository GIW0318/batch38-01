import json
import random
from datetime import datetime, timezone
from urllib.parse import urlsplit


_SIZE_LIMIT = 8 * 1024
_MAX_AGE = 86400
_MAX_SKEW = 300
_DEFAULT_PORTS = {
    "http": 80,
    "https": 443,
    "ws": 80,
    "wss": 443,
    "ftp": 21,
}
_SPECIAL_BLOCKED_URIS = {"self", "inline", "eval", "data"}


class CspReportSink:
    def __init__(self, sample_rate=1.0, per_host_limit=100):
        self.sample_rate = sample_rate
        self.per_host_limit = per_host_limit
        self._received = 0
        self._dropped = 0
        self._counts = {}
        self._host_windows = {}

    def ingest(self, reports, now):
        now_seconds = self._as_timestamp(now)
        for report in self._iter_reports(reports):
            self._received += 1
            try:
                self._ingest_one(report, now_seconds)
            except Exception:
                self._dropped += 1

    def _ingest_one(self, report, now):
        if not isinstance(report, dict) or self._serialized_size(report) > _SIZE_LIMIT:
            self._dropped += 1
            return

        body = report.get("csp-report")
        if not isinstance(body, dict):
            body = report.get("body")
            if not isinstance(body, dict):
                self._dropped += 1
                return

            report_type = report.get("type")
            if report_type is not None and str(report_type).lower() not in {
                "csp-violation",
                "csp-report",
                "csp_report",
            }:
                self._dropped += 1
                return

        document = self._normalized_uri(body.get("document-uri"))
        blocked = self._normalized_blocked_uri(body.get("blocked-uri"))
        directive = self._normalized_directive(body)
        if document is None or blocked is None or directive is None:
            self._dropped += 1
            return

        timestamp = body.get("timestamp", report.get("timestamp"))
        if timestamp is not None:
            try:
                timestamp = self._as_timestamp(timestamp)
            except (TypeError, ValueError, OverflowError):
                self._dropped += 1
                return
            if timestamp < now - _MAX_AGE or timestamp > now + _MAX_SKEW:
                self._dropped += 1
                return

        if not self._sampled():
            self._dropped += 1
            return

        window = (document, int(now // 3600))
        used = self._host_windows.get(window, 0)
        if used >= self.per_host_limit:
            self._dropped += 1
            return
        self._host_windows[window] = used + 1

        key = (document, directive, blocked)
        self._counts[key] = self._counts.get(key, 0) + 1

    def summary(self, top=5):
        rows = sorted(self._counts.items(), key=lambda item: (-item[1], item[0]))
        if top is not None:
            rows = rows[: max(0, top)]
        return [
            {
                "document": document,
                "directive": directive,
                "blocked": blocked,
                "count": count,
            }
            for (document, directive, blocked), count in rows
        ]

    def violations(self):
        return {
            "received": self._received,
            "dropped": self._dropped,
            "unique": len(self._counts),
        }

    @staticmethod
    def _iter_reports(reports):
        if reports is None:
            return
        if isinstance(reports, dict):
            yield reports
            return
        if isinstance(reports, (str, bytes, bytearray)):
            yield reports
            return
        try:
            yield from reports
        except TypeError:
            yield reports

    @staticmethod
    def _serialized_size(report):
        try:
            encoded = json.dumps(
                report,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        except (TypeError, ValueError):
            return _SIZE_LIMIT + 1
        return len(encoded)

    @staticmethod
    def _normalized_uri(value):
        if not isinstance(value, str):
            return None
        value = value.strip()
        if not value:
            return None
        try:
            parsed = urlsplit(value)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError:
            return None
        if not hostname:
            return None

        host = hostname.lower()
        default_port = _DEFAULT_PORTS.get(parsed.scheme.lower())
        if port is not None and port != default_port:
            if ":" in host:
                return "[{}]:{}".format(host, port)
            return "{}:{}".format(host, port)
        return host

    @classmethod
    def _normalized_blocked_uri(cls, value):
        if not isinstance(value, str):
            return None
        token = value.strip().lower()
        if token in _SPECIAL_BLOCKED_URIS or token.startswith("data:"):
            if token.startswith("data:"):
                return "data"
            return token
        return cls._normalized_uri(value)

    @staticmethod
    def _normalized_directive(body):
        for field in ("effective-directive", "violated-directive", "directive"):
            value = body.get(field)
            if not isinstance(value, str):
                continue
            directive = value.strip().lower().split(None, 1)[0].rstrip(";")
            if directive:
                return directive
        return None

    @staticmethod
    def _as_timestamp(value):
        if isinstance(value, bool):
            raise ValueError("boolean is not a timestamp")
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("empty timestamp")
            try:
                return float(value)
            except ValueError:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.timestamp()
        raise TypeError("unsupported timestamp")

    def _sampled(self):
        rate = float(self.sample_rate)
        if rate >= 1:
            return True
        if rate <= 0:
            return False
        return random.random() < rate
