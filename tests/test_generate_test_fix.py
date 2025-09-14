import os
import uuid
from src.autocode.mcp_autocode_server import AutoCodeMCPServer
import code_db


def _make_sample_function(code: str, name: str = None):
    name = name or f"fn_{uuid.uuid4().hex[:6]}"
    fid = code_db.add_function(name, "sample", code, modules=["test_module"])
    return fid


def test_generate_test_happy_path():
    server = AutoCodeMCPServer()
    # simple function with docstring and signature
    code = """""Compute square
function square(x::Int)
    return x * x
end
"""""
    fid = _make_sample_function(code, name="square_test_gen")
    res = server._tool_generate_test({"function_id": fid, "name": "auto-test", "description": "generated"})
    assert isinstance(res, dict)
    assert "code" in res and res["code"].strip() != ""


def test_generate_test_missing_docstring():
    server = AutoCodeMCPServer()
    # code without docstring
    code = """
    function inc(x::Int)
        return x + 1
    end
    """
    fid = _make_sample_function(code, name="inc_no_doc")
    res = server._tool_generate_test({"function_id": fid, "name": "auto-test", "description": "generated"})
    assert isinstance(res, dict)
    assert "code" in res and res["code"].strip() != ""


def test_generate_test_large_signature():
    server = AutoCodeMCPServer()
    # function with many parameters to test edge case handling
    names = [f"a{i}" for i in range(20)]
    params = ", ".join([f"{n}::Int" for n in names])
    sum_expr = ", ".join(names)
    code = f"function big({params})\n    return sum([{sum_expr}])\nend\n"
    fid = _make_sample_function(code, name="big_sig")
    res = server._tool_generate_test({"function_id": fid, "name": "auto-test", "description": "generated"})
    assert isinstance(res, dict)
    assert "code" in res and res["code"].strip() != ""
