import ipaddress
import re
import time
import uuid


DEFAULT_PORT = 443
IDLE_TIMEOUT_SECONDS = 300
DEFAULT_MAX_PER_CLIENT = 4

REASON_METHOD = "method_not_connect"
REASON_MALFORMED = "malformed_authority"
REASON_HEADER_INJECTION = "header_injection"
REASON_PORT = "port_not_allowed"
REASON_BLOCKED_IP = "blocked_ip_address"
REASON_BLOCKED_DNS = "blocked_dns_address"
REASON_SNI = "sni_mismatch"
REASON_SUFFIX = "suffix_not_allowed"
REASON_LIMIT = "client_tunnel_limit"

_INTEGER_IP = re.compile(r"[0-9a-fx]+$")


class GuardDenial(Exception):
    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason


class ConnectGuard:
    def __init__(self, resolver, policy):
        self.resolver = resolver
        self.policy = policy
        self._tunnels = {}
        self._rejected = {}

    def authorize(self, method, target, headers, policy=None):
        rules = policy if policy is not None else self.policy
        headers = headers or {}
        try:
            if method != "CONNECT":
                raise GuardDenial(REASON_METHOD, "only CONNECT requests are accepted")
            self._reject_header_injection(headers)
            host, port = self._parse_authority(target)
            host = self._normalize_host(host)
            if port not in rules.get("ports", (443, 8443)):
                raise GuardDenial(REASON_PORT, "port %s is not allowlisted" % port)
            ip = self._parse_ip(host)
            if ip is not None:
                self._ensure_ip_allowed(ip, rules)
            else:
                self._ensure_suffix_allowed(host, rules)
                self._ensure_dns_public(host, rules)
            self._ensure_sni_matches(headers, host)
            client = headers.get("x-client", "unknown")
            self._reap_idle(time.time())
            if self._active_count(client) >= rules.get("max_per_client", DEFAULT_MAX_PER_CLIENT):
                raise GuardDenial(REASON_LIMIT, "tunnel limit reached for client %s" % client)
            tunnel_id = uuid.uuid4().hex
            now = time.time()
            self._tunnels[tunnel_id] = {
                "client": client,
                "host": host,
                "port": port,
                "created_at": now,
                "last_seen": now,
            }
            return {"host": host, "port": port, "tunnel_id": tunnel_id}
        except GuardDenial as denial:
            self._rejected[denial.reason] = self._rejected.get(denial.reason, 0) + 1
            raise ValueError(str(denial)) from denial

    def release(self, tunnel_id, now):
        self._tunnels.pop(tunnel_id, None)
        return None

    def tunnels(self):
        self._reap_idle(time.time())
        return {
            "active": len(self._tunnels),
            "rejected": dict(self._rejected),
        }

    def _reject_header_injection(self, headers):
        for name, value in headers.items():
            blob = "%s%s" % (name, value)
            if any(ch in blob for ch in ("\r", "\n", "\0")):
                raise GuardDenial(
                    REASON_HEADER_INJECTION,
                    "CR/LF/NUL characters are not allowed in headers",
                )

    def _parse_authority(self, target):
        if not isinstance(target, str) or not target:
            raise GuardDenial(REASON_MALFORMED, "authority must be a non-empty host:port")
        if any(ch == "\0" or ch.isspace() for ch in target):
            raise GuardDenial(REASON_MALFORMED, "whitespace and NUL characters are not allowed in authority")
        if "@" in target:
            raise GuardDenial(REASON_MALFORMED, "userinfo is not allowed in authority")
        if any(ch in target for ch in ("/", "?", "#", "\\")):
            raise GuardDenial(REASON_MALFORMED, "authority must contain only host and port")

        if target.startswith("["):
            close = target.find("]")
            if close < 0 or "[" in target[1:]:
                raise GuardDenial(REASON_MALFORMED, "malformed IPv6 literal")
            host = target[1:close]
            remainder = target[close + 1:]
            if not host:
                raise GuardDenial(REASON_MALFORMED, "empty IPv6 literal")
            if remainder == "":
                return host, DEFAULT_PORT
            if not remainder.startswith(":") or remainder == ":":
                raise GuardDenial(REASON_MALFORMED, "malformed authority port")
            return host, self._parse_port(remainder[1:])

        if "[" in target or "]" in target:
            raise GuardDenial(REASON_MALFORMED, "malformed IPv6 literal")
        if target.count(":") > 1:
            raise GuardDenial(REASON_MALFORMED, "IPv6 literals must be wrapped in brackets")
        if ":" in target:
            host, port_text = target.rsplit(":", 1)
            if not host:
                raise GuardDenial(REASON_MALFORMED, "empty host")
            return host, self._parse_port(port_text)
        return target, DEFAULT_PORT

    def _parse_port(self, port_text):
        if not port_text or not port_text.isdigit():
            raise GuardDenial(REASON_MALFORMED, "port must be a decimal number")
        port = int(port_text, 10)
        if not 1 <= port <= 65535:
            raise GuardDenial(REASON_MALFORMED, "port out of range")
        return port

    def _normalize_host(self, host):
        host = host.lower().rstrip(".")
        if not host:
            raise GuardDenial(REASON_MALFORMED, "empty host")
        if ".." in host:
            raise GuardDenial(REASON_MALFORMED, "empty label in host")
        return host.encode("idna").decode("ascii")

    def _parse_ip(self, host):
        try:
            return ipaddress.ip_address(host)
        except ValueError:
            pass
        integer = self._parse_radix_integer(host)
        if integer is not None:
            if integer > 0xFFFFFFFF:
                raise GuardDenial(REASON_MALFORMED, "integer IP out of range")
            return ipaddress.IPv4Address(integer)
        if "." in host:
            parts = host.split(".")
            if 1 < len(parts) <= 4 and all(parts):
                values = []
                for part in parts:
                    value = self._parse_radix_integer(part)
                    if value is None or value > 255:
                        return None
                    values.append(value)
                packed = 0
                for value in values:
                    packed = (packed << 8) | value
                return ipaddress.IPv4Address(packed)
        return None

    def _parse_radix_integer(self, text):
        if not _INTEGER_IP.fullmatch(text):
            return None
        if text.startswith("0x"):
            if text == "0x":
                return None
            return int(text, 16)
        if len(text) > 1 and text.startswith("0") and all("0" <= ch <= "7" for ch in text):
            return int(text, 8)
        if text.isdigit():
            return int(text, 10)
        return None

    def _is_blocked_ip(self, ip):
        return bool(
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
        )

    def _ensure_ip_allowed(self, ip, rules):
        if self._is_blocked_ip(ip) and not rules.get("allow_private", False):
            raise GuardDenial(REASON_BLOCKED_IP, "address %s is not a public address" % ip)

    def _ensure_suffix_allowed(self, host, rules):
        suffixes = rules.get("suffixes") or []
        if not suffixes:
            return
        for suffix in suffixes:
            normalized = suffix.lower().rstrip(".")
            if host == normalized or host.endswith("." + normalized):
                return
        raise GuardDenial(REASON_SUFFIX, "host %s does not match an allowed suffix" % host)

    def _ensure_dns_public(self, host, rules):
        try:
            addresses = self.resolver(host)
        except Exception as exc:
            raise GuardDenial(REASON_BLOCKED_DNS, "DNS resolution failed for %s" % host) from exc
        for address in addresses or []:
            try:
                ip = ipaddress.ip_address(address)
            except ValueError:
                raise GuardDenial(REASON_BLOCKED_DNS, "resolver returned an unparseable address %s" % address)
            self._ensure_ip_allowed(ip, rules)

    def _ensure_sni_matches(self, headers, host):
        sni = headers.get("sni")
        if not sni:
            raise GuardDenial(REASON_SNI, "SNI header is required")
        try:
            normalized_sni = self._normalize_host(sni)
        except GuardDenial:
            raise GuardDenial(REASON_SNI, "SNI is not a valid host name")
        if normalized_sni != host:
            raise GuardDenial(REASON_SNI, "SNI %s does not match target %s" % (normalized_sni, host))

    def _reap_idle(self, now):
        idle = [
            tunnel_id
            for tunnel_id, tunnel in self._tunnels.items()
            if now - tunnel["last_seen"] > IDLE_TIMEOUT_SECONDS
        ]
        for tunnel_id in idle:
            del self._tunnels[tunnel_id]

    def _active_count(self, client):
        return sum(1 for tunnel in self._tunnels.values() if tunnel["client"] == client)
