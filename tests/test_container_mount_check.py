import pytest

import container_mount_check as cm


def spec(source="/data", target="/app/data", read_only=True, propagation="rprivate",
         options=("nosuid", "noexec", "nodev")):
    return {
        "source": source,
        "target": target,
        "read_only": read_only,
        "propagation": propagation,
        "options": list(options),
    }


def policy(**over):
    value = {"require_options": ["nosuid", "noexec", "nodev"]}
    value.update(over)
    return value


def checked(*specs, pol=None):
    game = cm.MountInspector()
    for item in specs:
        game.inspect_spec(item)
    return game.evaluate(pol or policy())


def codes(result):
    return [x["code"] for x in result["problems"]]


def test_safe_mount_scores_full():
    result = checked(spec())
    assert result["score"] == 100
    assert result["problems"] == []


def test_host_root_is_rejected():
    assert "host_root" in codes(checked(spec(source="/")))


def test_sensitive_host_path_is_rejected():
    assert "sensitive_path" in codes(checked(spec(source="/etc")))
    assert "sensitive_path" in codes(checked(spec(source="/proc")))


def test_duplicate_target_is_reported():
    result = checked(spec(target="/app/data"), spec(target="/app/data"))
    assert "duplicate_target" in codes(result)


def test_rshared_propagation_is_reported():
    assert "propagation" in codes(checked(spec(propagation="rshared")))


def test_read_only_must_be_boolean():
    assert "read_only_type" in codes(checked(spec(read_only="true")))


def test_missing_option_is_reported():
    assert "missing_option" in codes(checked(spec(options=("nosuid", "noexec"))))


def test_docker_socket_is_critical():
    result = checked(spec(source="/var/run/docker.sock", target="/sock"))
    assert "docker_sock" in codes(result)
    assert result["score"] <= 50


def test_target_must_be_container_absolute():
    assert "bad_target" in codes(checked(spec(target="relative/path")))


def test_unknown_field_is_rejected():
    bad = spec()
    bad["privileged"] = True
    with pytest.raises(ValueError):
        cm.MountInspector().inspect_spec(bad)


def test_empty_source_is_rejected():
    with pytest.raises(ValueError):
        cm.MountInspector().inspect_spec(spec(source=""))


def test_symlink_like_parent_escape_is_rejected():
    assert "sensitive_path" in codes(checked(spec(source="/data/../etc/shadow")))


def test_multiple_problems_accumulate():
    result = checked(spec(source="/", options=("nosuid",)))
    assert "host_root" in codes(result)
    assert "missing_option" in codes(result)


def test_snapshot_counts_mounts_and_critical():
    game = cm.MountInspector()
    game.inspect_spec(spec())
    game.inspect_spec(spec(source="/var/run/docker.sock", target="/sock"))
    info = game.snapshot()
    assert info["mounts"] == 2
    assert info["critical"] == 1


def test_snapshot_is_copy():
    game = cm.MountInspector()
    game.inspect_spec(spec())
    game.evaluate(policy())
    snap = game.snapshot()
    snap["score"] = 999
    assert game.snapshot()["score"] != 999
