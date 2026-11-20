import struct

import pytest

import vertex_stream_plan as vp


def plan():
    game = vp.VertexPlan()
    game.add_stream(0, [{"name": "position", "fmt": "float32"}, {"name": "uv", "fmt": "float32"}])
    return game


def inputs():
    return [{"name": "position", "type": "float32"}, {"name": "uv", "type": "float32"}]


def built():
    game = plan()
    game.build(inputs())
    return game


def test_add_stream_accepts_valid_attributes():
    game = plan()
    assert game.layout()["streams"] == 1


def test_offsets_are_four_byte_aligned():
    game = plan()
    game.build(inputs())
    attrs = game.layout()["attributes"]
    for attr in attrs:
        assert attr["offset"] % 4 == 0


def test_explicit_overlap_is_rejected():
    game = vp.VertexPlan()
    with pytest.raises(ValueError):
        game.add_stream(0, [
            {"name": "position", "fmt": "float32", "offset": 0},
            {"name": "uv", "fmt": "float32", "offset": 4},
        ])


def test_stride_must_be_multiple_of_four():
    game = plan()
    with pytest.raises(ValueError):
        game.build(inputs(), stride_hint=10)


def test_more_than_sixteen_attributes_is_rejected():
    game = vp.VertexPlan()
    attrs = [{"name": f"a{i}", "fmt": "uint8"} for i in range(17)]
    with pytest.raises(ValueError):
        game.add_stream(0, attrs)


def test_duplicate_semantic_is_rejected():
    game = plan()
    with pytest.raises(ValueError):
        game.add_stream(1, [{"name": "uv", "fmt": "float32"}])


def test_missing_position_is_rejected():
    game = vp.VertexPlan()
    game.add_stream(0, [{"name": "uv", "fmt": "float32"}])
    with pytest.raises(ValueError):
        game.build([{"name": "uv", "type": "float32"}])


def test_normalized_float_is_rejected():
    game = vp.VertexPlan()
    with pytest.raises(ValueError):
        game.add_stream(0, [{"name": "position", "fmt": "float32", "normalized": True}])


def test_shader_type_mismatch_is_rejected():
    game = plan()
    with pytest.raises(ValueError):
        game.build([{"name": "position", "type": "float16"}, {"name": "uv", "type": "float32"}])


def test_missing_shader_input_gets_default():
    game = plan()
    game.build(inputs() + [{"name": "normal", "type": "float32"}])
    assert "normal" in game.layout()["defaults"]


def test_extra_shader_input_is_rejected():
    game = plan()
    with pytest.raises(ValueError):
        game.build(inputs() + [{"name": "tangent", "type": "float32"}])


def test_pack_writes_bytes_in_layout_order():
    game = built()
    data = game.pack([{"position": (1.0, 2.0, 3.0), "uv": (0.5, 0.25)}])
    assert len(data) == 20
    assert struct.unpack_from("<f", data, 0)[0] == pytest.approx(1.0)


def test_layout_hash_is_stable():
    first = built().layout()["hash"]
    second = built().layout()["hash"]
    assert first == second


def test_unknown_format_is_rejected():
    game = vp.VertexPlan()
    with pytest.raises(ValueError):
        game.add_stream(0, [{"name": "position", "fmt": "float64"}])


def test_layout_returns_copy():
    game = built()
    snap = game.layout()
    snap["streams"] = 99
    assert game.layout()["streams"] == 1
