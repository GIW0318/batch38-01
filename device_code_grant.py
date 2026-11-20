class DeviceGrant:
    def __init__(self, apps, allowed_perms, ttl=300):
        self.apps = apps
        self.allowed_perms = allowed_perms
        self.ttl = ttl

    def begin(self, app_key, fingerprint, perms, now):
        return None

    def claim(self, short_code, account, now):
        return None

    def redeem(self, handle, fingerprint, now):
        return None

    def revoke_subject(self, account, now):
        return None

    def snapshot(self):
        return {}
import secrets
import threading


INVALID_GRANT = "invalid grant"

PENDING = "pending"
CLAIMED = "claimed"
REDEEMED = "redeemed"
REVOKED = "revoked"

UNREDEEMED_STATUSES = (PENDING, CLAIMED)
MAX_PENDING_PER_FINGERPRINT = 3

FULLWIDTH_DIGITS = {ord(chr(0xFF10 + i)): str(i) for i in range(10)}


class DeviceGrant:
    def __init__(self, apps, allowed_perms, ttl=300):
        self.apps = apps
        self.allowed_perms = allowed_perms
        self.ttl = ttl
        self._grants = {}
        self._codes = {}
        self._lock = threading.RLock()

    def begin(self, app_key, fingerprint, perms, now):
        if app_key not in self.apps:
            raise ValueError("unknown app")
        if not fingerprint or not str(fingerprint).strip():
            raise ValueError("fingerprint is required")

        deduped_perms = list(dict.fromkeys(perms))
        if not deduped_perms:
            raise ValueError("perms are required")
        app_perms = self.apps[app_key].get("allowed_perms", self.allowed_perms)
        if any(perm not in self.allowed_perms or perm not in app_perms
               for perm in deduped_perms):
            raise ValueError("perm outside whitelist")

        with self._lock:
            active = sum(1 for grant in self._grants.values()
                         if grant["fingerprint"] == fingerprint
                         and grant["status"] in UNREDEEMED_STATUSES)
            if active >= MAX_PENDING_PER_FINGERPRINT:
                raise ValueError("too many pending grants for fingerprint")

            handle = secrets.token_hex(16)
            while handle in self._grants:
                handle = secrets.token_hex(16)

            short_code = f"{secrets.randbelow(10 ** 6):06d}"
            while short_code in self._codes:
                short_code = f"{secrets.randbelow(10 ** 6):06d}"

            self._grants[handle] = {
                "app_key": app_key,
                "fingerprint": fingerprint,
                "perms": deduped_perms,
                "short_code": short_code,
                "expires_at": now + self.ttl,
                "status": PENDING,
                "account": None,
            }
            self._codes[short_code] = handle

            return {
                "handle": handle,
                "short_code": short_code,
                "expires_at": now + self.ttl,
            }

    def claim(self, short_code, account, now):
        normalized = str(short_code).strip().translate(FULLWIDTH_DIGITS)
        if len(normalized) != 6 or not normalized.isdigit():
            raise ValueError(INVALID_GRANT)

        with self._lock:
            handle = self._codes.get(normalized)
            grant = self._grants.get(handle) if handle else None
            if grant is None or grant["status"] != PENDING:
                raise ValueError(INVALID_GRANT)
            if now >= grant["expires_at"]:
                raise ValueError(INVALID_GRANT)

            grant["status"] = CLAIMED
            grant["account"] = account
            return {
                "handle": handle,
                "account": account,
                "expires_at": grant["expires_at"],
            }

    def redeem(self, handle, fingerprint, now):
        with self._lock:
            grant = self._grants.get(handle)
            if grant is None or grant["status"] != CLAIMED:
                raise ValueError(INVALID_GRANT)
            if grant["fingerprint"] != fingerprint:
                raise ValueError(INVALID_GRANT)
            if now >= grant["expires_at"]:
                raise ValueError(INVALID_GRANT)

            grant["status"] = REDEEMED
            return {
                "handle": handle,
                "subject": grant["account"],
                "perms": list(grant["perms"]),
                "expires_at": grant["expires_at"],
            }

    def revoke_subject(self, account, now):
        with self._lock:
            for grant in self._grants.values():
                if (grant["account"] == account
                        and grant["status"] in UNREDEEMED_STATUSES):
                    grant["status"] = REVOKED

    def snapshot(self):
        with self._lock:
            counts = {PENDING: 0, CLAIMED: 0, REDEEMED: 0, REVOKED: 0}
            for grant in self._grants.values():
                counts[grant["status"]] += 1
            return {
                "pending": counts[PENDING],
                "claimed": counts[CLAIMED],
                "redeemed": counts[REDEEMED],
                "revoked": counts[REVOKED],
            }
