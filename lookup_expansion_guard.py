import re
from urllib.parse import unquote


_MARKER_RE = re.compile(r"\\?\$")
_PROTOCOLS = ("jndi", "ldap", "rmi", "dns", "http", "file")
_DEFAULT_PREFIXES = ("app.", "env.", "ctx.")
_MAX_DEPTH = 5
_MAX_OUTPUT_LENGTH = 4096


def _normalize_name(name):
    current = name
    previous = None
    while previous != current:
        previous = current
        current = unquote(current)
    return current.lower()


def _has_control_character(value):
    return any(ord(char) < 0x20 or char == "\x7f" for char in value)


class LookupShield:
    def __init__(self):
        self._renders = 0
        self._denied = 0

    def render(self, template, context, policy):
        if not isinstance(template, str):
            self._denied += 1
            raise ValueError("template must be a string")
        prefixes = tuple((policy or {}).get("prefixes", _DEFAULT_PREFIXES))
        try:
            rendered = self._render(template, context or {}, prefixes, 0, frozenset())
            if _has_control_character(rendered):
                raise ValueError("control characters are not allowed in rendered output")
            if len(rendered) > _MAX_OUTPUT_LENGTH:
                raise ValueError(
                    "rendered output exceeds %d characters" % _MAX_OUTPUT_LENGTH
                )
        except ValueError:
            self._denied += 1
            raise
        self._renders += 1
        return rendered

    def _classify_after_marker(self, text, marker_end):
        second = _MARKER_RE.match(text, marker_end)
        if (
            second
            and second.end() < len(text)
            and text[second.end()] == "{"
        ):
            return "escape", second.end() + 1
        if marker_end < len(text) and text[marker_end] == "{":
            return "lookup", marker_end
        return "literal", marker_end

    def _find_closing_brace(self, text, open_brace_index):
        depth = 1
        index = open_brace_index + 1
        while index < len(text):
            marker = _MARKER_RE.match(text, index)
            if marker and marker.end() < len(text) and text[marker.end()] == "{":
                kind, next_index = self._classify_after_marker(text, marker.end())
                if kind == "escape":
                    index = next_index
                    continue
                depth += 1
                index = next_index + 1
                continue
            if marker:
                index = marker.end()
                continue
            char = text[index]
            if char == "}":
                depth -= 1
                if depth == 0:
                    return index
            elif char == "{":
                depth += 1
            index += 1
        return -1

    def _render(self, text, context, prefixes, depth, active_names):
        parts = []
        index = 0
        length = len(text)
        while index < length:
            marker = _MARKER_RE.search(text, index)
            if marker is None:
                parts.append(text[index:])
                break
            start, end = marker.span()
            parts.append(text[index:start])
            kind, next_index = self._classify_after_marker(text, end)
            if kind == "literal":
                parts.append(text[start:end])
                index = next_index
                continue
            if kind == "escape":
                parts.append(text[start:end])
                parts.append("{")
                index = next_index
                continue
            close = self._find_closing_brace(text, end)
            if close == -1:
                raise ValueError("unmatched '{' in template")
            body = text[end + 1:close]
            raw_lookup = text[start:close + 1]
            parts.append(
                self._render_lookup(
                    body, context, prefixes, depth, active_names, raw_lookup
                )
            )
            index = close + 1
        return "".join(parts)

    def _render_lookup(self, body, context, prefixes, depth, active_names, raw_lookup):
        if depth >= _MAX_DEPTH:
            raise ValueError("nested lookup depth exceeds %d" % _MAX_DEPTH)
        if ":-" in body:
            name, default_body = body.split(":-", 1)
        else:
            name, default_body = body, None
        if name == "":
            raise ValueError("empty lookup name")
        if name in active_names:
            raise ValueError("cyclic reference detected for key: %s" % name)
        normalized = _normalize_name(name)
        if any(protocol in normalized for protocol in _PROTOCOLS):
            raise ValueError("forbidden protocol referenced in lookup: %s" % name)
        if not any(name.startswith(prefix) for prefix in prefixes):
            raise ValueError("lookup name uses disallowed prefix: %s" % name)
        if name in context:
            value = context[name]
            if not isinstance(value, str):
                value = str(value)
            if _has_control_character(value):
                raise ValueError(
                    "control characters are not allowed in value: %s" % name
                )
            return value
        if default_body is not None:
            return self._render(
                default_body,
                context,
                prefixes,
                depth + 1,
                active_names | frozenset((name,)),
            )
        return raw_lookup

    def scan(self, value):
        if not isinstance(value, str):
            return []
        matches = []
        consumed_markers = set()
        for marker in _MARKER_RE.finditer(value):
            start, end = marker.span()
            if start in consumed_markers:
                continue
            second = _MARKER_RE.match(value, end)
            if (
                second
                and second.end() < len(value)
                and value[second.end()] == "{"
            ):
                consumed_markers.add(end)
                continue
            if end >= len(value) or value[end] != "{":
                continue
            close = self._find_closing_brace(value, end)
            balanced = close != -1
            if balanced:
                raw = value[start:close + 1]
                body = value[end + 1:close]
                match_end = close + 1
            else:
                raw = value[start:]
                body = value[end + 1:]
                match_end = len(value)
            name = body.split(":-", 1)[0]
            normalized = _normalize_name(name) if name else ""
            blocked = (
                name == ""
                or any(protocol in normalized for protocol in _PROTOCOLS)
                or not any(name.startswith(prefix) for prefix in _DEFAULT_PREFIXES)
            )
            matches.append(
                {
                    "start": start,
                    "end": match_end,
                    "raw": raw,
                    "name": name,
                    "balanced": balanced,
                    "blocked": blocked,
                }
            )
        return matches

    def dump(self):
        return {"renders": self._renders, "denied": self._denied}
