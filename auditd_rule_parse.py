class RuleBook:
    def __init__(self):
        pass

    def load(self, text):
        return None

    def match(self, event):
        return []

    def snapshot(self):
        return {}
import re


ALLOWED_ARCHES = {"b64", "b32"}
ALLOWED_PERMS = set("rwxa")
TAG_RE = re.compile(r"^[A-Za-z0-9_]+$")

KNOWN_SYSCALLS = {
    "read", "write", "open", "openat", "openat2", "close", "stat", "fstat",
    "lstat", "newfstatat", "poll", "ppoll", "lseek", "mmap", "mprotect",
    "munmap", "brk", "rt_sigaction", "rt_sigprocmask", "rt_sigreturn",
    "ioctl", "pread64", "pwrite64", "readv", "writev", "access", "faccessat",
    "pipe", "pipe2", "select", "pselect6", "sched_yield", "mremap", "msync",
    "mincore", "madvise", "dup", "dup2", "dup3", "nanosleep", "getitimer",
    "setitimer", "alarm", "getpid", "sendfile", "socket", "connect",
    "accept", "accept4", "sendto", "recvfrom", "sendmsg", "recvmsg",
    "recvmmsg", "sendmmsg", "shutdown", "bind", "listen", "getsockname",
    "getpeername", "socketpair", "setsockopt", "getsockopt", "clone",
    "clone3", "fork", "vfork", "execve", "execveat", "exit", "exit_group",
    "wait4", "waitid", "kill", "tgkill", "uname", "fcntl", "flock", "fsync",
    "fdatasync", "sync", "syncfs", "truncate", "ftruncate", "getdents",
    "getdents64", "getcwd", "chdir", "fchdir", "rename", "renameat",
    "renameat2", "mkdir", "mkdirat", "rmdir", "creat", "link", "linkat",
    "unlink", "unlinkat", "symlink", "symlinkat", "readlink", "readlinkat",
    "chmod", "fchmod", "fchmodat", "chown", "fchown", "lchown", "fchownat",
    "umask", "gettimeofday", "clock_gettime", "clock_settime",
    "clock_getres", "clock_nanosleep", "getrlimit", "prlimit64",
    "setrlimit", "getrusage", "sysinfo", "times", "ptrace", "getuid",
    "getgid", "setuid", "setgid", "geteuid", "getegid", "setpgid",
    "getppid", "getpgrp", "setsid", "setreuid", "setregid", "getgroups",
    "setgroups", "setresuid", "getresuid", "setresgid", "getresgid",
    "getpgid", "setfsuid", "setfsgid", "getsid", "capget", "capset",
    "sigaltstack", "utime", "utimensat", "mknod", "mknodat", "statfs",
    "fstatfs", "statx", "getpriority", "setpriority", "mlock", "munlock",
    "mlockall", "munlockall", "pivot_root", "prctl", "arch_prctl",
    "chroot", "mount", "umount2", "swapon", "swapoff", "reboot",
    "sethostname", "setdomainname", "ioperm", "init_module",
    "finit_module", "delete_module", "quotactl", "epoll_create",
    "epoll_create1", "epoll_ctl", "epoll_wait", "epoll_pwait",
    "set_tid_address", "restart_syscall", "fadvise64", "timer_create",
    "timer_settime", "timer_gettime", "timer_getoverrun", "timer_delete",
    "inotify_init", "inotify_init1", "inotify_add_watch",
    "inotify_rm_watch", "mkdirat", "ioprio_set", "ioprio_get", "futex",
    "sched_setaffinity", "sched_getaffinity", "io_setup", "io_destroy",
    "io_getevents", "io_submit", "io_cancel", "unshare", "setns",
    "set_robust_list", "get_robust_list", "splice", "tee",
    "sync_file_range", "vmsplice", "move_pages", "mbind",
    "set_mempolicy", "get_mempolicy", "mq_open", "mq_unlink",
    "mq_timedsend", "mq_timedreceive", "mq_notify", "mq_getsetattr",
    "kexec_load", "add_key", "request_key", "keyctl", "signalfd",
    "signalfd4", "timerfd_create", "timerfd_settime", "timerfd_gettime",
    "eventfd", "eventfd2", "fallocate", "fanotify_init", "fanotify_mark",
    "name_to_handle_at", "open_by_handle_at", "getcpu",
    "process_vm_readv", "process_vm_writev", "memfd_create", "copy_file_range",
    "userfaultfd", "seccomp", "bpf", "pidfd_open", "clone3", "open_tree",
    "move_mount", "fsconfig", "fsmount", "fsopen", "fspick",
}

_TOKEN_RE = re.compile(r'"([^"]*)"|\'([^\']*)\'|(\S+)')


def _strip_comment(line):
    quote = None
    for index, char in enumerate(line):
        if quote is not None:
            if char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif char == "#":
            return line[:index]
    return line


def _tokenize(line):
    tokens = []
    for match in _TOKEN_RE.finditer(line):
        double_quoted, single_quoted, bare = match.groups()
        if double_quoted is not None:
            tokens.append(double_quoted)
        elif single_quoted is not None:
            tokens.append(single_quoted)
        else:
            tokens.append(bare)
    return tokens


class RuleBook:
    def __init__(self):
        self._reset()

    def _reset(self):
        self.rules = []
        self.exclusions = []
        self.duplicates = 0
        self.unknown_syscalls = 0
        self._signatures = set()
        self._exclusion_signatures = set()

    def load(self, text):
        self._reset()
        joined = re.sub(r"\\\r?\n", " ", text)
        saw_syscall = False
        for raw_line in joined.splitlines():
            line = _strip_comment(raw_line).strip()
            if not line:
                continue
            tokens = _tokenize(line)
            if not tokens:
                continue

            is_exclusion = False
            if tokens[0] == "--":
                is_exclusion = True
                tokens = tokens[1:]
                if not tokens:
                    raise ValueError("exclusion marker without a rule")

            rule, is_syscall, unknown_count = self._parse_rule(tokens)
            if unknown_count:
                self.unknown_syscalls += unknown_count
                continue

            if is_syscall:
                saw_syscall = True
            elif saw_syscall:
                raise ValueError(
                    "watch rule must be declared before exit/syscall rules: %s"
                    % " ".join(tokens)
                )

            signature = self._signature(rule)
            if is_exclusion:
                if signature in self._exclusion_signatures:
                    self.duplicates += 1
                    continue
                self._exclusion_signatures.add(signature)
                self.exclusions.append(rule)
            else:
                if signature in self._signatures:
                    self.duplicates += 1
                    continue
                self._signatures.add(signature)
                self.rules.append(rule)

    def _parse_rule(self, tokens):
        head = tokens[0]
        if head == "-w":
            return self._parse_watch(tokens), False, 0
        if head == "-a":
            return self._parse_syscall(tokens)
        raise ValueError("unknown rule type: %s" % head)

    def _read_flag(self, tokens, index):
        if index + 1 >= len(tokens):
            raise ValueError("missing value for flag %s" % tokens[index])
        return tokens[index + 1], index + 2

    def _validate_key(self, key):
        if not key or not TAG_RE.match(key):
            raise ValueError("invalid key tag %r: only letters, digits and _ allowed" % key)

    def _parse_watch(self, tokens):
        if len(tokens) < 2:
            raise ValueError("watch rule requires a path")
        path = tokens[1]
        perms = None
        key = None
        index = 2
        while index < len(tokens):
            flag = tokens[index]
            if flag == "-p":
                perms, index = self._read_flag(tokens, index)
            elif flag == "-k":
                key, index = self._read_flag(tokens, index)
            else:
                raise ValueError("unexpected token in watch rule: %s" % flag)

        if not path:
            raise ValueError("watch rule requires a path")
        if not perms or any(char not in ALLOWED_PERMS for char in perms):
            raise ValueError("invalid permission %r: only a combination of r, w, x, a is allowed" % perms)
        self._validate_key(key)
        return {"type": "watch", "path": path, "perms": perms, "key": key}

    def _parse_syscall(self, tokens):
        if len(tokens) < 2 or tokens[1].startswith("-"):
            raise ValueError("syscall rule requires an action list after -a")
        arch = None
        key = None
        syscalls = []
        index = 2
        while index < len(tokens):
            flag = tokens[index]
            if flag == "-F":
                field, index = self._read_flag(tokens, index)
                name, sep, value = field.partition("=")
                if not sep:
                    raise ValueError("invalid -F field: %s" % field)
                if name == "arch":
                    if value not in ALLOWED_ARCHES:
                        raise ValueError("invalid arch %r: only b64 and b32 are allowed" % value)
                    arch = value
            elif flag == "-S":
                name, index = self._read_flag(tokens, index)
                syscalls.append(name)
            elif flag == "-k":
                key, index = self._read_flag(tokens, index)
            else:
                raise ValueError("unexpected token in syscall rule: %s" % flag)

        if arch is None:
            raise ValueError("syscall rule requires -F arch=b64|b32")
        if not syscalls:
            raise ValueError("syscall rule requires at least one -S entry")
        self._validate_key(key)

        unknown = [name for name in syscalls if name not in KNOWN_SYSCALLS]
        if unknown:
            return None, True, len(unknown)
        return {
            "type": "syscall",
            "arch": arch,
            "syscalls": tuple(syscalls),
            "key": key,
        }, True, 0

    def _signature(self, rule):
        if rule["type"] == "watch":
            return ("watch", rule["path"], rule["perms"], rule["key"])
        return ("syscall", rule["arch"], tuple(sorted(rule["syscalls"])), rule["key"])

    def _matches(self, rule, event):
        if rule["type"] == "watch":
            path = event.get("path")
            watched = rule["path"]
            if path is None:
                return False
            path_matches = path == watched or path.startswith(watched + "/")
            return path_matches and event.get("perm") in rule["perms"]
        return (
            event.get("arch") == rule["arch"]
            and event.get("syscall") in rule["syscalls"]
        )

    def match(self, event):
        for rule in self.exclusions:
            if self._matches(rule, event):
                return []
        keys = []
        for rule in self.rules:
            if self._matches(rule, event):
                keys.append(rule["key"])
        return keys

    def snapshot(self):
        return {
            "rules": len(self.rules),
            "duplicates": self.duplicates,
            "unknown_syscalls": self.unknown_syscalls,
        }
