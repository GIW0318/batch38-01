import hashlib


VALID_VERSIONS = frozenset(range(769, 773))
VALID_ACTIONS = frozenset(("allow", "deny", "challenge"))
EXCLUDED_EXTENSIONS = frozenset((0, 16, 21))
MAX_EXTENSIONS = 64


def _is_grease(value):
    if not isinstance(value, int) or value < 0:
        return False
    high_byte = (value >> 8) & 0xFF
    low_byte = value & 0xFF
    return high_byte == low_byte and (high_byte & 0x0F) == 0x0A


def _as_int_list(raw, field_name):
    if not isinstance(raw, list):
        raise ValueError("%s must be a list" % field_name)
    values = []
    for item in raw:
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError("%s contains a non-integer value" % field_name)
        if item < 0:
            raise ValueError("%s contains a negative value" % field_name)
        values.append(item)
    return values


class Ja3Index:
    def __init__(self):
        self._policies = []
        self._fingerprints = set()
        self._hits = 0
        self._rejections = 0
        self._last_fingerprint = None
        self._last_version = None

    def parse(self, hello):
        if not isinstance(hello, dict):
            raise ValueError("hello must be a dict")

        version = hello.get("version")
        if not isinstance(version, int) or isinstance(version, bool):
            raise ValueError("version is missing or not an integer")
        if version not in VALID_VERSIONS:
            raise ValueError("unsupported TLS version: %r" % (version,))

        ciphers = _as_int_list(hello.get("ciphers", []), "ciphers")
        ciphers = [cipher for cipher in ciphers if not _is_grease(cipher)]
        if len(ciphers) % 2 != 0:
            raise ValueError("cipher list has an odd length")

        raw_extensions = _as_int_list(hello.get("extensions", []), "extensions")
        if len(raw_extensions) > MAX_EXTENSIONS:
            raise ValueError("too many extensions: %d" % len(raw_extensions))
        extensions = []
        seen_extensions = set()
        for extension in raw_extensions:
            if _is_grease(extension) or extension in EXCLUDED_EXTENSIONS:
                continue
            if extension in seen_extensions:
                continue
            seen_extensions.add(extension)
            extensions.append(extension)

        curves = [
            curve
            for curve in _as_int_list(hello.get("curves", []), "curves")
            if not _is_grease(curve)
        ]
        point_formats = [
            point_format
            for point_format in _as_int_list(
                hello.get("point_formats", []), "point_formats"
            )
            if not _is_grease(point_format)
        ]

        parsed = {
            "version": version,
            "ciphers": ciphers,
            "extensions": extensions,
            "curves": curves,
            "point_formats": point_formats,
        }
        ja3 = ",".join(
            (
                str(version),
                "-".join(str(value) for value in ciphers),
                "-".join(str(value) for value in extensions),
                "-".join(str(value) for value in curves),
                "-".join(str(value) for value in point_formats),
            )
        )
        digest = hashlib.md5(ja3.encode("utf-8")).hexdigest()
        self._fingerprints.add(digest)
        self._last_fingerprint = digest
        self._last_version = version
        return parsed

    def fingerprint(self, hello):
        self.parse(hello)
        return self._last_fingerprint

    def match(self, policy):
        if not isinstance(policy, list):
            raise ValueError("policy must be a list of entries")
        if self._last_fingerprint is None:
            return {"action": "default", "md5": None}

        for entry in policy:
            if not isinstance(entry, dict):
                continue
            md5 = entry.get("md5")
            if not isinstance(md5, str) or md5.lower() != self._last_fingerprint:
                continue
            min_version = entry.get("min_version", 0)
            if isinstance(min_version, int) and self._last_version < min_version:
                continue

            action = entry.get("action", "default")
            self._hits += 1
            if action == "deny":
                self._rejections += 1
            return {"action": action, "md5": self._last_fingerprint}

        return {"action": "default", "md5": self._last_fingerprint}

    def add_policy(self, entry):
        if not isinstance(entry, dict):
            raise ValueError("policy entry must be a dict")

        action = entry.get("action")
        if action not in VALID_ACTIONS:
            raise ValueError("unknown policy action: %r" % (action,))

        min_version = entry.get("min_version", 0)
        if (
            not isinstance(min_version, int)
            or isinstance(min_version, bool)
            or min_version < 0
            or (min_version != 0 and min_version not in VALID_VERSIONS)
        ):
            raise ValueError("invalid min_version: %r" % (min_version,))

        md5 = entry.get("md5")
        if not isinstance(md5, str) or len(md5) != 32:
            raise ValueError("md5 must be a 32-character hex string")
        md5 = md5.lower()
        if any(char not in "0123456789abcdef" for char in md5):
            raise ValueError("md5 must be a 32-character hex string")
        if any(stored["md5"] == md5 for stored in self._policies):
            raise ValueError("duplicate policy for md5: %s" % md5)

        self._policies.append(
            {"md5": md5, "action": action, "min_version": min_version}
        )

    def catalog(self):
        return {
            "fingerprints": len(self._fingerprints),
            "policies": len(self._policies),
            "hits": self._hits,
            "rejections": self._rejections,
        }
