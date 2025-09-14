import hashlib
import os

import pytest

import code_db


def test_generate_module_file_writes_metadata(tmp_path):
    """Ensure generate_module_file writes an atomic file and returns filepath, size, and sha256 that match the on-disk file.

    This test uses a fresh in-memory CodeDatabase instance to avoid depending on the persisted DB state.
    """
    # Preserve original DB and restore at the end
    orig_db = getattr(code_db, "_db", None)
    try:
        # Create a fresh in-memory database and populate a module + function + unit test
        db = code_db.CodeDatabase()
        code_db._db = db

        # Add module/function and attach a simple unit test
        func = db.add_function(
            name="add_one",
            description="Add one",
            code_snippet="function add_one(x)\n    return x + 1\nend\n",
            modules=["math_utils"],
        )
        db.add_unit_test(func.function_id, "test_add_one", "basic", "using Test\n@test add_one(1) == 2\n")

        # Prepare output path
        outdir = tmp_path / "exports"
        outdir.mkdir()
        outpath = str(outdir / "math_utils.jl")

        # Call the function under test
        res = code_db.generate_module_file("math_utils", outpath, with_tests=True)

        # Validate structured metadata
        assert isinstance(res, dict), "generate_module_file should return a dict"
        assert res.get("filepath") == outpath
        assert isinstance(res.get("size"), int) and res.get("size") > 0
        assert isinstance(res.get("sha256"), str) and len(res.get("sha256")) == 64

        # Validate on-disk file matches metadata
        assert os.path.exists(outpath)
        stat = os.stat(outpath)
        assert stat.st_size == res["size"]

        h = hashlib.sha256()
        with open(outpath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        assert h.hexdigest() == res["sha256"]

    finally:
        # Restore original DB object to avoid side-effects for other tests
        code_db._db = orig_db
