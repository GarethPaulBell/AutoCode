import os
import tempfile
import uuid
import code_db
from src.autocode.mcp_server_fast import generate_module_file


def test_generate_module_file_atomic(tmp_path):
    # Create a sample function and module
    module_name = f"mod_{uuid.uuid4().hex[:6]}"
    func_code = """function hello()\n    return 42\nend\n"""
    fid = code_db.add_function("hello", "desc", func_code, modules=[module_name])
    out_file = str(tmp_path / f"{module_name}.jl")
    res = code_db.generate_module_file(module_name, out_file, with_tests=False)
    assert isinstance(res, dict)
    # Support either 'file' (older behavior) or 'filepath' (new atomic writer)
    filepath = res.get("filepath") or res.get("file")
    assert filepath == out_file
    assert os.path.exists(out_file)
    assert res.get("size") is not None
    assert res.get("sha256") is not None
    # cleanup
    try:
        os.remove(out_file)
    except Exception:
        pass
