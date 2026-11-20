import copy
from collections.abc import Mapping


class CnameAudit:
    _MAX_HOPS = 8
    _DANGLING_SCORE = 60
    _REASON_SCORES = {
        "conflict": 100,
        "loop": 90,
        "too_deep": 80,
    }
    _ADDRESS_TYPES = {"A", "AAAA"}
    _REQUIRED_RECORD_FIELDS = {"name", "type", "value", "ttl", "apex"}

    def __init__(self):
        self._scanned = 0
        self._risks = {}

    @staticmethod
    def _normalize_name(value):
        if not isinstance(value, str):
            raise ValueError("DNS name must be a string")
        if not value or value != value.strip() or any(char.isspace() for char in value):
            raise ValueError("invalid DNS name")
        normalized = value.lower().rstrip(".")
        if not normalized:
            raise ValueError("invalid DNS name")
        return normalized

    @classmethod
    def _normalize_records(cls, records):
        if isinstance(records, (str, bytes)) or not hasattr(records, "__iter__"):
            raise ValueError("records must be an iterable of records")

        normalized_records = []
        for record in records:
            if not isinstance(record, Mapping):
                raise ValueError("record must be a mapping")
            if not cls._REQUIRED_RECORD_FIELDS.issubset(record):
                raise ValueError("record is missing required fields")

            name = cls._normalize_name(record["name"])

            record_type = record["type"]
            if not isinstance(record_type, str) or not record_type.strip():
                raise ValueError("record type must be a non-empty string")
            record_type = record_type.strip().upper()

            value = record["value"]
            if not isinstance(value, str) or not value.strip():
                raise ValueError("record value must be a non-empty string")
            value = value.strip()

            ttl = record["ttl"]
            if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl < 0:
                raise ValueError("record ttl must be a non-negative integer")

            apex = record["apex"]
            if not isinstance(apex, bool):
                raise ValueError("record apex must be a boolean")

            normalized = {
                "name": name,
                "type": record_type,
                "value": value if record_type != "CNAME" else cls._normalize_name(value),
                "ttl": ttl,
                "apex": apex,
            }
            normalized_records.append(normalized)

        return normalized_records

    @classmethod
    def _normalize_fingerprints(cls, fingerprints):
        if fingerprints is None:
            return []
        if isinstance(fingerprints, (str, bytes)) or not hasattr(fingerprints, "__iter__"):
            raise ValueError("fingerprints must be an iterable")

        normalized = []
        for fingerprint in fingerprints:
            if not isinstance(fingerprint, Mapping) or "suffix" not in fingerprint:
                raise ValueError("fingerprint must contain a suffix")

            suffix = cls._normalize_name(fingerprint["suffix"])
            weight = fingerprint.get("weight", 0)
            if (
                isinstance(weight, bool)
                or not isinstance(weight, (int, float))
                or weight < 0
            ):
                raise ValueError("fingerprint weight must be non-negative")

            provider = fingerprint.get("provider", "")
            if provider is None:
                provider = ""
            if not isinstance(provider, str):
                raise ValueError("fingerprint provider must be a string")

            normalized.append(
                {
                    "suffix": suffix,
                    "weight": weight,
                    "provider": provider,
                }
            )

        return normalized

    @staticmethod
    def _is_wildcard(name):
        return name == "*" or name.startswith("*.")

    @staticmethod
    def _matches_suffix(host, suffix):
        if suffix.startswith("*."):
            suffix = suffix[2:]
            return bool(suffix) and host.endswith("." + suffix)
        return host == suffix or host.endswith("." + suffix)

    @classmethod
    def _fingerprint_result(cls, host, fingerprints):
        weight = 0
        provider = None
        for fingerprint in fingerprints:
            if cls._matches_suffix(host, fingerprint["suffix"]):
                weight += fingerprint["weight"]
                if provider is None and fingerprint["provider"]:
                    provider = fingerprint["provider"]
        return weight, provider

    @classmethod
    def _has_conflict(cls, records):
        cname_records = [record for record in records if record["type"] == "CNAME"]
        if not cname_records:
            return False
        has_address = any(record["type"] in cls._ADDRESS_TYPES for record in records)
        return (
            len(cname_records) > 1
            or has_address
            or any(record["apex"] for record in cname_records)
        )

    @classmethod
    def _add_risk(cls, risks, host, reason, score, provider=None):
        risk = {
            "host": host,
            "reason": reason,
            "score": score,
        }
        if provider:
            risk["provider"] = provider
        risks[host] = risk

    def scan(self, records, fingerprints, ts):
        normalized_records = self._normalize_records(records)
        normalized_fingerprints = self._normalize_fingerprints(fingerprints)

        records_by_name = {}
        for record in normalized_records:
            records_by_name.setdefault(record["name"], []).append(record)

        cname_by_name = {}
        conflicts = set()
        for name, name_records in records_by_name.items():
            if self._is_wildcard(name):
                continue
            cname_records = [
                record for record in name_records if record["type"] == "CNAME"
            ]
            if cname_records:
                cname_by_name[name] = cname_records[0]
            if self._has_conflict(name_records):
                conflicts.add(name)

        risks = {}
        for host in cname_by_name:
            cname_records = [
                record
                for record in records_by_name[host]
                if record["type"] == "CNAME"
            ]
            ttl_penalty = 10 if any(record["ttl"] == 0 for record in cname_records) else 0

            if host in conflicts:
                self._add_risk(
                    risks,
                    host,
                    "conflict",
                    self._REASON_SCORES["conflict"] + ttl_penalty,
                )
                continue

            current = host
            visited = {host}
            hops = 0
            result = None

            while True:
                if current != host and current in conflicts:
                    result = ("conflict", self._REASON_SCORES["conflict"], None)
                    break

                current_records = records_by_name.get(current, [])
                current_cname = cname_by_name.get(current)

                if current_cname is None:
                    has_address = any(
                        record["type"] in self._ADDRESS_TYPES
                        for record in current_records
                    )
                    if has_address:
                        break

                    weight, provider = self._fingerprint_result(
                        current, normalized_fingerprints
                    )
                    result = (
                        "dangling",
                        self._DANGLING_SCORE + weight,
                        provider,
                    )
                    break

                target = current_cname["value"]
                if target in visited:
                    result = ("loop", self._REASON_SCORES["loop"], None)
                    break
                if hops >= self._MAX_HOPS:
                    result = ("too_deep", self._REASON_SCORES["too_deep"], None)
                    break

                visited.add(target)
                hops += 1
                current = target

            if result is not None:
                reason, score, provider = result
                self._add_risk(risks, host, reason, score + ttl_penalty, provider)

        self._scanned = len(normalized_records)
        self._risks = risks
        return self._scanned

    def risk(self, host):
        try:
            normalized_host = self._normalize_name(host)
        except ValueError:
            return None
        risk = self._risks.get(normalized_host)
        return copy.deepcopy(risk) if risk is not None else None

    def digest(self):
        high_risk = sorted(
            self._risks.values(),
            key=lambda risk: (-risk["score"], risk["host"]),
        )
        return {
            "scanned": self._scanned,
            "high_risk": copy.deepcopy(high_risk),
        }
