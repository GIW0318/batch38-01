import math

_PREFIX = "CVSS:3.1"

_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
_AC = {"L": 0.77, "H": 0.44}
_PR_U = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_C = {"N": 0.85, "L": 0.68, "H": 0.5}
_UI = {"N": 0.85, "R": 0.62}
_S = {"U", "C"}
_CIA = {"H": 0.56, "L": 0.22, "N": 0.0}
_E = {"X": 1.0, "H": 1.0, "F": 0.97, "P": 0.94, "U": 0.91}
_RL = {"X": 1.0, "U": 1.0, "W": 0.97, "T": 0.96, "O": 0.95}
_RC = {"X": 1.0, "C": 1.0, "R": 0.96, "U": 0.92}
_CIR = {"X": 1.0, "H": 1.5, "M": 1.0, "L": 0.5}

_BASE_KEYS = ("AV", "AC", "PR", "UI", "S", "C", "I", "A")
_TEMPORAL_KEYS = ("E", "RL", "RC")
_ENV_KEYS = ("CR", "IR", "AR", "MAV", "MAC", "MPR", "MUI", "MS", "MC", "MI", "MA")

_VALUES = {
    "AV": _AV, "AC": _AC, "PR": _PR_U, "UI": _UI, "S": _S,
    "C": _CIA, "I": _CIA, "A": _CIA,
    "E": _E, "RL": _RL, "RC": _RC,
    "CR": _CIR, "IR": _CIR, "AR": _CIR,
    "MAV": dict(_AV, X=None), "MAC": dict(_AC, X=None),
    "MPR": dict(_PR_U, X=None), "MUI": dict(_UI, X=None),
    "MS": {"U", "C", "X"},
    "MC": dict(_CIA, X=None), "MI": dict(_CIA, X=None), "MA": dict(_CIA, X=None),
}


def _roundup(value):
    scaled = round(value * 100000)
    if scaled % 10000 == 0:
        return scaled / 100000.0
    return (math.floor(scaled / 10000.0) + 1) / 10.0


def _parse(vector):
    if not isinstance(vector, str):
        raise ValueError("vector must be a string")
    parts = vector.split("/")
    if not parts or parts[0] != _PREFIX:
        raise ValueError("vector must start with %s" % _PREFIX)
    metrics = {}
    for segment in parts[1:]:
        if not segment or ":" not in segment:
            raise ValueError("malformed metric: %r" % segment)
        key, _, value = segment.partition(":")
        if key not in _VALUES:
            raise ValueError("unknown metric: %r" % key)
        if key in metrics:
            raise ValueError("duplicate metric: %r" % key)
        if value not in _VALUES[key]:
            raise ValueError("invalid value %r for metric %r" % (value, key))
        metrics[key] = value
    missing = [k for k in _BASE_KEYS if k not in metrics]
    if missing:
        raise ValueError("missing base metrics: %s" % ",".join(missing))
    return metrics


def _base_scores(m):
    scope_changed = m["S"] == "C"
    pr = (_PR_C if scope_changed else _PR_U)[m["PR"]]
    iss = 1.0 - (1 - _CIA[m["C"]]) * (1 - _CIA[m["I"]]) * (1 - _CIA[m["A"]])
    if scope_changed:
        impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
    else:
        impact = 6.42 * iss
    exploitability = 8.22 * _AV[m["AV"]] * _AC[m["AC"]] * pr * _UI[m["UI"]]
    if impact <= 0:
        base = 0.0
    elif scope_changed:
        base = _roundup(min(1.08 * (impact + exploitability), 10.0))
    else:
        base = _roundup(min(impact + exploitability, 10.0))
    return base, impact, exploitability


def _temporal_factor(m):
    return (_E.get(m.get("E", "X"), 1.0)
            * _RL.get(m.get("RL", "X"), 1.0)
            * _RC.get(m.get("RC", "X"), 1.0))


def _environmental_score(m):
    if not any(k in m for k in _ENV_KEYS):
        return None
    scope = m.get("MS", "X")
    scope = m["S"] if scope == "X" else scope
    scope_changed = scope == "C"

    def pick(mod_key, base_key):
        value = m.get(mod_key, "X")
        return m[base_key] if value == "X" else value

    mav, mac = pick("MAV", "AV"), pick("MAC", "AC")
    mpr, mui = pick("MPR", "PR"), pick("MUI", "UI")
    mc, mi, ma = pick("MC", "C"), pick("MI", "I"), pick("MA", "A")
    cr, ir, ar = (_CIR[m.get(k, "X")] for k in ("CR", "IR", "AR"))

    miss = min(1.0 - (1 - cr * _CIA[mc]) * (1 - ir * _CIA[mi]) * (1 - ar * _CIA[ma]), 0.915)
    if scope_changed:
        mod_impact = 7.52 * (miss - 0.029) - 3.25 * (miss * 0.9731 - 0.02) ** 13
    else:
        mod_impact = 6.42 * miss
    pr = (_PR_C if scope_changed else _PR_U)[mpr]
    mod_exploitability = 8.22 * _AV[mav] * _AC[mac] * pr * _UI[mui]
    if mod_impact <= 0:
        return 0.0
    if scope_changed:
        inner = _roundup(min(1.08 * (mod_impact + mod_exploitability), 10.0))
    else:
        inner = _roundup(min(mod_impact + mod_exploitability, 10.0))
    return _roundup(inner * _temporal_factor(m))


def _profile_key(profile):
    if profile is None:
        return None
    if isinstance(profile, dict):
        return tuple(sorted((repr(k), repr(v)) for k, v in profile.items()))
    return repr(profile)


class CvssEngine:
    def __init__(self):
        self._cache = {}
        self._hits = 0
        self._misses = 0

    def _compute(self, vector):
        metrics = _parse(vector)
        base, impact, exploitability = _base_scores(metrics)
        has_temporal = any(k in metrics for k in _TEMPORAL_KEYS)
        temporal = _roundup(base * _temporal_factor(metrics)) if has_temporal else None
        environmental = _environmental_score(metrics)
        if environmental is not None:
            final = environmental
        elif temporal is not None:
            final = temporal
        else:
            final = base
        return {
            "score": final,
            "base": base,
            "impact": impact,
            "exploitability": exploitability,
            "temporal": temporal,
            "environmental": environmental,
        }

    def score(self, vector, profile=None):
        key = (vector, _profile_key(profile))
        if key in self._cache:
            self._hits += 1
            return self._cache[key]["score"]
        self._misses += 1
        result = self._compute(vector)
        self._cache[key] = result
        return result["score"]

    def batch(self, vectors, profile=None):
        scores = {}
        total = 0
        for vector in vectors:
            total += 1
            if vector not in scores:
                scores[vector] = self.score(vector, profile)
        return {"total": total, "unique": len(scores), "scores": scores}

    def severity(self, score):
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError("score must be a number")
        if not 0.0 <= score <= 10.0:
            raise ValueError("score out of range: %r" % score)
        if score == 0.0:
            return "none"
        if score < 4.0:
            return "low"
        if score < 7.0:
            return "medium"
        if score < 9.0:
            return "high"
        return "critical"

    def breakdown(self, vector, profile=None):
        key = (vector, _profile_key(profile))
        if key in self._cache:
            self._hits += 1
            result = self._cache[key]
        else:
            self._misses += 1
            result = self._compute(vector)
            self._cache[key] = result
        return {
            "exploitability": result["exploitability"],
            "impact": result["impact"],
            "temporal": result["temporal"],
            "environmental": result["environmental"],
        }

    def cache_stats(self):
        return {"hits": self._hits, "misses": self._misses}
