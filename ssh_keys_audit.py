from __future__ import annotations

import base64
import binascii
import hashlib
import ipaddress
import re
from datetime import date, datetime


class KeyAudit:
    ALLOWED_KEY_TYPES = {
        "ssh-ed25519",
        "ssh-rsa",
        "ecdsa-sha2-nistp256",
    }

    _VALUE_OPTIONS = {
        "command",
        "from",
        "expiry-time",
        "permitopen",
        "environment",
        "principals",
        "tunnel",
    }
    _FLAG_OPTIONS = {
        "no-pty",
        "cert-authority",
        "no-agent-forwarding",
        "no-port-forwarding",
        "no-X11-forwarding",
        "agent-forwarding",
        "port-forwarding",
        "X11-forwarding",
        "restrict",
        "touch-required",
        "verify-required",
    }
    _KNOWN_OPTIONS = _VALUE_OPTIONS | _FLAG_OPTIONS

    _SEVERITY = {
        "revoked": "critical",
        "bad_type": "critical",
        "expired": "high",
        "weak_rsa": "high",
        "bad_from": "high",
        "bad_expiry": "medium",
        "cert_authority": "medium",
        "duplicate": "medium",
        "too_many": "low",
    }
    _SEVERITY_RANK = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
    }

    def __init__(self):
        self._keys = []
        self.keys = self._keys
        self._findings = []
        self.invalid_lines = 0
        self.skipped_lines = 0
        self.parse_errors = []

    def parse(self, text):
        self._keys = []
        self.keys = self._keys
        self._findings = []
        self.invalid_lines = 0
        self.skipped_lines = 0
        self.parse_errors = []

        if text is None:
            return 0
        if not isinstance(text, str):
            raise TypeError("text must be a string")

        lines = text.splitlines()
        accepted = 0
        index = 0
        while index < len(lines):
            raw = lines[index].lstrip("\ufeff").strip()
            index += 1
            if not raw or raw.startswith("#"):
                continue

            logical = raw
            while index < len(lines):
                next_line = lines[index].strip()
                if not self._should_join_continuation(logical, next_line):
                    break
                logical += next_line
                index += 1

            try:
                key = self._parse_line(logical)
            except (ValueError, binascii.Error) as exc:
                self.invalid_lines += 1
                self.skipped_lines = self.invalid_lines
                self.parse_errors.append({"line": index, "error": str(exc)})
                continue

            key["line"] = index
            self._keys.append(key)
            accepted += 1

        return accepted

    def audit(self, policy=None, now=None):
        self._findings = []
        policy = policy or {}
        now_value = self._normalise_date(now if now is not None else datetime.now())

        for key in self._keys:
            self._audit_key(key, policy, now_value)

        self._audit_duplicates()
        self._audit_user_limits(policy)
        self._findings.sort(
            key=lambda item: (
                -self._SEVERITY_RANK.get(item["severity"], 0),
                item.get("line", 0),
                item["code"],
            )
        )
        return self.findings()

    def findings(self):
        return [dict(item) for item in self._findings]

    def _parse_line(self, line):
        first, rest = self._take_first_field(line)
        if not first:
            raise ValueError("missing key type")

        if self._looks_like_options(first):
            options = self._parse_options(first)
            key_type, rest = self._take_token(rest)
        else:
            options = {}
            key_type = first

        if not key_type:
            raise ValueError("missing key type")
        if not re.fullmatch(r"[A-Za-z0-9@._+-]+", key_type):
            raise ValueError("invalid key type")

        blob_token, comment = self._take_token(rest)
        if not blob_token:
            raise ValueError("missing key data")
        if not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", blob_token):
            raise ValueError("invalid base64 key data")

        try:
            blob = base64.b64decode(blob_token, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("invalid base64 key data") from exc
        if not blob:
            raise ValueError("empty key data")

        comment = comment.strip()
        return {
            "key_type": key_type,
            "type": key_type,
            "blob": blob,
            "fingerprint": hashlib.sha256(blob).hexdigest(),
            "comment": comment,
            "user": self._user_from_comment(comment),
            "options": options,
        }

    @staticmethod
    def _take_first_field(text):
        in_quotes = False
        escaped = False
        index = 0
        while index < len(text):
            char = text[index]
            if escaped:
                escaped = False
            elif in_quotes and char == "\\":
                escaped = True
            elif char == '"':
                in_quotes = not in_quotes
            elif char.isspace() and not in_quotes:
                break
            index += 1

        if in_quotes or escaped:
            raise ValueError("unterminated quoted option")
        return text[:index], text[index:].lstrip()

    @staticmethod
    def _take_token(text):
        text = text.lstrip()
        if not text:
            return "", ""
        match = re.search(r"\s", text)
        if match is None:
            return text, ""
        return text[: match.start()], text[match.start() :].lstrip()

    def _looks_like_options(self, field):
        if field in self._KNOWN_OPTIONS:
            return True
        return "=" in field or "," in field

    def _parse_options(self, token):
        options = {}
        for part in self._split_option_segments(token):
            name, separator, raw_value = part.partition("=")
            if not name or not re.fullmatch(r"[A-Za-z0-9-]+", name):
                raise ValueError("invalid option name")
            if name not in self._KNOWN_OPTIONS:
                raise ValueError(f"unsupported option: {name}")
            if name in options:
                raise ValueError(f"conflicting option: {name}")

            if name in self._FLAG_OPTIONS:
                if separator:
                    raise ValueError(f"option does not take a value: {name}")
                options[name] = True
            else:
                if not separator:
                    raise ValueError(f"option requires a value: {name}")
                options[name] = self._unquote_option_value(raw_value)
        if not options:
            raise ValueError("empty options")
        return options

    @staticmethod
    def _split_option_segments(token):
        segments = []
        current = []
        in_quotes = False
        escaped = False
        for char in token:
            if escaped:
                current.append(char)
                escaped = False
            elif in_quotes and char == "\\":
                current.append(char)
                escaped = True
            elif char == '"':
                current.append(char)
                in_quotes = not in_quotes
            elif char == "," and not in_quotes:
                segments.append("".join(current))
                current = []
            else:
                current.append(char)

        if in_quotes or escaped:
            raise ValueError("unterminated quoted option")
        segments.append("".join(current))
        if any(not segment for segment in segments):
            raise ValueError("empty option")
        return segments

    @staticmethod
    def _unquote_option_value(raw_value):
        if not raw_value:
            return ""
        if not raw_value.startswith('"'):
            if '"' in raw_value:
                raise ValueError("invalid quoted option value")
            return raw_value
        if len(raw_value) < 2 or not raw_value.endswith('"'):
            raise ValueError("unterminated quoted option value")

        value = []
        index = 1
        end = len(raw_value) - 1
        while index < end:
            char = raw_value[index]
            if char == "\\":
                index += 1
                if index >= end:
                    raise ValueError("invalid escape in option value")
                value.append(raw_value[index])
            elif char == '"':
                raise ValueError("invalid quote in option value")
            else:
                value.append(char)
            index += 1
        return "".join(value)

    def _should_join_continuation(self, current, next_line):
        if not next_line or next_line.startswith("#"):
            return False

        try:
            first, rest = self._take_first_field(current)
            if self._looks_like_options(first):
                self._parse_options(first)
                _, rest = self._take_token(rest)
            blob_token, comment = self._take_token(rest)
        except ValueError:
            return False

        if comment or not blob_token:
            return False
        if not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", blob_token):
            return False

        next_first, _ = self._take_token(next_line)
        if not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", next_first):
            return False
        return next_first not in self._KNOWN_OPTIONS

    @staticmethod
    def _user_from_comment(comment):
        if not comment:
            return ""
        return comment.split("@", 1)[0].strip()

    def _audit_key(self, key, policy, now_value):
        options = key["options"]
        fingerprint = key["fingerprint"]

        revoked = {self._normalise_fingerprint(item) for item in policy.get("revoked", [])}
        if fingerprint.lower() in revoked:
            self._add_finding(
                "revoked",
                key,
                "key fingerprint is revoked",
                fingerprint=fingerprint,
            )

        allowed_types = policy.get("allowed_types")
        if allowed_types is None:
            allowed_types = self.ALLOWED_KEY_TYPES
        allowed_types = {str(item) for item in allowed_types}
        if key["key_type"] not in allowed_types:
            self._add_finding(
                "bad_type",
                key,
                f"key type is not allowed: {key['key_type']}",
                fingerprint=fingerprint,
            )

        expiry = options.get("expiry-time")
        if expiry is not None:
            try:
                expiry_value = self._normalise_date(expiry)
            except ValueError:
                self._add_finding(
                    "bad_expiry",
                    key,
                    f"invalid expiry-time: {expiry}",
                    fingerprint=fingerprint,
                )
            else:
                if expiry_value < now_value:
                    self._add_finding(
                        "expired",
                        key,
                        f"key expired on {expiry}",
                        fingerprint=fingerprint,
                        expiry=expiry_value,
                        now=now_value,
                    )

        min_rsa_bits = policy.get("min_rsa_bits", 2048)
        if key["key_type"] == "ssh-rsa" and min_rsa_bits is not None:
            bits = self._rsa_modulus_bits(key["blob"])
            if bits is not None and bits < int(min_rsa_bits):
                self._add_finding(
                    "weak_rsa",
                    key,
                    f"RSA key is only {bits} bits",
                    fingerprint=fingerprint,
                    bits=bits,
                    min_bits=int(min_rsa_bits),
                )

        if "from" in options and not self._valid_from_list(options["from"]):
            self._add_finding(
                "bad_from",
                key,
                "from option contains an invalid address list",
                fingerprint=fingerprint,
            )

        if options.get("cert-authority") is True:
            self._add_finding(
                "cert_authority",
                key,
                "key is trusted as a certificate authority",
                fingerprint=fingerprint,
            )

    def _audit_duplicates(self):
        groups = {}
        for key in self._keys:
            groups.setdefault(key["fingerprint"], []).append(key)

        for entries in groups.values():
            if len({entry["user"] for entry in entries}) < 2:
                continue
            first = entries[0]
            for entry in entries[1:]:
                if entry["user"] == first["user"]:
                    continue
                self._add_finding(
                    "duplicate",
                    entry,
                    "same public key is used by multiple users",
                    fingerprint=entry["fingerprint"],
                    duplicate_of=first["user"],
                )

    def _audit_user_limits(self, policy):
        max_keys = policy.get("max_keys_per_user")
        if max_keys is None:
            return

        max_keys = int(max_keys)
        counts = {}
        for key in self._keys:
            counts[key["user"]] = counts.get(key["user"], 0) + 1

        for user, count in counts.items():
            if count > max_keys:
                self._add_finding(
                    "too_many",
                    None,
                    f"user {user or '<unknown>'} has {count} keys; limit is {max_keys}",
                    user=user,
                    count=count,
                    max_keys=max_keys,
                )

    def _add_finding(self, code, key, message, **extra):
        severity = self._SEVERITY.get(code, "medium")
        finding = {
            "code": code,
            "severity": severity,
            "message": message,
        }
        if key is not None:
            finding.update(
                {
                    "line": key.get("line", 0),
                    "key_type": key["key_type"],
                    "user": key["user"],
                    "comment": key["comment"],
                }
            )
        finding.update(extra)
        self._findings.append(finding)

    @staticmethod
    def _normalise_date(value):
        if isinstance(value, datetime):
            return int(value.strftime("%Y%m%d"))
        if isinstance(value, date):
            return int(value.strftime("%Y%m%d"))

        text = str(value).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            text = text.replace("-", "")
        if not re.fullmatch(r"\d{8}(\d{4}(\d{2})?)?", text):
            raise ValueError(f"invalid date: {value}")
        return int(text)

    @staticmethod
    def _normalise_fingerprint(value):
        if isinstance(value, bytes):
            return value.hex().lower()

        text = str(value).strip()
        if text.upper().startswith("SHA256:"):
            payload = text[7:]
            if re.fullmatch(r"[0-9A-Fa-f]{64}", payload):
                return payload.lower()
            payload += "=" * (-len(payload) % 4)
            try:
                return base64.b64decode(payload, validate=True).hex()
            except (ValueError, binascii.Error):
                return text.lower()
        return text.lower()

    @staticmethod
    def _valid_from_list(value):
        patterns = str(value).split(",")
        if not patterns:
            return False
        return all(KeyAudit._valid_from_pattern(item) for item in patterns)

    @staticmethod
    def _valid_from_pattern(value):
        pattern = value.strip()
        if pattern.startswith("!"):
            pattern = pattern[1:].strip()
        if not pattern:
            return False

        try:
            ipaddress.ip_network(pattern, strict=False)
            return True
        except ValueError:
            pass

        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-*?"
        if any(char not in allowed for char in pattern):
            return False
        labels = pattern.split(".")
        return bool(labels) and all(label and len(label) <= 63 for label in labels)

    @staticmethod
    def _rsa_modulus_bits(blob):
        try:
            offset = 0

            def read_string():
                nonlocal offset
                if offset + 4 > len(blob):
                    raise ValueError("truncated key")
                length = int.from_bytes(blob[offset : offset + 4], "big")
                offset += 4
                if offset + length > len(blob):
                    raise ValueError("truncated key")
                data = blob[offset : offset + length]
                offset += length
                return data

            read_string()
            read_string()
            modulus = read_string()
            return int.from_bytes(modulus, "big").bit_length()
        except ValueError:
            return None
