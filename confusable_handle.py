import unicodedata


BIDI_CONTROLS = (
    {0x061C, 0x200E, 0x200F}
    | set(range(0x202A, 0x202F))
    | set(range(0x2066, 0x206A))
)

# Single-codepoint lookalike table: Cyrillic / Greek letters mapped to their
# Latin skeleton. Fullwidth letters are covered by NFKC normalization.
CONFUSABLES = {
    # Cyrillic
    "а": "a", "б": "b", "в": "b", "г": "r", "д": "d",
    "е": "e", "ё": "e", "з": "z", "к": "k", "м": "m",
    "н": "n", "о": "o", "р": "p", "с": "c", "т": "t",
    "у": "y", "ф": "f", "х": "x", "э": "e", "і": "i",
    "ї": "i", "є": "e", "ј": "j", "ѕ": "s", "ѓ": "r",
    "ќ": "k", "ў": "y",
    # Greek
    "α": "a", "β": "b", "γ": "y", "δ": "d", "ε": "e",
    "ζ": "z", "η": "n", "ι": "i", "κ": "k", "μ": "u",
    "ν": "v", "ο": "o", "ρ": "p", "σ": "s", "ς": "s",
    "τ": "t", "υ": "u", "φ": "f", "χ": "x", "ω": "w",
}

# Digit / letter confusion: 0~O and 1~l (uppercase I reaches 'i' via casefold).
DIGIT_FOLD = {"0": "o", "1": "l"}

ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_.-")

RESERVED_NAMES = (
    "root", "system", "support", "official",
    "moderator", "help", "info", "null",
)

MIN_LENGTH = 3
MAX_LENGTH = 24


class HandleRegistry:
    def __init__(self):
        self._records = {}
        self._reserved_skeletons = {
            self._to_skeleton(self._canonicalize(name))
            for name in RESERVED_NAMES
        }

    @staticmethod
    def _canonicalize(name):
        if any(ord(ch) in BIDI_CONTROLS for ch in name):
            raise ValueError("bidirectional control characters are not allowed")
        text = unicodedata.normalize("NFKC", name)
        # Turkish capital İ (U+0130) casefolds to 'i' + combining dot above.
        text = text.replace("\u0130", "i")
        text = text.casefold()
        # Strip zero-width and other format characters.
        return "".join(
            ch for ch in text if unicodedata.category(ch) != "Cf"
        )

    @staticmethod
    def _to_skeleton(canonical):
        chars = []
        for ch in canonical:
            ch = CONFUSABLES.get(ch, ch)
            ch = DIGIT_FOLD.get(ch, ch)
            chars.append(ch)
        return "".join(chars)

    def register(self, name, now):
        canonical = self._canonicalize(name)
        skeleton = self._to_skeleton(canonical)
        if not skeleton or any(ch not in ALLOWED_CHARS for ch in skeleton):
            raise ValueError("handle contains invalid characters")
        if not MIN_LENGTH <= len(skeleton) <= MAX_LENGTH:
            raise ValueError(
                "handle must be between 3 and 24 codepoints long"
            )
        if skeleton in self._reserved_skeletons:
            raise ValueError("handle conflicts with a reserved name")
        if skeleton in self._records:
            raise ValueError("handle is already registered")
        record = {
            "handle": canonical,
            "skeleton": skeleton,
            "registered_at": now,
        }
        self._records[skeleton] = record
        return dict(record)

    def resolve(self, name):
        try:
            canonical = self._canonicalize(name)
            skeleton = self._to_skeleton(canonical)
        except ValueError:
            return None
        record = self._records.get(skeleton)
        if record is None:
            return None
        return dict(record)

    def handles(self):
        return {
            "count": len(self._records),
            "reserved": list(RESERVED_NAMES),
        }
