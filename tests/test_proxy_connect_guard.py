import pytest

import proxy_connect_guard as pc


def resolver(host):
    mapping = {
        "example.com": ["93.184.216.34"],
        "api.example.com": ["93.184.216.35"],
        "internal.example.com": ["10.0.0.1"],
        "mixed.example.com": ["93.184.216.36", "10.0.0.1"],
    }
    return mapping.get(host, ["93.184.216.34"])


def policy(**over):
    value = {
        "ports": [443, 8443],
        "allow_private": False,
        "suffixes": ["example.com"],
        "max_per_client": 4,
    }
    value.update(over)
    return value


def guard(**over):
    return pc.ConnectGuard(resolver, policy(**over))


def headers(sni="example.com", client="c1"):
    return {"sni": sni, "x-client": client}


def test_valid_connect_is_authorized():
    result = guard().authorize("CONNECT", "example.com:443", headers())
    assert result["host"] == "example.com"
    assert result["port"] == 443
    assert len(result["tunnel_id"]) == 32


def test_non_connect_method_is_rejected():
    with pytest.raises(ValueError):
        guard().authorize("GET", "example.com:443", headers())


def test_port_must_be_allowlisted():
    with pytest.raises(ValueError):
        guard().authorize("CONNECT", "example.com:25", headers())


def test_userinfo_is_rejected():
    with pytest.raises(ValueError):
        guard().authorize("CONNECT", "user@example.com:443", headers())


def test_crlf_in_target_is_rejected():
    with pytest.raises(ValueError):
        guard().authorize("CONNECT", "example.com:443\r\nX: y", headers())


def test_decimal_loopback_is_rejected():
    with pytest.raises(ValueError):
        guard().authorize("CONNECT", "2130706433:443", headers(sni="2130706433"))


def test_ipv6_loopback_is_rejected():
    with pytest.raises(ValueError):
        guard().authorize("CONNECT", "[::1]:443", headers(sni="::1"))


def test_dns_private_address_is_rejected():
    with pytest.raises(ValueError):
        guard().authorize("CONNECT", "internal.example.com:443", headers(sni="internal.example.com"))


def test_mixed_public_and_private_dns_is_rejected():
    with pytest.raises(ValueError):
        guard().authorize("CONNECT", "mixed.example.com:443", headers(sni="mixed.example.com"))


def test_sni_must_match_target():
    with pytest.raises(ValueError):
        guard().authorize("CONNECT", "example.com:443", headers(sni="other.example.com"))


def test_suffix_must_match_on_label_boundary():
    with pytest.raises(ValueError):
        guard().authorize("CONNECT", "evil-example.com:443", headers(sni="evil-example.com"))


def test_allow_private_policy_permits_private_host():
    result = guard(allow_private=True).authorize(
        "CONNECT", "internal.example.com:443", headers(sni="internal.example.com")
    )
    assert result["host"] == "internal.example.com"


def test_client_tunnel_limit_is_enforced():
    game = guard(max_per_client=1)
    game.authorize("CONNECT", "example.com:443", headers())
    with pytest.raises(ValueError):
        game.authorize("CONNECT", "api.example.com:443", headers(sni="api.example.com"))


def test_release_frees_a_slot():
    game = guard(max_per_client=1)
    first = game.authorize("CONNECT", "example.com:443", headers())
    game.release(first["tunnel_id"], 0)
    second = game.authorize("CONNECT", "api.example.com:443", headers(sni="api.example.com"))
    assert second["host"] == "api.example.com"


def test_tunnels_reports_active_and_rejections():
    game = guard()
    game.authorize("CONNECT", "example.com:443", headers())
    with pytest.raises(ValueError):
        game.authorize("GET", "example.com:443", headers())
    info = game.tunnels()
    assert info["active"] == 1
    assert sum(info["rejected"].values()) == 1
    info["rejected"].clear()
    assert sum(game.tunnels()["rejected"].values()) == 1
