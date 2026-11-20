import pytest

import lookup_expansion_guard as lg


def shield():
    return lg.LookupShield()


def policy():
    return {"prefixes": ["app.", "env.", "ctx."]}


def render(template, context=None):
    return shield().render(template, context or {}, policy())


def test_simple_lookup_is_replaced():
    assert render("\${app.name}", {"app.name": "svc"}) == "svc"


def test_unknown_key_keeps_original_text():
    assert render("\${app.missing}", {}) == "\${app.missing}"


def test_default_value_is_used():
    assert render("\${app.missing:-fallback}", {}) == "fallback"


def test_nested_default_is_expanded():
    assert render("\${ctx.x:-\${app.name}}", {"app.name": "svc"}) == "svc"


def test_depth_limit_is_enforced():
    nested = "\${app.a:-\${app.a:-\${app.a:-\${app.a:-\${app.a:-\${app.a:-\${app.a}}}}}}}"
    with pytest.raises(ValueError):
        render(nested, {})


def test_protocol_names_are_rejected():
    with pytest.raises(ValueError):
        render("\${jndi:ldap://evil}", {})


def test_case_and_percent_encoding_are_normalized():
    with pytest.raises(ValueError):
        render("\${%6a%6e%64%69:ldap://evil}", {})


def test_dollar_escape_outputs_literal():
    assert render("\$\${app.name}", {"app.name": "svc"}) == "\${app.name}"


def test_env_prefix_is_allowed():
    assert render("\${env.HOME}", {"env.HOME": "/root"}) == "/root"


def test_sys_prefix_is_rejected():
    with pytest.raises(ValueError):
        render("\${sys.user}", {})


def test_output_length_limit():
    with pytest.raises(ValueError):
        render("\${app.big}", {"app.big": "x" * 5000})


def test_unmatched_braces_are_rejected():
    with pytest.raises(ValueError):
        render("\${app.name", {})


def test_control_characters_are_rejected():
    with pytest.raises(ValueError):
        render("\${app.name}", {"app.name": "bad\nvalue"})


def test_scan_reports_matches_and_positions():
    matches = shield().scan("hello \${jndi:x} and \${app.name}")
    assert len(matches) == 2
    assert matches[0]["start"] == 6


def test_dump_counts_renders_and_denials():
    game = shield()
    game.render("\${app.name}", {"app.name": "svc"}, policy())
    with pytest.raises(ValueError):
        game.render("\${jndi:ldap://evil}", {}, policy())
    info = game.dump()
    assert info["renders"] == 1
    assert info["denied"] == 1
