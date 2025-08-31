#!/usr/bin/env python3
"""
MCP Server for AutoCode / code_db

- Mirrors the major commands of code_db_cli.py as MCP tools.
- Uses FastMCP (official Model Context Protocol Python SDK layer).
- Default transport: stdio.

Usage (stdio):
    python mcp_server_fast.py

Then point your MCP-capable client at the stdio command.
"""

from __future__ import annotations

import os
import json
import sys
from typing import Optional, List, Dict, Any, Generator
from mcp.types import TextContent



# --- Optional: honor DB config via environment or per-call kwargs ---
# The code_db module is expected to look up its own persistence config,
# but we expose db-admin tools mirroring the CLI for symmetry.

# Ensure repository root is on sys.path so local top-level modules (e.g., code_db) can be imported
def _ensure_repo_on_path():
    try:
        file_dir = os.path.abspath(os.path.dirname(__file__))
    except NameError:
        file_dir = os.getcwd()
    # Candidate: two levels up from this file (workspace root expected at ../../)
    candidate = os.path.abspath(os.path.join(file_dir, "..", ".."))

    def _find_repo_root(start: str) -> Optional[str]:
        p = start
        for _ in range(10):
            if os.path.exists(os.path.join(p, "code_db.py")) or os.path.exists(os.path.join(p, ".git")):
                return p
            newp = os.path.dirname(p)
            if newp == p:
                break
            p = newp
        return None

    found = _find_repo_root(candidate) or _find_repo_root(os.getcwd())
    repo_root = found or candidate
    if repo_root and repo_root not in sys.path:
        sys.path.insert(0, repo_root)

_ensure_repo_on_path()

# Set MCP mode before importing code_db to suppress stdout prints
os.environ["MCP_AUTOCODE_MODE"] = "1"

try:
    import code_db
except Exception as e:
    raise RuntimeError("Failed to import code_db. Ensure it's on PYTHONPATH.") from e

# FastMCP: install `fastmcp` (>=2.0) in your environment.
try:
    from fastmcp import FastMCP
except ImportError as e:
    raise RuntimeError(
        "fastmcp is required. pip install fastmcp"
    ) from e


# ---------- Helpers ----------

def _ok(data: Any = None) -> Dict[str, Any]:
    return {"ok": True, "data": data}

def _err(msg: str, **extra) -> Dict[str, Any]:
    return {"ok": False, "error": msg, **extra}

def _stream_lines(text: str) -> Generator[TextContent, None, None]:
    # Yield line-by-line to demonstrate streaming
    for line in text.splitlines():
        yield TextContent(line)


# ---------- Server ----------
app = FastMCP("autocode-mcp")

# ---------- DB admin (mirrors CLI) ----------

@app.tool()
def init_db(overwrite: bool = False,
            mode: Optional[str] = None,
            backend: Optional[str] = None,
            db_path: Optional[str] = None,
            project_root: Optional[str] = None) -> Dict[str, Any]:
    """
    Initialize the DB. Returns path.
    """
    from src.autocode.persistence import init_db as db_init  # lazy import to avoid hard dep at import time
    path = db_init(overwrite=overwrite,
                   mode=mode, backend=backend,
                   explicit_path=(None if not db_path else __import__("pathlib").Path(db_path)),
                   project_root=(None if not project_root else __import__("pathlib").Path(project_root)))
    return _ok({"path": str(path)})


@app.tool()
def status_db(mode: Optional[str] = None,
              backend: Optional[str] = None,
              db_path: Optional[str] = None,
              project_root: Optional[str] = None) -> Dict[str, Any]:
    """
    Return DB status/metadata.
    """
    from src.autocode.persistence import status_db as db_status
    info = db_status(mode=mode, backend=backend,
                     explicit_path=(None if not db_path else __import__("pathlib").Path(db_path)),
                     project_root=(None if not project_root else __import__("pathlib").Path(project_root)))
    return _ok(info)


@app.tool()
def migrate_db(to: str,
               overwrite: bool = False,
               mode: Optional[str] = None,
               backend: Optional[str] = None,
               db_path: Optional[str] = None,
               project_root: Optional[str] = None) -> Dict[str, Any]:
    """
    Migrate DB backend between pickle/sqlite.
    """
    from src.autocode.persistence import migrate_db as db_migrate
    dest = db_migrate(to, overwrite=overwrite,
                      mode=mode, backend=backend,
                      explicit_path=(None if not db_path else __import__("pathlib").Path(db_path)),
                      project_root=(None if not project_root else __import__("pathlib").Path(project_root)))
    return _ok({"dest": str(dest)})


@app.tool()
def vacuum_db(mode: Optional[str] = None,
              backend: Optional[str] = None,
              db_path: Optional[str] = None,
              project_root: Optional[str] = None) -> Dict[str, Any]:
    """
    Vacuum/compact DB file.
    """
    from src.autocode.persistence import vacuum_db as db_vacuum
    db_vacuum(mode=mode, backend=backend,
              explicit_path=(None if not db_path else __import__("pathlib").Path(db_path)),
              project_root=(None if not project_root else __import__("pathlib").Path(project_root)))
    return _ok()


@app.tool()
def unlock_db(force: bool = False,
              mode: Optional[str] = None,
              backend: Optional[str] = None,
              db_path: Optional[str] = None,
              project_root: Optional[str] = None) -> Dict[str, Any]:
    """
    Remove a stale DB lock file.
    """
    from src.autocode.persistence import unlock_db as db_unlock
    report = db_unlock(force=force, mode=mode, backend=backend,
                       explicit_path=(None if not db_path else __import__("pathlib").Path(db_path)),
                       project_root=(None if not project_root else __import__("pathlib").Path(project_root)))
    return _ok(report)


# ---------- Core code_db tools ----------

@app.tool()
def list_functions(module: Optional[str] = None,
                   tag: Optional[str] = None) -> Dict[str, Any]:
    """
    List functions with optional module/tag filter.
    """
    try:
        funcs = code_db.list_functions(module, tag)
        return _ok(funcs)
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def get_function(id: str) -> Dict[str, Any]:
    """
    Return full function record by ID.
    """
    try:
        f = code_db.get_function(id)
        if not f:
            return _err("Not found", id=id)
        return _ok(f)
    except Exception as e:
        return _err(f"{e}", id=id)


@app.tool()
def add_function(name: str,
                 description: str,
                 code: str,
                 modules: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Add a new function. Returns new ID.
    """
    try:
        fid = code_db.add_function(name, description, code, modules)
        return _ok({"id": fid})
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def modify_function(id: str,
                    modifier: str,
                    description: str,
                    code: str) -> Dict[str, Any]:
    """
    Modify existing function.
    """
    try:
        code_db.modify_function(id, modifier, description, code)
        return _ok({"id": id})
    except Exception as e:
        return _err(f"{e}", id=id)


@app.tool()
def add_test(function_id: str,
             name: str,
             description: str,
             test_code: str) -> Dict[str, Any]:
    """
    Attach a unit test to a function.
    """
    try:
        tid = code_db.add_test(function_id, name, description, test_code)
        return _ok({"test_id": tid})
    except Exception as e:
        return _err(f"{e}", function_id=function_id)


@app.tool()
def run_tests(function_id: Optional[str] = None) -> Generator[TextContent, None, Dict[str, Any]]:
    """
    Run tests; streams each test result line-by-line and returns the structured list.
    """
    try:
        results = code_db.run_tests(function_id) if function_id else code_db.run_tests()
    except Exception as e:
        yield TextContent(f"error: {e}")
        return _err(f"{e}")

    # Stream human-friendly lines
    for r in results:
        line = f"Test {r['test_id']} | {r['status']}: {r.get('output','')[:200]}"
        yield TextContent(line)
    return _ok(results)


@app.tool()
def get_test_results(function_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch last test results.
    """
    try:
        results = code_db.get_test_results(function_id) if function_id else code_db.get_test_results()
        return _ok(results or [])
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def generate_function(description: str,
                      module: Optional[str] = None) -> Generator[TextContent, None, Dict[str, Any]]:
    """
    Use AI to generate a Julia function + test, add both to DB, and stream the code.
    """
    try:
        result = code_db.generate_julia_function(description)
        gen = result.parsed
        modules = [module] if module else None

        fid = code_db.add_function(gen.function_name, gen.short_description, gen.code, modules)
        tid = code_db.add_test(fid, gen.test_name, gen.test_description, gen.tests)

        # Stream code for preview
        yield from _stream_lines(gen.code)
        yield TextContent("\n---\n# Test\n")
        yield from _stream_lines(gen.tests)

        return _ok({
            "function_id": fid,
            "test_id": tid,
            "name": gen.function_name,
            "module": module,
        })
    except Exception as e:
        yield TextContent(f"error: {e}")
        return _err(f"{e}")


@app.tool()
def generate_test(function_id: str,
                  name: str,
                  description: str) -> Dict[str, Any]:
    """
    AI-generate a unit test for an existing function and attach it.
    """
    try:
        func = code_db.get_function(function_id)
        if not func:
            return _err("Function not found", function_id=function_id)
        test_code = code_db.write_test_case(func["name"])
        tid = code_db.add_test(function_id, name, description, test_code)
        return _ok({"test_id": tid, "test_code": test_code})
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def search_functions(query: str,
                     created_after: Optional[str] = None,
                     modified_after: Optional[str] = None,
                     test_status: Optional[str] = None) -> Dict[str, Any]:
    """
    Search by keyword with optional filters.
    """
    try:
        res = code_db.search_functions(query, created_after=created_after,
                                       modified_after=modified_after,
                                       test_status=test_status)
        return _ok(res or [])
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def list_modules() -> Dict[str, Any]:
    try:
        mods = code_db.list_modules()
        return _ok(mods)
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def add_function_to_module(function_id: str, module: str) -> Dict[str, Any]:
    try:
        code_db.add_function_to_module(function_id, module)
        return _ok({"function_id": function_id, "module": module})
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def export_function(function_id: str, file: str) -> Dict[str, Any]:
    try:
        code_db.export_function(function_id, file)
        return _ok({"file": file})
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def import_function(file: str) -> Dict[str, Any]:
    try:
        new_id = code_db.import_function(file)
        return _ok({"id": new_id})
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def export_module(module: str, file: str) -> Dict[str, Any]:
    try:
        code_db.export_module(module, file)
        return _ok({"module": module, "file": file})
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def import_module(file: str) -> Dict[str, Any]:
    try:
        ids = code_db.import_module(file)
        return _ok({"num_functions": len(ids), "ids": ids})
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def import_julia_file(file: str,
                      module: Optional[str] = None,
                      generate_tests: bool = False) -> Dict[str, Any]:
    try:
        ids = code_db.import_julia_file(file, module_name=module, generate_tests=generate_tests)
        return _ok({"num_functions": len(ids), "ids": ids})
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def generate_module_file(module: str, file: str, with_tests: bool = False) -> Dict[str, Any]:
    try:
        code_db.generate_module_file(module, file, with_tests=with_tests)
        return _ok({"file": file})
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def add_dependency(function_id: str, depends_on_id: str) -> Dict[str, Any]:
    try:
        code_db.add_dependency(function_id, depends_on_id)
        return _ok({"function_id": function_id, "depends_on_id": depends_on_id})
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def list_dependencies(function_id: str) -> Dict[str, Any]:
    try:
        deps = code_db.list_dependencies(function_id) or []
        return _ok(deps)
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def visualize_dependencies(file: str) -> Dict[str, Any]:
    try:
        code_db.visualize_dependencies(file)
        return _ok({"file": file})
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def coverage_report() -> Dict[str, Any]:
    try:
        report = code_db.get_coverage_report() or []
        return _ok(report)
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def list_tags() -> Dict[str, Any]:
    try:
        tags = code_db.list_tags() or []
        return _ok(tags)
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def add_tag(function_id: str, tag: str) -> Dict[str, Any]:
    try:
        code_db.add_tag(function_id, tag)
        return _ok({"function_id": function_id, "tag": tag})
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def semantic_search(query: str, top_k: int = 5) -> Dict[str, Any]:
    try:
        res = code_db.semantic_search_functions(query, top_k=top_k) or []
        return _ok(res)
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def benchmark_function(function_id: str, input_file: str, iterations: int = 1) -> Dict[str, Any]:
    try:
        result = code_db.benchmark_function(function_id, input_file, iterations)
        return _ok(result)
    except Exception as e:
        return _err(f"{e}")


@app.tool()
def property_test(function_id: str, num_tests: int = 50, seed: int = 42) -> Dict[str, Any]:
    try:
        result = code_db.property_test_function(function_id, num_tests, seed)
        return _ok(result)
    except Exception as e:
        return _err(f"{e}")


# ---------- Entrypoint ----------

def main() -> None:
    # stdio transport; you can also expose HTTP/SSE if desired
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
