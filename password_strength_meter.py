import hashlib
import math
import re
import string
import unicodedata
from collections import deque


COMMON_WORDS = (
    "password", "passw0rd", "qwerty", "azerty", "letmein", "welcome",
    "monkey", "dragon", "master", "shadow", "superman", "football",
    "baseball", "sunshine", "princess", "admin", "login", "hello",
    "secret", "ninja", "iloveyou", "trustno1", "starwars", "computer",
    "michelle", "charlie", "robert", "thomas", "jordan", "hunter",
    "ranger", "summer", "winter", "spring", "autumn", "orange",
)

LEET_MAP = {
    "@": "a", "4": "a", "8": "b", "3": "e", "1": "i", "0": "o",
    "$": "s", "5": "s", "7": "t", "9": "g", "2": "z",
}

KEYBOARD_ROWS_QWERTY = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
KEYBOARD_ROWS_AZERTY = ("azertyuiop", "qsdfghjklm", "wxcvbn")
ALPHABETS = ("abcdefghijklmnopqrstuvwxyz", "0123456789") + (
    KEYBOARD_ROWS_QWERTY + KEYBOARD_ROWS_AZERTY
)

YEAR_RE = re.compile(r"(?:19|20)\d{2}")
TOKEN_RE = re.compile(r"[a-z0-9]+")

FEEDBACK_ORDER = (
    "BREACHED_PASSWORD",
    "TOO_SHORT",
    "REPEATED_CHARACTERS",
    "SEQUENCE_DETECTED",
    "COMMON_WORD",
    "LEET_SUBSTITUTION",
    "YEAR_PRESENT",
    "USER_INPUT",
    "LOW_ENTROPY",
)

SCORE_THRESHOLDS = (20, 36, 60, 80)
RECENT_SCORE_LIMIT = 10


class StrengthMeter:
    def __init__(self):
        self._evaluations = 0
        self._rejections = 0
        self._recent_scores = deque(maxlen=RECENT_SCORE_LIMIT)

    def _normalize(self, password, count_rejection):
        if not isinstance(password, str):
            if count_rejection:
                self._rejections += 1
            raise ValueError("password must be a non-empty string")
        normalized = unicodedata.normalize("NFKC", password)
        if normalized == "" or normalized.strip() == "":
            if count_rejection:
                self._rejections += 1
            raise ValueError("password must not be empty or whitespace only")
        return normalized

    @staticmethod
    def _decode_leet(text):
        return "".join(LEET_MAP.get(char, char) for char in text)

    @staticmethod
    def _pool_size(text):
        pool = 0
        if any(char in string.ascii_lowercase for char in text):
            pool += 26
        if any(char in string.ascii_uppercase for char in text):
            pool += 26
        if any(char in string.digits for char in text):
            pool += 10
        if any(char in string.punctuation for char in text):
            pool += len(string.punctuation)
        if any(
            char not in (
                string.ascii_letters + string.digits + string.punctuation
            )
            and not char.isspace()
            for char in text
        ):
            pool += 100
        if any(char.isspace() for char in text):
            pool += 1
        return max(pool, 1)

    @staticmethod
    def _sequence_run_length(text, start, alphabet):
        if text[start:start + 3] in alphabet:
            step = 1
        elif text[start:start + 3] in alphabet[::-1]:
            step = -1
        else:
            return 0
        end = start + 3
        while end < len(text):
            current = alphabet.find(text[end - 1])
            following = alphabet.find(text[end])
            if following == -1 or following - current != step:
                break
            end += 1
        return end - start

    def _analyze(self, normalized, user_inputs):
        text = normalized.lower()
        decoded = self._decode_leet(text)
        length = len(normalized)

        entropy = length * math.log2(self._pool_size(normalized))
        findings = {
            "too_short": length < 8,
            "repeated": False,
            "sequence": False,
            "common_word": False,
            "leet": False,
            "year": False,
            "user_input": False,
        }

        for match in re.finditer(r"(.)\1{2,}", text):
            entropy -= (len(match.group()) - 1) * 4
            findings["repeated"] = True

        index = 0
        while index < length - 2:
            for alphabet in ALPHABETS:
                run_length = self._sequence_run_length(text, index, alphabet)
                if run_length >= 3:
                    entropy -= (run_length - 1) * 3
                    findings["sequence"] = True
                    index += run_length
                    break
            else:
                index += 1

        for word in COMMON_WORDS:
            in_plain = word in text
            in_decoded = word in decoded
            if in_plain or in_decoded:
                entropy -= len(word) * 3
                findings["common_word"] = True
                if in_decoded and not in_plain:
                    findings["leet"] = True

        years = set(YEAR_RE.findall(text)) | set(YEAR_RE.findall(decoded))
        if years:
            entropy -= 6 * len(years)
            findings["year"] = True

        tokens = set()
        for item in user_inputs or ():
            if not isinstance(item, str):
                continue
            for token in TOKEN_RE.findall(item.lower()):
                if len(token) >= 3 and (token in text or token in decoded):
                    tokens.add(token)
        if tokens:
            entropy -= 10 * len(tokens)
            findings["user_input"] = True

        if findings["leet"]:
            entropy -= 6

        return max(entropy, 0.0), findings

    @staticmethod
    def _band(entropy):
        score = 0
        for threshold in SCORE_THRESHOLDS:
            if entropy >= threshold:
                score += 1
        return score

    def _is_breached(self, normalized, breach_hashes):
        if not breach_hashes:
            return False
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return digest in {str(item).lower() for item in breach_hashes}

    def score(self, password, user_inputs=None, breach_hashes=None):
        normalized = self._normalize(password, count_rejection=True)
        self._evaluations += 1
        if self._is_breached(normalized, breach_hashes):
            self._recent_scores.append(0)
            return 0
        entropy, _ = self._analyze(normalized, user_inputs)
        result = self._band(entropy)
        self._recent_scores.append(result)
        return result

    def feedback(self, password, user_inputs=None, breach_hashes=None):
        normalized = self._normalize(password, count_rejection=False)
        entropy, findings = self._analyze(normalized, user_inputs)
        active = {
            "BREACHED_PASSWORD": self._is_breached(normalized, breach_hashes),
            "TOO_SHORT": findings["too_short"],
            "REPEATED_CHARACTERS": findings["repeated"],
            "SEQUENCE_DETECTED": findings["sequence"],
            "COMMON_WORD": findings["common_word"],
            "LEET_SUBSTITUTION": findings["leet"],
            "YEAR_PRESENT": findings["year"],
            "USER_INPUT": findings["user_input"],
            "LOW_ENTROPY": self._band(entropy) < 2,
        }
        return [code for code in FEEDBACK_ORDER if active[code]][:5]

    def check_rotation(self, old, new):
        old_normalized = self._normalize(old, count_rejection=True)
        new_normalized = self._normalize(new, count_rejection=True)
        position_diffs = abs(len(old_normalized) - len(new_normalized))
        for old_char, new_char in zip(old_normalized, new_normalized):
            if old_char != new_char:
                position_diffs += 1
        if position_diffs < 4 or old_normalized in new_normalized:
            self._rejections += 1
            raise ValueError("new password is too similar to the old one")
        return True

    def report(self):
        return {
            "evaluations": self._evaluations,
            "rejections": self._rejections,
            "recent_scores": list(self._recent_scores),
        }
