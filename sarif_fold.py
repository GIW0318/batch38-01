import posixpath
from urllib.parse import unquote


SARIF_VERSION = "2.1.0"

LEVEL_MAP = {
    "error": "high",
    "warning": "medium",
    "note": "low",
    "none": "info",
}

SUPPRESSED_STATUSES = ("accepted", "underReview")


class SarifFold:
    def __init__(self):
        self._runs = 0
        self._skipped = 0
        self._results = []

    def merge(self, runs):
        if not runs:
            raise ValueError("at least one SARIF run is required")
        for run in runs:
            self._validate_run(run)
        for run in runs:
            self._runs += 1
            driver = run.get("tool", {}).get("driver", {})
            rules = driver.get("rules")
            base_ids = run.get("originalUriBaseIds") or {}
            for result in run.get("results") or []:
                record = self._build_record(result, rules, base_ids)
                if record is None:
                    self._skipped += 1
                else:
                    self._results.append(record)

    def dedupe(self):
        seen = set()
        kept = []
        for record in self._results:
            fingerprints = record.get("partialFingerprints")
            if fingerprints:
                key = ("fingerprint", tuple(sorted(fingerprints.items())))
            else:
                key = (
                    "location",
                    record["ruleId"],
                    record["uri"],
                    record["startLine"],
                )
            if key in seen:
                continue
            seen.add(key)
            kept.append(record)
        self._results = kept
        return kept

    def summary(self):
        by_level = {"high": 0, "medium": 0, "low": 0, "info": 0}
        by_rule = {}
        for record in self._results:
            level = record["level"]
            by_level[level] = by_level.get(level, 0) + 1
            rule_id = record["ruleId"]
            by_rule[rule_id] = by_rule.get(rule_id, 0) + 1
        top_rules = sorted(by_rule.items(), key=lambda item: (-item[1], item[0]))
        return {
            "by_level": by_level,
            "by_rule": by_rule,
            "top_rules": top_rules,
        }

    def merge_report(self):
        return {
            "runs": self._runs,
            "results": len(self._results),
            "skipped": self._skipped,
        }

    def _validate_run(self, run):
        if not isinstance(run, dict) or run.get("version") != SARIF_VERSION:
            raise ValueError("only SARIF version %s is accepted" % SARIF_VERSION)
        driver = (run.get("tool") or {}).get("driver") or {}
        if not driver.get("name") or not driver.get("version"):
            raise ValueError("run requires tool.driver.name and tool.driver.version")

    def _build_record(self, result, rules, base_ids):
        if not isinstance(result, dict):
            return None
        for suppression in result.get("suppressions") or []:
            if (
                isinstance(suppression, dict)
                and suppression.get("status") in SUPPRESSED_STATUSES
            ):
                return None
        rule_id = self._resolve_rule_id(result, rules)
        location = self._first_location(result, base_ids)
        if rule_id is None or location is None:
            return None
        uri, start_line = location
        return {
            "ruleId": rule_id,
            "level": LEVEL_MAP.get(result.get("level", "warning"), "medium"),
            "uri": uri,
            "startLine": start_line,
            "message": result.get("message"),
            "partialFingerprints": dict(result.get("partialFingerprints") or {}),
            "baselineState": result.get("baselineState"),
        }

    def _resolve_rule_id(self, result, rules):
        index = result.get("ruleIndex")
        if (
            isinstance(rules, list)
            and isinstance(index, int)
            and not isinstance(index, bool)
            and 0 <= index < len(rules)
        ):
            entry = rules[index]
            if isinstance(entry, dict) and entry.get("id"):
                return entry["id"]
        rule_id = result.get("ruleId")
        return rule_id if rule_id else None

    def _first_location(self, result, base_ids):
        locations = result.get("locations")
        if not isinstance(locations, list) or not locations:
            return None
        first = locations[0]
        if not isinstance(first, dict):
            return None
        physical = first.get("physicalLocation")
        if not isinstance(physical, dict):
            return None
        artifact = physical.get("artifactLocation") or {}
        region = physical.get("region") or {}
        uri = artifact.get("uri")
        start_line = region.get("startLine")
        if not isinstance(uri, str) or not uri:
            return None
        if not isinstance(start_line, int) or isinstance(start_line, bool):
            return None
        base_uri = self._base_uri(artifact.get("uriBaseId"), base_ids)
        if base_uri and not base_uri.endswith("/") and not uri.startswith("/"):
            base_uri += "/"
        return self._normalize_uri(base_uri + uri), start_line

    def _base_uri(self, base_id, base_ids, seen=None):
        if not base_id or not isinstance(base_ids, dict):
            return ""
        entry = base_ids.get(base_id)
        if not isinstance(entry, dict):
            return ""
        seen = seen if seen is not None else set()
        if base_id in seen:
            return ""
        seen.add(base_id)
        uri = entry.get("uri") or ""
        parent = entry.get("uriBaseId")
        if parent:
            uri = self._base_uri(parent, base_ids, seen) + uri
        return uri

    def _normalize_uri(self, uri):
        if uri.startswith("file://"):
            uri = uri[len("file://"):]
        elif uri.startswith("file:"):
            uri = uri[len("file:"):]
        uri = unquote(uri)
        uri = uri.replace("\\", "/")
        return posixpath.normpath(uri)
