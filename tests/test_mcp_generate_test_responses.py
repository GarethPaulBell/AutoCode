import types
import pytest

from src.autocode import mcp_autocode_server


class DummyServer(mcp_autocode_server.AutoCodeMCPServer):
    def __init__(self):
        # don't call base init that may try to start IO
        pass


def make_func_record(fid, code="function f() end", signature="f()", docstring="doc", name="f"):
    return {
        "id": fid,
        "code": code,
        "signature": signature,
        "docstring": docstring,
        "name": name,
    }


def test_generate_test_missing_function(monkeypatch):
    server = DummyServer()

    # Simulate code_db.get_function returning None
    monkeypatch.setattr(mcp_autocode_server.code_db, "get_function", lambda fid: None)

    res = server._tool_generate_test({"function_id": "nope", "name": "auto-test", "description": "generated"})

    assert isinstance(res, dict)
    assert res.get("ok") is False
    assert "error" in res
    assert res["error"]["type"] == "FunctionNotFound"
    assert "not found" in res["error"]["message"].lower()


def test_generate_test_not_available(monkeypatch):
    server = DummyServer()
    fid = "f1"
    func = make_func_record(fid)

    monkeypatch.setattr(mcp_autocode_server.code_db, "get_function", lambda fid: func)
    # Simulate write_test_case being absent
    monkeypatch.setattr(mcp_autocode_server.code_db, "write_test_case", None)

    res = server._tool_generate_test({"function_id": fid, "name": "auto-test", "description": "generated"})

    assert isinstance(res, dict)
    assert res.get("ok") is False
    assert "error" in res
    assert res["error"]["type"] == "NotAvailable"
    assert "not available" in res["error"]["message"].lower()


def test_generate_test_write_typeerror_and_fallback_fails(monkeypatch):
    server = DummyServer()
    fid = "f2"
    func = make_func_record(fid, name="myfunc")

    monkeypatch.setattr(mcp_autocode_server.code_db, "get_function", lambda fid: func)

    # Simulate write_test_case raising TypeError on the 4-arg call, and then raising on fallback
    def bad_write(*args, **kwargs):
        raise TypeError("bad signature")

    monkeypatch.setattr(mcp_autocode_server.code_db, "write_test_case", bad_write)

    res = server._tool_generate_test({"function_id": fid, "name": "auto-test", "description": "generated"})

    assert isinstance(res, dict)
    assert res.get("ok") is False
    assert "error" in res
    assert res["error"]["type"] == "GeneratorError"
    assert "fallback_stub_generated" in res["error"]["details"]


def test_generate_test_write_general_exception(monkeypatch):
    server = DummyServer()
    fid = "f3"
    func = make_func_record(fid, name="funcx")

    monkeypatch.setattr(mcp_autocode_server.code_db, "get_function", lambda fid: func)

    def raise_exc(*args, **kwargs):
        raise RuntimeError("model failure")

    monkeypatch.setattr(mcp_autocode_server.code_db, "write_test_case", raise_exc)

    res = server._tool_generate_test({"function_id": fid, "name": "auto-test", "description": "generated"})

    assert isinstance(res, dict)
    assert res.get("ok") is False
    assert "error" in res
    assert res["error"]["type"] == "GeneratorFailure"
    assert "fallback_stub_generated" in res["error"]["details"]


def test_generate_test_add_test_failure(monkeypatch):
    server = DummyServer()
    fid = "f4"
    func = make_func_record(fid, name="fn")

    monkeypatch.setattr(mcp_autocode_server.code_db, "get_function", lambda fid: func)

    # Provide a working write_test_case that returns valid code
    monkeypatch.setattr(mcp_autocode_server.code_db, "write_test_case", lambda *a, **k: "using Test\n@test true\n")

    # Simulate add_test raising when trying to attach the test
    def bad_add(fid_arg, name, description, code):
        raise RuntimeError("db write failed")

    monkeypatch.setattr(mcp_autocode_server.code_db, "add_test", bad_add)

    res = server._tool_generate_test({"function_id": fid, "name": "auto-test", "description": "generated"})

    assert isinstance(res, dict)
    assert res.get("ok") is False
    assert "error" in res
    assert res["error"]["type"] == "AttachTestFailed"
    assert "generated_code" in res["error"]["details"]
