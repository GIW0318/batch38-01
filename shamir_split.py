import random
import zlib

_POLY = 0x11B
_MAX_SHARES = 255
_MIN_SECRET_LEN = 1
_MAX_SECRET_LEN = 64
_CHECKSUM_LEN = 4

_EXP = [0] * 512
_LOG = [0] * 256


def _init_tables():
    x = 1
    for i in range(255):
        _EXP[i] = x
        _LOG[x] = i
        x = (x << 1) ^ x
        if x & 0x100:
            x ^= _POLY
    for i in range(255, 512):
        _EXP[i] = _EXP[i - 255]


_init_tables()


def _mul(a, b):
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _div(a, b):
    if b == 0:
        raise ZeroDivisionError("division by zero in GF(256)")
    if a == 0:
        return 0
    return _EXP[(_LOG[a] - _LOG[b]) % 255]


def _checksum(payload):
    return "%04x" % (zlib.crc32(payload.encode("ascii")) & 0xFFFF)


class SecretSharer:
    def __init__(self):
        self._threshold = None
        self._shares = None
        self._issued_x = []

    def split(self, secret, threshold, shares, seed):
        if not isinstance(secret, str):
            raise ValueError("secret must be a string")
        data = secret.encode("utf-8")
        if not (_MIN_SECRET_LEN <= len(data) <= _MAX_SECRET_LEN):
            raise ValueError("secret length out of range")
        if not isinstance(threshold, int) or threshold < 2:
            raise ValueError("threshold must be at least 2")
        if not isinstance(shares, int) or shares < 1 or shares > _MAX_SHARES:
            raise ValueError("shares must be between 1 and 255")
        if threshold > shares:
            raise ValueError("threshold must not exceed shares")

        rng = random.Random(seed)
        ys_list = [bytearray() for _ in range(shares)]
        for byte in data:
            coeffs = [byte] + [rng.randrange(256) for _ in range(threshold - 1)]
            for idx in range(shares):
                x = idx + 1
                y = 0
                power = 1
                for coeff in coeffs:
                    y ^= _mul(coeff, power)
                    power = _mul(power, x)
                ys_list[idx].append(y)
        parts = []
        for idx in range(shares):
            ys = ys_list[idx]
            payload = ys.hex()
            parts.append("%d.%s%s" % (idx + 1, payload, _checksum(payload)))

        self._threshold = threshold
        self._shares = shares
        self._issued_x = list(range(1, shares + 1))
        return parts

    def _parse(self, share):
        if not isinstance(share, str):
            raise ValueError("share must be a string")
        pieces = share.split(".")
        if len(pieces) != 2 or not pieces[0] or not pieces[1]:
            raise ValueError("share format must be x.y")
        try:
            x = int(pieces[0], 10)
        except ValueError:
            raise ValueError("share x coordinate is not an integer")
        if x < 1 or x > _MAX_SHARES:
            raise ValueError("share x coordinate out of range")
        body = pieces[1]
        if len(body) <= _CHECKSUM_LEN or len(body) % 2 != 0:
            raise ValueError("share payload has invalid length")
        payload, given = body[:-_CHECKSUM_LEN], body[-_CHECKSUM_LEN:]
        if given.lower() != _checksum(payload.lower()):
            raise ValueError("share checksum mismatch")
        try:
            data = bytes.fromhex(payload)
        except ValueError:
            raise ValueError("share payload is not valid hex")
        if not data:
            raise ValueError("share payload is empty")
        return x, data

    def combine(self, shares):
        if self._threshold is None:
            raise ValueError("no split has been performed")
        if not shares:
            raise ValueError("no shares provided")
        points = []
        seen_x = set()
        length = None
        for share in shares:
            x, data = self._parse(share)
            if x in seen_x:
                raise ValueError("duplicate share x coordinate")
            seen_x.add(x)
            if length is None:
                length = len(data)
            elif len(data) != length:
                raise ValueError("inconsistent share lengths")
            points.append((x, data))
        if len(points) < self._threshold:
            raise ValueError("fewer shares than threshold")

        secret = bytearray()
        for i in range(length):
            acc = 0
            for j, (xj, yj) in enumerate(points):
                num = 1
                den = 1
                for k, (xk, _) in enumerate(points):
                    if k == j:
                        continue
                    num = _mul(num, xk)
                    den = _mul(den, xj ^ xk)
                acc ^= _mul(yj[i], _div(num, den))
            secret.append(acc)
        return secret.decode("utf-8")

    def verify(self, share):
        try:
            self._parse(share)
        except (ValueError, TypeError):
            return False
        return True

    def dump(self):
        return {
            "threshold": self._threshold,
            "shares": self._shares,
            "issued_x": list(self._issued_x),
        }
