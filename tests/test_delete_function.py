"""Test for function deletion in the code database."""
import code_db
import pytest

def get_db():
    # code_db.py exposes a global _db instance
    return code_db._db

def test_delete_function(tmp_path):
    db = get_db()
    func = db.add_function(
        name="delete_me",
        description="Function to be deleted",
        code_snippet="function delete_me(x) return x end",
        modules=["test_mod"],
        tags=["delete_test"]
    )
    func_id = func.function_id if hasattr(func, 'function_id') else func
    # Confirm it exists
    found = db.functions.get(func_id)
    assert found is not None
    # Delete the function
    deleted = db.delete_function(func_id)
    assert deleted is True
    # Confirm it is gone
    assert db.functions.get(func_id) is None
    # Confirm tag is cleaned up if unused
    tags = db.list_tags()
    assert "delete_test" not in tags
    # Confirm module still exists (module cleanup is not required)
    modules = db.list_modules()
    assert any(m["name"] == "test_mod" for m in modules)

def test_delete_nonexistent_function():
    db = get_db()
    deleted = db.delete_function("nonexistent-id-123")
    assert deleted is False
