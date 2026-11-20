import unicodedata


CHANNELS = ("say", "party", "guild", "whisper", "system")
PLAYER_CHANNELS = ("say", "party", "guild", "whisper")

DEFAULT_BLOCKED_WORDS = ("badword",)

MAX_MESSAGE_LEN = 500
RATE_WINDOW_SECONDS = 10
RATE_LIMIT_DEFAULT = 5
RATE_LIMIT_WHISPER = 3
REPORT_COOLDOWN_SECONDS = 60


def normalize_text(text):
    return unicodedata.normalize("NFKC", text).lower()


def is_separator(char):
    category = unicodedata.category(char)
    return char.isspace() or category.startswith("P") or category.startswith("S")


class Trie:
    def __init__(self, words):
        self.root = {}
        self.terminal = object()
        for word in words:
            node = self.root
            for char in normalize_text(word):
                node = node.setdefault(char, {})
            node[self.terminal] = None

    def contains(self, text):
        normalized = normalize_text(text)
        for start in range(len(normalized)):
            node = self.root
            index = start
            while index < len(normalized):
                char = normalized[index]
                if char in node:
                    node = node[char]
                    index += 1
                    if self.terminal in node:
                        return True
                elif is_separator(char):
                    index += 1
                else:
                    break
        return False


class ChatGate:
    def __init__(self, blocked_words=DEFAULT_BLOCKED_WORDS):
        self._members = {}
        self._gms = set()
        self._mutes = {}
        self._message_times = {}
        self._report_times = {}
        self._trie = Trie(blocked_words)
        self._audit = []
        self._stats = {"sent": 0, "rejected": 0, "muted": 0}

    def join(self, player, guild=None, party=None):
        self._members[player] = {"guild": guild, "party": party}
        self._message_times.setdefault(player, [])

    def set_gm(self, player, flag):
        if flag:
            self._gms.add(player)
        else:
            self._gms.discard(player)

    def _member(self, player):
        if player not in self._members:
            raise ValueError(f"unknown player: {player}")
        return self._members[player]

    def _is_muted(self, player, at):
        until = self._mutes.get(player)
        return until is not None and at < until

    def _check_rate_limit(self, player, channel, at):
        window_start = at - RATE_WINDOW_SECONDS
        times = [item for item in self._message_times[player] if item[1] > window_start]
        whisper_count = sum(1 for item in times if item[0] == "whisper")
        if channel == "whisper":
            if whisper_count >= RATE_LIMIT_WHISPER:
                raise ValueError("whisper rate limit exceeded")
        elif len(times) >= RATE_LIMIT_DEFAULT:
            raise ValueError("message rate limit exceeded")
        times.append((channel, at))
        self._message_times[player] = times

    def send(self, player, channel, text, at):
        if channel not in CHANNELS:
            raise ValueError(f"unknown channel: {channel}")
        if not isinstance(text, str) or len(text) > MAX_MESSAGE_LEN:
            raise ValueError("message too long")

        member = self._member(player)
        normalized = normalize_text(text)
        if not normalized.strip():
            raise ValueError("empty message")

        if channel == "guild" and not member["guild"]:
            raise ValueError("guild channel requires guild membership")
        if channel == "party" and not member["party"]:
            raise ValueError("party channel requires party membership")

        if channel != "system" and self._is_muted(player, at):
            raise ValueError(f"player is muted until {self._mutes[player]}")

        if channel in PLAYER_CHANNELS:
            self._check_rate_limit(player, channel, at)

        filtered = channel != "system" and player not in self._gms
        if filtered and self._trie.contains(normalized):
            self._stats["rejected"] += 1
            self._audit.append(
                {"event": "rejected", "player": player, "channel": channel, "at": at}
            )
            return {"sent": False, "reason": "blocked_word"}

        self._stats["sent"] += 1
        self._audit.append(
            {"event": "sent", "player": player, "channel": channel, "at": at}
        )
        return {"sent": True}

    def mute(self, player, until, reason):
        self._member(player)
        self._mutes[player] = until
        self._stats["muted"] += 1
        self._audit.append(
            {"event": "mute", "player": player, "until": until, "reason": reason}
        )

    def report(self, player, target, at):
        self._member(player)
        self._member(target)
        key = (player, target)
        last_at = self._report_times.get(key)
        if last_at is not None and at - last_at < REPORT_COOLDOWN_SECONDS:
            raise ValueError("report cooldown not elapsed")
        self._report_times[key] = at
        self._audit.append(
            {"event": "report", "player": player, "target": target, "at": at}
        )

    def gate_report(self):
        return dict(self._stats)
