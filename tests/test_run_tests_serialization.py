import types
import json
import pytest

from src.autocode import mcp_autocode_server as server


class DummyNonSerializable:
    def __init__(self, value):
        self.value = value


def generator_with_nonserializable():
    # yields a mix of simple dicts and non-serializable objects
    yield {"status": "start"}
    yield DummyNonSerializable(123)
    yield {"status": "end"}


def list_with_nonserializable():
    return [{"a": 1}, DummyNonSerializable(2), {"b": 3}]


def test_convert_generator_output_to_serializable():
    gen = generator_with_nonserializable()
    # Ensure it's a generator
    assert isinstance(gen, types.GeneratorType)

    converted = server._convert_to_serializable(gen)

    # Should be a list after conversion
    assert isinstance(converted, list)

    # All items must be JSON serializable
    json.dumps(converted)


def test_convert_list_output_to_serializable():
    lst = list_with_nonserializable()
    assert isinstance(lst, list)

    converted = server._convert_to_serializable(lst)
    assert isinstance(converted, list)
    json.dumps(converted)


def test_convert_raises_for_unexpected_type():
    # Scalars should passthrough and be JSON serializable
    out = server._convert_to_serializable(123)
    assert out == 123
    json.dumps(out)
