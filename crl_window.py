import re


_HEX_SERIAL = re.compile(r"\A[0-9A-Fa-f]+\Z")
_REMOVE_FROM_CRL = "removeFromCRL"


def _normalize_serial(value):
    if isinstance(value, bool):
        raise ValueError("invalid serial number")
    if isinstance(value, int):
        if value < 0:
            raise ValueError("negative serial number")
        text = format(value, "X")
    elif isinstance(value, str):
        if not _HEX_SERIAL.fullmatch(value):
            raise ValueError("invalid serial number")
        text = value
    else:
        raise ValueError("invalid serial number")

    return text.upper().lstrip("0") or "0"


def _number(value, name):
    if isinstance(value, bool):
        raise ValueError("invalid %s" % name)
    if isinstance(value, str):
        if not value.isdigit():
            raise ValueError("invalid %s" % name)
        value = int(value)
    if not isinstance(value, int) or value < 0:
        raise ValueError("invalid %s" % name)
    return value


def _time(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("invalid %s" % name)
    return value


def _parse_crl(crl, name):
    if not isinstance(crl, dict):
        raise ValueError("%s must be a mapping" % name)

    issuer = crl.get("issuer")
    if not isinstance(issuer, str) or not issuer:
        raise ValueError("%s has an empty issuer" % name)

    this_update = _time(crl.get("this_update"), "this_update")
    next_update = _time(crl.get("next_update"), "next_update")
    if this_update > next_update:
        raise ValueError("%s has an invalid validity window" % name)

    critical = crl.get("critical_extensions") or []
    if not isinstance(critical, (list, tuple, set, frozenset)):
        raise ValueError("%s has invalid critical extensions" % name)
    if any(not isinstance(oid, str) for oid in critical):
        raise ValueError("%s has invalid critical extensions" % name)
    if critical:
        raise ValueError("%s has unknown critical extensions" % name)

    entries = crl.get("entries")
    if entries is None:
        entries = []
    if not isinstance(entries, (list, tuple)):
        raise ValueError("%s entries must be a sequence" % name)

    parsed = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("%s contains an invalid entry" % name)

        serial = _normalize_serial(entry.get("serial"))
        if serial in parsed:
            raise ValueError("%s contains conflicting serials" % name)

        reason = entry.get("reason")
        if reason is not None and not isinstance(reason, str):
            raise ValueError("%s contains an invalid reason" % name)

        invalidity_date = entry.get("invalidity_date")
        if invalidity_date is not None:
            invalidity_date = _time(invalidity_date, "invalidity_date")

        parsed[serial] = {
            "serial": serial,
            "reason": reason,
            "effective_at": (
                invalidity_date
                if invalidity_date is not None
                else this_update
            ),
        }

    return {
        "issuer": issuer,
        "this_update": this_update,
        "next_update": next_update,
        "crl_number": (
            _number(crl["crl_number"], "crl_number")
            if "crl_number" in crl
            else None
        ),
        "entries": parsed,
    }


class RevocationWindow:
    def __init__(self):
        self._state = None

    def load(self, base, delta, now):
        now = _time(now, "now")
        base_crl = _parse_crl(base, "base CRL")

        this_update = base_crl["this_update"]
        next_update = base_crl["next_update"]
        entries = dict(base_crl["entries"])

        if delta is not None:
            delta_crl = _parse_crl(delta, "delta CRL")

            if base_crl["crl_number"] is None:
                raise ValueError("base CRL has no CRL number")
            if "base_number" not in delta:
                raise ValueError("delta CRL has no base number")

            base_number = _number(delta["base_number"], "base_number")
            if base_number != base_crl["crl_number"]:
                raise ValueError("delta CRL does not match the base CRL")
            if delta_crl["this_update"] < base_crl["this_update"]:
                raise ValueError("delta CRL is older than the base CRL")
            if delta_crl["issuer"] != base_crl["issuer"]:
                raise ValueError("delta CRL issuer does not match the base CRL")

            this_update = max(this_update, delta_crl["this_update"])
            next_update = min(next_update, delta_crl["next_update"])

            additions = []
            for serial, delta_entry in delta_crl["entries"].items():
                if delta_entry["reason"] == _REMOVE_FROM_CRL:
                    entries.pop(serial, None)
                else:
                    additions.append((serial, delta_entry))

            for serial, delta_entry in additions:
                current = entries.get(serial)
                if current is None:
                    entries[serial] = delta_entry
                elif (
                    current["reason"] != delta_entry["reason"]
                    or current["effective_at"] != delta_entry["effective_at"]
                ):
                    raise ValueError("conflicting serial in delta CRL")

        if this_update > next_update:
            raise ValueError("CRLs have no overlapping validity window")
        if not this_update <= now <= next_update:
            raise ValueError("CRL is not valid at the requested time")

        self._state = {
            "issuer": base_crl["issuer"],
            "this_update": this_update,
            "next_update": next_update,
            "entries": entries,
        }
        return None

    def check(self, serial, issuer, now):
        if self._state is None:
            raise ValueError("no CRL has been loaded")
        if not isinstance(issuer, str) or not issuer:
            raise ValueError("empty issuer")
        if issuer != self._state["issuer"]:
            raise ValueError("issuer does not match the loaded CRL")

        now = _time(now, "now")
        if not (
            self._state["this_update"]
            <= now
            <= self._state["next_update"]
        ):
            raise ValueError("CRL is not valid at the requested time")

        entry = self._state["entries"].get(_normalize_serial(serial))
        if entry is None:
            return {"revoked": False, "reason": None, "effective_at": None}
        return {
            "revoked": True,
            "reason": entry["reason"],
            "effective_at": entry["effective_at"],
        }

    def window(self):
        if self._state is None:
            return {}
        return {
            "entries": len(self._state["entries"]),
            "this_update": self._state["this_update"],
            "next_update": self._state["next_update"],
        }
