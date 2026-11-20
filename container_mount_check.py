import os
import posixpath
import re
from collections.abc import Mapping


_SPEC_FIELDS = frozenset({"source", "target", "read_only", "propagation", "options"})
_SENSITIVE_PATHS = ("/etc", "/var/lib", "/proc", "/sys", "/dev")
_ALLOWED_PROPAGATION = frozenset({"private", "rprivate"})
_DEFAULT_OPTIONS = ("nosuid", "noexec", "nodev")
_PENALTIES = {
    "host_root": 60,
    "sensitive_path": 50,
    "docker_sock": 60,
    "bad_target": 40,
    "duplicate_target": 30,
    "propagation": 25,
    "read_only_type": 20,
    "read_only_false": 20,
    "missing_option": 10,
}


def _normalize_absolute(path):
    value = os.path.normpath(path)
    if value.startswith("//"):
        value = "/" + value.lstrip("/")
    return value


def _is_below(path, directory):
    return path == directory or path.startswith(directory + "/")


def _container_target(target):
    if not isinstance(target, str) or not target.startswith("/"):
        return None
    value = posixpath.normpath("/" + target.lstrip("/"))
    if value == "/":
        return None
    return value


def _is_docker_socket(source):
    value = _normalize_absolute(source)
    return posixpath.basename(value) == "docker.sock"


def _option_set(options):
    if options is None:
        return set()
    if isinstance(options, str):
        return {item for item in re.split(r"[\s,]+", options) if item}
    try:
        values = list(options)
    except TypeError:
        return set()
    return {item.strip() for item in values if isinstance(item, str) and item.strip()}


def _required_options(policy):
    value = policy.get("require_options", _DEFAULT_OPTIONS)
    if isinstance(value, str):
        value = [value]
    try:
        values = list(value)
    except TypeError:
        values = []

    result = []
    for item in values:
        if isinstance(item, str) and item not in result:
            result.append(item)
    return result


class MountInspector:
    def __init__(self):
        self._mounts = []
        self._policy = None
        self._result = None
        self._dirty = True

    def inspect_spec(self, spec):
        if not isinstance(spec, Mapping):
            raise ValueError("mount spec must be a mapping")

        unknown = set(spec) - _SPEC_FIELDS
        if unknown:
            fields = ", ".join(sorted(str(field) for field in unknown))
            raise ValueError("unknown mount spec field(s): {}".format(fields))

        source = spec.get("source")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("source must be a non-empty string")

        target = spec.get("target", "")
        normalized_source = _normalize_absolute(os.path.realpath(source))
        self._mounts.append({
            "source": source,
            "resolved_source": normalized_source,
            "target": target,
            "normalized_target": _container_target(target),
            "read_only": spec.get("read_only"),
            "propagation": spec.get("propagation"),
            "options": spec.get("options", []),
        })
        self._dirty = True
        return None

    def _problem(self, code, message, mount, severity=None):
        if severity is None:
            severity = "critical" if code == "docker_sock" else "high"
        return {
            "code": code,
            "message": message,
            "severity": severity,
            "source": mount["resolved_source"],
            "target": mount["normalized_target"] or mount["target"],
        }

    def _analyze(self, policy):
        required = _required_options(policy)
        problems = []
        seen_targets = set()

        for mount in self._mounts:
            source = mount["resolved_source"]

            if source == "/":
                problems.append(self._problem(
                    "host_root", "host root must not be mounted into a container", mount
                ))
            elif any(_is_below(source, path) for path in _SENSITIVE_PATHS):
                problems.append(self._problem(
                    "sensitive_path",
                    "sensitive host path must not be mounted into a container",
                    mount,
                ))

            if _is_docker_socket(source):
                problems.append(self._problem(
                    "docker_sock",
                    "docker socket mount grants control of the host daemon",
                    mount,
                    severity="critical",
                ))

            target = mount["normalized_target"]
            if target is None:
                problems.append(self._problem(
                    "bad_target", "target must be an absolute container path", mount
                ))
            elif target in seen_targets:
                problems.append(self._problem(
                    "duplicate_target", "target is mounted more than once", mount
                ))
            else:
                seen_targets.add(target)

            if mount["propagation"] not in _ALLOWED_PROPAGATION:
                problems.append(self._problem(
                    "propagation",
                    "propagation must be private or rprivate",
                    mount,
                ))

            read_only = mount["read_only"]
            if not isinstance(read_only, bool):
                problems.append(self._problem(
                    "read_only_type", "read_only must be a boolean", mount
                ))
            elif read_only is not True:
                problems.append(self._problem(
                    "read_only_false", "mount must be read-only", mount
                ))

            provided = _option_set(mount["options"])
            for option in required:
                if option not in provided:
                    problem = self._problem(
                        "missing_option",
                        "required mount option is missing: {}".format(option),
                        mount,
                    )
                    problem["option"] = option
                    problems.append(problem)

        score = 100
        for problem in problems:
            score -= _PENALTIES.get(problem["code"], 10)
        score = max(0, score)
        if any(problem["code"] == "docker_sock" for problem in problems):
            score = min(score, 50)

        return {"problems": problems, "score": score}

    def evaluate(self, policy=None):
        if policy is None:
            policy = {}
        if not isinstance(policy, Mapping):
            raise ValueError("policy must be a mapping")

        self._policy = dict(policy)
        self._result = self._analyze(self._policy)
        self._dirty = False
        return {
            "problems": [dict(problem) for problem in self._result["problems"]],
            "score": self._result["score"],
        }

    def _current_result(self):
        if self._result is None or self._dirty:
            policy = self._policy if self._policy is not None else {}
            return self._analyze(policy)
        return self._result

    def snapshot(self):
        result = self._current_result()
        critical = sum(
            1 for mount in self._mounts
            if _is_docker_socket(mount["resolved_source"])
        )
        return {
            "mounts": len(self._mounts),
            "critical": critical,
            "score": result["score"],
        }
