import hashlib
import json
import os

import code_db


def compute_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def test_export_function_and_module(tmp_path):
    # Preserve original DB and restore at the end
    orig_db = getattr(code_db, "_db", None)
    try:
        db = code_db.CodeDatabase()
        code_db._db = db

        # Add a module and function with a test
        func = db.add_function(name="mul2", description="Multiply by two", code_snippet="function mul2(x)\n  return x*2\nend\n", modules=["mymod"]) 
        db.add_unit_test(func.function_id, "test_mul2", "basic", "using Test\n@test mul2(3) == 6\n")

        # Export function JSON
        func_out = tmp_path / "mul2.json"
        res_func = code_db.export_function(func.function_id, str(func_out))
        assert res_func.get("success") is True
        assert os.path.exists(str(func_out))
        assert res_func.get("filepath") == str(func_out)
        assert res_func.get("size") == os.stat(str(func_out)).st_size
        assert res_func.get("sha256") == compute_sha256(str(func_out))

        # Export module JSON
        mod_out = tmp_path / "mymod.json"
        res_mod = code_db.export_module("mymod", str(mod_out))
        assert res_mod.get("success") is True
        assert os.path.exists(str(mod_out))
        assert res_mod.get("filepath") == str(mod_out)
        assert res_mod.get("size") == os.stat(str(mod_out)).st_size
        assert res_mod.get("sha256") == compute_sha256(str(mod_out))

        # Verify JSON structure for module file
        with open(str(mod_out), "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("module_name") == "mymod"
        assert isinstance(data.get("functions"), list) and len(data["functions"]) >= 1

    finally:
        code_db._db = orig_db
