"""AutoCode: Julia function database and MCP server.

A system for storing, generating, and testing Julia functions with MCP integration.
"""
from __future__ import annotations

import os
import sys
from typing import List, Optional, Dict

# Import pretty test/coverage reporting
from src.autocode.ui import print_test_and_coverage_report
from src.autocode import julia_linter

# Ensure stdout uses UTF-8 encoding for proper output handling
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass  # Ignore if reconfigure is not available

import subprocess
import tempfile
import datetime
import uuid
import pickle
import json
import math
import re
from enum import Enum
from pydantic import BaseModel, Field
from colorama import Fore, Style, init
from tabulate import tabulate
init()

try:
    import openai
    HAVE_OPENAI = True
except Exception:
    HAVE_OPENAI = False

try:
    import ell
    HAVE_ELL = True
except ImportError:
    HAVE_ELL = False

# Use models from the extracted package instead of local duplicates
from src.autocode.models import (
    TestStatusEnum,
    TestResult,
    Modification,
    UnitTest,
    Module,
    Function,
)

# Use persistence module for DB file/location and save/load logic
from src.autocode.persistence import save_db as persistence_save_db, load_db as persistence_load_db, DB_PATH as DB_PATH

# Detect if running in MCP mode (suppress stdout prints to avoid JSON-RPC pollution)
MCP_MODE = os.environ.get("MCP_AUTOCODE_MODE", "").lower() in ("1", "true", "yes")

_db = None

def save_db():
    # persist the in-memory _db using the dedicated persistence helper
    return persistence_save_db(_db)


def load_db():
    global _db
    loaded = persistence_load_db()
    if loaded is not None:
        # Patch for legacy DBs: ensure modules and tags exist
        if isinstance(loaded, CodeDatabase):
            if not hasattr(loaded, "modules") or loaded.modules is None:
                loaded.modules = {}
            if not hasattr(loaded, "tags") or loaded.tags is None:
                loaded.tags = set()
            for func in getattr(loaded, "functions", {}).values():
                if not hasattr(func, "tags") or func.tags is None:
                    func.tags = []
        _db = loaded
    return loaded

# Julia File Parsing Functions
# Use the extracted, tested implementation from src.autocode.julia_parsers
from src.autocode.julia_parsers import (
    parse_julia_file,
    parse_julia_function,
    extract_julia_docstring,
)

# Models are now provided by src.autocode.models and imported near the top of this file.
# The local class definitions were removed as part of the refactor to avoid duplication.
# (Compatibility shims remain in place where needed.)

class CodeDatabase:
    def delete_function(self, function_id: str) -> bool:
        """
        Delete a function by its ID, cleaning up all associated data (unit tests, tags, dependencies, modules).
        Returns True if deleted, False if not found.
        """
        func = self.functions.get(function_id)
        if not func:
            print(f"Function ID {function_id} not found.")
            return False

        # Remove from modules
        for module_name in getattr(func, "modules", []):
            module = self.modules.get(module_name)
            if module and hasattr(module, "functions"):
                module.functions = [f for f in module.functions if f != function_id]

        # Remove from tags
        for tag in getattr(func, "tags", []):
            # Remove tag from global set if no other function uses it
            still_used = any(tag in f.tags for fid, f in self.functions.items() if fid != function_id)
            if not still_used and tag in self.tags:
                self.tags.remove(tag)

        # Remove from dependencies of other functions
        for other_func in self.functions.values():
            if hasattr(other_func, "dependencies"):
                other_func.dependencies = [d for d in other_func.dependencies if d != function_id]

        # Remove test results for this function
        self.test_results = [r for r in self.test_results if r.function_id != function_id]

        # Remove the function itself
        del self.functions[function_id]
        self.last_modified_date = datetime.datetime.now()
        print(f"Deleted Function {function_id} and cleaned up associated data.")
        return True
    def __init__(self):
        self.db_name = "AutomatedDevDB"
        self.db_version = "1.0"
        self.created_date = datetime.datetime.now()
        self.last_modified_date = self.created_date
        self.functions: Dict[str, Function] = {}
        self.modifications: List[Modification] = []
        self.test_results: List[TestResult] = []
        self.modules: Dict[str, Module] = {}
        self.tags: set = set()  # Set of all tags used

    def add_module(self, module_name: str) -> Module:
        if module_name in self.modules:
            return self.modules[module_name]
        mod = Module(module_name)
        self.modules[module_name] = mod
        self.last_modified_date = datetime.datetime.now()
        if not MCP_MODE:
            print(f"Added Module {mod.module_id}: {module_name}")
        return mod

    def add_function(self, name: str, description: str, code_snippet: str, modules: Optional[List[str]] = None, tags: Optional[List[str]] = None) -> Function:
        func = Function(name, description, code_snippet, modules, tags)
        self.functions[func.function_id] = func
        if modules:
            for m in modules:
                self.add_module(m)
                func.add_module(m)
        if tags:
            for tag in tags:
                self.tags.add(tag)
        self.last_modified_date = datetime.datetime.now()
        if not MCP_MODE:
            print(f"Added Function {func.function_id}: {name} (Modules: {modules}, Tags: {tags})")
        return func

    def add_unit_test(self, function_id: str, name: str, description: str, test_case: str) -> Optional[UnitTest]:
        func = self.functions.get(function_id)
        if not func:
            if not MCP_MODE:
                print(f"Function ID {function_id} not found.")
            return None
        test = UnitTest(function_id, name, description, test_case)
        func.add_unit_test(test)
        self.last_modified_date = datetime.datetime.now()
        if not MCP_MODE:
            print(f"Added UnitTest {test.test_id} to Function {function_id}")
        return test

        # Print updated test and coverage report after adding a test
        try:
            print_test_and_coverage_report(self)
        except Exception as e:
            print(f"[WARN] Could not print test/coverage report: {e}")

    def execute_tests(self, function_id: str = None):
        results = []
        # Check for missing function
        if function_id:
            func = self.functions.get(function_id)
            if not func:
                error_result = {
                    "success": False,
                    "error_type": "function_not_found",
                    "message": f"Function ID {function_id} not found.",
                    "suggested_action": "Check the function ID or create the function first."
                }
                return [error_result]
            funcs = [func]
        else:
            funcs = list(self.functions.values())

        # Optionally clear previous results for these functions
        if function_id:
            self.test_results = [r for r in self.test_results if r.function_id != function_id]
        elif funcs:
            func_ids = {f.function_id for f in funcs}
            self.test_results = [r for r in self.test_results if r.function_id not in func_ids]

        for func in funcs:
            if not func:
                continue
            if not func.unit_tests:
                error_result = {
                    "success": False,
                    "error_type": "no_tests_found",
                    "message": f"No unit tests found for function '{func.name}' (ID: {func.function_id}).",
                    "suggested_action": "Add at least one unit test to this function before running tests."
                }
                results.append(error_result)
                continue
            for test in func.unit_tests:
                result = test.run_test(func.code_snippet)
                self.test_results.append(result)
                results.append(result)
                print(f"Test Result: {result}")
        # Print updated test and coverage report after running tests
        try:
            print_test_and_coverage_report(self)
        except Exception as e:
            print(f"[WARN] Could not print test/coverage report: {e}")
        return results

    def modify_function(self, function_id: str, modifier: str, description: str, new_code_snippet: str):
        func = self.functions.get(function_id)
        if not func:
            print(f"Function ID {function_id} not found.")
            return
        func.modify_code(new_code_snippet)
        modification = Modification(function_id, modifier, description)
        self.modifications.append(modification)
        self.last_modified_date = datetime.datetime.now()
        print(f"Logged Modification {modification.modification_id} for Function {function_id}")

        # Print updated test and coverage report after code change
        try:
            print_test_and_coverage_report(self)
        except Exception as e:
            print(f"[WARN] Could not print test/coverage report: {e}")

    def add_function_to_module(self, function_id: str, module_name: str):
        func = self.functions.get(function_id)
        if not func:
            print(f"Function ID {function_id} not found.")
            return
        self.add_module(module_name)
        func.add_module(module_name)
        self.last_modified_date = datetime.datetime.now()
        print(f"Added Function {function_id} to Module {module_name}")

    def add_dependency(self, function_id: str, depends_on_id: str):
        """Add a dependency from one function to another, with circular dependency detection."""
        func = self.functions.get(function_id)
        if not func:
            from src.autocode.errors import make_error
            return make_error("FunctionNotFound", f"Function ID '{function_id}' not found.", "Check the function ID or create the function first.")
        if depends_on_id not in self.functions:
            from src.autocode.errors import make_error
            return make_error("DependencyNotFound", f"Dependency function ID '{depends_on_id}' not found.", "Check the dependency function ID or create the function first.")
        # Detect direct or indirect cycles using DFS
        def has_cycle(start_id, target_id, visited=None):
            if visited is None:
                visited = set()
            if start_id == target_id:
                return True
            visited.add(start_id)
            for dep_id in getattr(self.functions.get(start_id), 'dependencies', []):
                if dep_id not in visited and has_cycle(dep_id, target_id, visited):
                    return True
            return False
        # Check if adding depends_on_id to function_id would create a cycle
        if has_cycle(depends_on_id, function_id):
            from src.autocode.errors import make_error
            return make_error(
                "CircularDependency",
                f"Adding this dependency would create a circular dependency between '{function_id}' and '{depends_on_id}'.",
                "Review the dependency graph and avoid cycles."
            )
        func.add_dependency(depends_on_id)
        self.last_modified_date = datetime.datetime.now()
        return {"success": True, "message": f"Added dependency: {function_id} depends on {depends_on_id}"}

    def add_tag(self, function_id: str, tag: str):
        func = self.functions.get(function_id)
        if not func:
            raise ValueError(f"Function ID {function_id} not found.")
        func.add_tag(tag)
        self.tags.add(tag)
        self.last_modified_date = datetime.datetime.now()
        print(f"Added tag '{tag}' to function {function_id}")

    def list_tags(self):
        if not hasattr(self, "tags") or self.tags is None:
            self.tags = set()
        return sorted(list(self.tags))

    def list_functions_by_tag(self, tag: str):
        return [
            {
                "id": func.function_id,
                "name": func.name,
                "description": func.description,
                "modules": func.modules,
                "tags": func.tags
            }
            for func in self.functions.values()
            if tag in getattr(func, "tags", [])
        ]

    def list_dependencies(self, function_id: str):
        func = self.functions.get(function_id)
        if not func:
            raise ValueError(f"Function ID {function_id} not found.")
        return func.dependencies

    def remove_dependency(self, function_id: str, depends_on_id: str):
        func = self.functions.get(function_id)
        from src.autocode.errors import make_error
        if not func:
            return make_error("FunctionNotFound", f"Function ID '{function_id}' not found.", "Check the function ID or create the function first.")
        if depends_on_id not in getattr(func, 'dependencies', []):
            return make_error("DependencyNotFound", f"Function '{function_id}' does not depend on '{depends_on_id}'.", "Check the dependency list for the function.")
        func.remove_dependency(depends_on_id)
        self.last_modified_date = datetime.datetime.now()
        return {"success": True, "message": f"Removed dependency: {function_id} no longer depends on {depends_on_id}"}

    def _build_dependency_graph(self):
        """Return adjacency list mapping function_id -> list of dependency ids."""
        graph = {}
        for fid, func in self.functions.items():
            graph[fid] = list(getattr(func, 'dependencies', []) or [])
        return graph

    def find_cycles(self):
        """Detect cycles in the dependency graph using DFS and return a list of cycles (each cycle is list of node ids)."""
        graph = self._build_dependency_graph()
        visited = set()
        stack = []
        onstack = set()
        cycles = []

        def dfs(node):
            visited.add(node)
            stack.append(node)
            onstack.add(node)
            for neigh in graph.get(node, []):
                if neigh not in visited:
                    dfs(neigh)
                elif neigh in onstack:
                    # found a cycle: extract segment
                    try:
                        idx = stack.index(neigh)
                        cycle = stack[idx:] + [neigh]
                        cycles.append(cycle)
                    except ValueError:
                        pass
            stack.pop()
            onstack.remove(node)

        for n in graph.keys():
            if n not in visited:
                dfs(n)

        # Deduplicate cycles (normalize by rotating so smallest id first)
        norm = set()
        unique = []
        for c in cycles:
            if not c:
                continue
            # remove trailing duplicate (we appended neigh at end)
            if c[0] == c[-1]:
                c = c[:-1]
            # normalize by smallest id
            minidx = min(range(len(c)), key=lambda i: c[i])
            rc = tuple(c[minidx:] + c[:minidx])
            if rc not in norm:
                norm.add(rc)
                unique.append(list(rc))
        return unique

    def detect_recursion_in_function(self, function_id: str):
        """Heuristic detection of direct or mutual recursion by scanning code for calls to other functions.
        Returns a dict: { 'direct': bool, 'mutual': [path] }
        """
        func = self.functions.get(function_id)
        if not func:
            raise ValueError(f"Function ID {function_id} not found.")
        code = getattr(func, 'code_snippet', '') or ''
        name = func.name
        # Simple direct recursion: function name appears followed by '(' in code
        direct = False
        try:
            import re
            # match name(... or name :: (for higher-order) but avoid function declaration
            pattern = re.compile(r"\b" + re.escape(name) + r"\s*\(")
            if pattern.search(code):
                direct = True
        except Exception:
            direct = False

        # For mutual recursion, check if dependency graph contains a cycle involving this function
        cycles = self.find_cycles()
        mutual = [c for c in cycles if function_id in c]
        return {"direct": direct, "mutual_cycles": mutual}

    def visualize_dependencies(self, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("digraph dependencies {\n")
            for func in self.functions.values():
                for dep in getattr(func, "dependencies", []):
                    f.write(f'    "{func.function_id}" -> "{dep}";\n')
            f.write("}\n")
        print(f"Dependency graph written to {filepath}")

    def list_modules(self):
        if not hasattr(self, "modules") or self.modules is None:
            self.modules = {}
        return [{"id": m.module_id, "name": m.name} for m in self.modules.values()]

    def list_functions(self, module: Optional[str] = None, tag: Optional[str] = None):
        def get_modules_safe(func):
            if not hasattr(func, "modules") or func.modules is None:
                func.modules = []
            return func.modules
        def get_tags_safe(func):
            if not hasattr(func, "tags") or func.tags is None:
                func.tags = []
            return func.tags

        funcs = list(self.functions.values())
        if module:
            funcs = [func for func in funcs if module in get_modules_safe(func)]
        if tag:
            funcs = [func for func in funcs if tag in get_tags_safe(func)]
        return [
            {
                "id": func.function_id,
                "name": func.name,
                "description": func.description,
                "modules": get_modules_safe(func),
                "tags": get_tags_safe(func)
            }
            for func in funcs
        ]

    def __repr__(self):
        return (f"<CodeDatabase: {self.db_name} v{self.db_version}, "
                f"Created: {self.created_date.isoformat()}, "
                f"Last Modified: {self.last_modified_date.isoformat()}, "
                f"Functions: {len(self.functions)}, Modules: {len(self.modules)}, Tags: {len(self.tags)}>")
    
    # Simple JSON export/import helpers
def export_function(function_id: str, filepath: str):
    try:
        func = _db.functions.get(function_id)
        if not func:
            return {
                "success": False,
                "error_type": "FunctionNotFound",
                "message": f"Function ID '{function_id}' not found.",
                "suggested_action": "Check the function ID or create the function first."
            }

        # Lint the function code for compatibility issues before export
        lint_result = julia_linter.lint_julia_code(func.code_snippet, fix=False)
        if not lint_result.success:
            error_messages = [issue.message for issue in lint_result.issues if issue.severity == 'error']
            return {
                "success": False,
                "error_type": "LintingFailed",
                "message": f"Function contains compatibility errors that prevent export: {', '.join(error_messages)}",
                "suggested_action": "Fix the compatibility issues in the function code before exporting.",
                "lint_issues": [{"type": i.type, "message": i.message, "severity": i.severity} for i in lint_result.issues]
            }

        if not hasattr(func, "modules") or func.modules is None:
            func.modules = []
        if not hasattr(func, "tags") or func.tags is None:
            func.tags = []
        if os.path.exists(filepath):
            return {
                "success": False,
                "error_type": "FileExists",
                "message": f"File '{filepath}' already exists.",
                "suggested_action": "Choose a different file path or remove the existing file."
            }
        data = {
            "function_id": func.function_id,
            "name": func.name,
            "description": func.description,
            "code_snippet": func.code_snippet,
            "modules": func.modules,
            "tags": func.tags,
            "creation_date": func.creation_date.isoformat(),
            "last_modified_date": func.last_modified_date.isoformat(),
            "unit_tests": [
                {
                    "test_id": t.test_id,
                    "name": t.name,
                    "description": t.description,
                    "test_case": t.test_case,
                }
                for t in getattr(func, "unit_tests", [])
            ],
        }
        # Write atomically to avoid partial files: write to temp in same dir, fsync, then replace
        import tempfile
        import hashlib
        dirpath = os.path.dirname(os.path.abspath(filepath)) or os.getcwd()
        basename = os.path.basename(filepath)
        fd, tmp_path = tempfile.mkstemp(prefix=basename + '.', dir=dirpath, text=True)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            os.replace(tmp_path, filepath)
            # Compute metadata
            stat = os.stat(filepath)
            size = stat.st_size
            sha256 = hashlib.sha256()
            with open(filepath, 'rb') as r:
                for chunk in iter(lambda: r.read(8192), b''):
                    sha256.update(chunk)
            digest = sha256.hexdigest()
            return {"success": True, "filepath": filepath, "size": size, "sha256": digest}
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error_type": "PythonException",
            "message": str(e),
            "suggested_action": "Check the Python traceback for details and report this as a bug if unexpected.",
            "traceback": traceback.format_exc()
        }

def import_function(filepath: str, override: bool = False):
    """
    Import a function from a JSON file. If a function with the same name (case-insensitive, trimmed) exists, abort unless override is True.
    If override is True, skip importing the colliding function and report it.
    """
    try:
        if not os.path.exists(filepath):
            return {
                "success": False,
                "error_type": "FileNotFound",
                "message": f"File '{filepath}' not found.",
                "suggested_action": "Check the file path or export a function first."
            }
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        imported_name = data["name"].strip().lower()
        for f in _db.functions.values():
            if f.name.strip().lower() == imported_name:
                if not override:
                    return {
                        "success": False,
                        "error_type": "FunctionNameCollision",
                        "message": f"A function named '{data['name']}' already exists (case-insensitive, trimmed).",
                        "suggested_action": "Rename the function before importing, delete the existing one, or use override=True to skip importing this function."
                    }
                else:
                    return {
                        "success": True,
                        "message": f"Skipped import: function named '{data['name']}' already exists. No overwrite performed.",
                        "skipped": True
                    }
        func = Function(
            name=data["name"],
            description=data["description"],
            code_snippet=data["code_snippet"],
            modules=data.get("modules", []),
            tags=data.get("tags", []),
        )
        _db.functions[func.function_id] = func
        for t in data.get("unit_tests", []):
            test = UnitTest(
                function_id=func.function_id,
                name=t["name"],
                description=t.get("description", ""),
                test_case=t["test_case"],
            )
            func.add_unit_test(test)
        for tag in getattr(func, "tags", []):
            _db.tags.add(tag)
        _db.last_modified_date = datetime.datetime.now()
        save_db()
        return {"success": True, "message": f"Imported function '{func.name}' with new ID: {func.function_id}", "function_id": func.function_id}
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error_type": "PythonException",
            "message": str(e),
            "suggested_action": "Check the Python traceback for details and report this as a bug if unexpected.",
            "traceback": traceback.format_exc()
        }

def export_module(module_name: str, filepath: str):
    try:
        if module_name not in _db.modules:
            return {
                "success": False,
                "error_type": "ModuleNotFound",
                "message": f"Module '{module_name}' not found.",
                "suggested_action": "Check the module name or create the module first."
            }
        if os.path.exists(filepath):
            return {
                "success": False,
                "error_type": "FileExists",
                "message": f"File '{filepath}' already exists.",
                "suggested_action": "Choose a different file path or remove the existing file."
            }
        functions = [
            f for f in _db.functions.values()
            if module_name in (f.modules if hasattr(f, "modules") else [])
        ]
        data = {
            "module_name": module_name,
            "functions": [
                {
                    "function_id": func.function_id,
                    "name": func.name,
                    "description": func.description,
                    "code_snippet": func.code_snippet,
                    "creation_date": func.creation_date.isoformat(),
                    "last_modified_date": func.last_modified_date.isoformat(),
                    "modules": func.modules,
                    "tags": getattr(func, "tags", []),
                    "unit_tests": [
                        {
                            "test_id": t.test_id,
                            "name": t.name,
                            "description": t.description,
                            "test_case": t.test_case
                        }
                        for t in func.unit_tests
                    ]
                }
                for func in functions
            ]
        }
        # Atomic write: write to temp file in same dir, fsync, then replace
        import tempfile
        import hashlib
        dirpath = os.path.dirname(os.path.abspath(filepath)) or os.getcwd()
        basename = os.path.basename(filepath)
        fd, tmp_path = tempfile.mkstemp(prefix=basename + '.', dir=dirpath, text=True)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            os.replace(tmp_path, filepath)
            stat = os.stat(filepath)
            size = stat.st_size
            sha256 = hashlib.sha256()
            with open(filepath, 'rb') as r:
                for chunk in iter(lambda: r.read(8192), b''):
                    sha256.update(chunk)
            digest = sha256.hexdigest()
            return {"success": True, "filepath": filepath, "size": size, "sha256": digest}
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error_type": "PythonException",
            "message": str(e),
            "suggested_action": "Check the Python traceback for details and report this as a bug if unexpected.",
            "traceback": traceback.format_exc()
        }

def import_module(filepath: str):
    try:
        if not os.path.exists(filepath):
            return {
                "success": False,
                "error_type": "FileNotFound",
                "message": f"File '{filepath}' not found.",
                "suggested_action": "Check the file path or export a module first."
            }
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        module_name = data["module_name"]
        # Check for collision by module name
        if module_name in _db.modules:
            return {
                "success": False,
                "error_type": "ModuleNameCollision",
                "message": f"A module named '{module_name}' already exists.",
                "suggested_action": "Rename the module before importing or delete the existing one."
            }
        _db.add_module(module_name)
        new_func_ids = []
        for func_data in data.get("functions", []):
            # Check for function name collision
            for f in _db.functions.values():
                if f.name == func_data["name"]:
                    return {
                        "success": False,
                        "error_type": "FunctionNameCollision",
                        "message": f"A function named '{func_data['name']}' already exists.",
                        "suggested_action": "Rename the function before importing or delete the existing one."
                    }
            func = Function(
                name=func_data["name"],
                description=func_data["description"],
                code_snippet=func_data["code_snippet"],
                modules=func_data.get("modules", []),
                tags=func_data.get("tags", [])
            )
            _db.functions[func.function_id] = func
            for t in func_data.get("unit_tests", []):
                test = UnitTest(
                    function_id=func.function_id,
                    name=t["name"],
                    description=t["description"],
                    test_case=t["test_case"]
                )
                func.add_unit_test(test)
            for tag in getattr(func, "tags", []):
                _db.tags.add(tag)
            new_func_ids.append(func.function_id)
        _db.last_modified_date = datetime.datetime.now()
        save_db()
        return {"success": True, "message": f"Imported module '{module_name}' with {len(new_func_ids)} functions.", "function_ids": new_func_ids}
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error_type": "PythonException",
            "message": str(e),
            "suggested_action": "Check the Python traceback for details and report this as a bug if unexpected.",
            "traceback": traceback.format_exc()
        }

def import_julia_file(filepath: str, module_name: str = None, generate_tests: bool = False):
    """
    Import functions from a Julia (.jl) file.
    
    Args:
        filepath: Path to the Julia file
        module_name: Optional module name override (uses parsed module name if not provided)
        generate_tests: Whether to auto-generate basic tests for functions
    
    Returns:
        List of imported function IDs
    """
    try:
        parsed_data = parse_julia_file(filepath)
    except Exception as e:
        raise ValueError(f"Error parsing Julia file: {e}")
    
    # Use provided module name or parsed module name or filename
    final_module_name = module_name or parsed_data.get('module_name')
    if not final_module_name:
        # Use filename without extension as module name
        final_module_name = os.path.splitext(os.path.basename(filepath))[0]
    
    # Add module to database if it doesn't exist
    if final_module_name not in _db.modules:
        _db.add_module(final_module_name)
    
    new_func_ids = []
    for func_data in parsed_data['functions']:
        # Create function object
        func = Function(
            name=func_data['name'],
            description=func_data['description'],
            code_snippet=func_data['code'],
            modules=[final_module_name],
            tags=['julia', 'imported']
        )
        _db.functions[func.function_id] = func
        
        # Generate basic test if requested
        if generate_tests:
            try:
                # Extract function code, signature, and docstring for context-aware test generation
                function_code = func_data['code']
                parsed = parse_julia_function(function_code)
                signature = parsed['declaration'] if parsed and 'declaration' in parsed else ''
                # Extract docstring from code lines
                code_lines = function_code.strip().split('\n')
                docstring, _ = extract_julia_docstring(code_lines, 0)
                test_code = write_test_case(function_code, signature, docstring, func_data['name'])
                if test_code:
                    test = UnitTest(
                        function_id=func.function_id,
                        name=f"test_{func_data['name']}_basic",
                        description=f"Auto-generated basic test for {func_data['name']}",
                        test_case=test_code
                    )
                    func.add_unit_test(test)
            except Exception as e:
                print(f"Warning: Could not generate test for {func_data['name']}: {e}")
        
        # Add tags to global set
        for tag in getattr(func, "tags", []):
            _db.tags.add(tag)
        
        new_func_ids.append(func.function_id)
        print(f"Imported function '{func_data['name']}' with ID: {func.function_id}")
    
    _db.last_modified_date = datetime.datetime.now()
    save_db()
    print(f"Imported {len(new_func_ids)} functions from Julia file '{filepath}' into module '{final_module_name}'")
    return new_func_ids

def search_functions(query: str, created_after: str = None, modified_after: str = None, test_status: str = None):
    query_lower = query.lower()
    results = []
    for func in _db.functions.values():
        if not hasattr(func, "modules") or func.modules is None:
            func.modules = []
        if not hasattr(func, "tags") or func.tags is None:
            func.tags = []
        if (query_lower in func.name.lower() or
            query_lower in func.description.lower() or
            query_lower in func.code_snippet.lower()):
            if created_after:
                try:
                    created_dt = datetime.datetime.fromisoformat(created_after)
                    if func.creation_date < created_dt:
                        continue
                except Exception:
                    pass
            if modified_after:
                try:
                    modified_dt = datetime.datetime.fromisoformat(modified_after)
                    if func.last_modified_date < modified_dt:
                        continue
                except Exception:
                    pass
            if test_status:
                last_status = None
                for r in reversed(_db.test_results):
                    if r.function_id == func.function_id:
                        last_status = r.status.value
                        break
                if last_status is None or last_status.lower() != test_status.lower():
                    continue
            results.append({
                "id": func.function_id,
                "name": func.name,
                "description": func.description,
                "modules": func.modules,
                "tags": func.tags
            })
    return results

def import_module(filepath: str, override: bool = False):
    """
    Import a module from a JSON file. If a module or any function with the same name (case-insensitive, trimmed) exists, abort unless override is True.
    If override is True, skip importing colliding module/functions and report them.
    """
    try:
        if not os.path.exists(filepath):
            return {
                "success": False,
                "error_type": "FileNotFound",
                "message": f"File '{filepath}' not found.",
                "suggested_action": "Check the file path or export a module first."
            }
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        module_name = data["module_name"]
        norm_mod_name = module_name.strip().lower()
        existing_mods = {m.strip().lower() for m in _db.modules.keys()}
        if norm_mod_name in existing_mods:
            if not override:
                return {
                    "success": False,
                    "error_type": "ModuleNameCollision",
                    "message": f"A module named '{module_name}' already exists (case-insensitive, trimmed).",
                    "suggested_action": "Rename the module before importing, delete the existing one, or use override=True to skip importing this module."
                }
            else:
                return {
                    "success": True,
                    "message": f"Skipped import: module named '{module_name}' already exists. No overwrite performed.",
                    "skipped": True
                }
        _db.add_module(module_name)
        new_func_ids = []
        collisions = []
        existing_func_names = {f.name.strip().lower() for f in _db.functions.values()}
        for func_data in data.get("functions", []):
            norm_func_name = func_data["name"].strip().lower()
            if norm_func_name in existing_func_names:
                collisions.append(func_data["name"])
                continue
            func = Function(
                name=func_data["name"],
                description=func_data["description"],
                code_snippet=func_data["code_snippet"],
                modules=func_data.get("modules", []),
                tags=func_data.get("tags", [])
            )
            _db.functions[func.function_id] = func
            for t in func_data.get("unit_tests", []):
                test = UnitTest(
                    function_id=func.function_id,
                    name=t["name"],
                    description=t["description"],
                    test_case=t["test_case"]
                )
                func.add_unit_test(test)
            for tag in getattr(func, "tags", []):
                _db.tags.add(tag)
            new_func_ids.append(func.function_id)
        _db.last_modified_date = datetime.datetime.now()
        save_db()
        if collisions:
            return {
                "success": False if not override else True,
                "error_type": "FunctionNameCollision" if not override else None,
                "message": f"The following function names already exist and were skipped: {collisions}",
                "function_ids": new_func_ids,
                "skipped_functions": collisions
            }
        return {"success": True, "message": f"Imported module '{module_name}' with {len(new_func_ids)} functions.", "function_ids": new_func_ids}
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error_type": "PythonException",
            "message": str(e),
            "suggested_action": "Check the Python traceback for details and report this as a bug if unexpected.",
            "traceback": traceback.format_exc()
        }

# Use extracted modules directly (no fallback paths). These modules were moved to src.autocode during the refactor.
try:
    from src.autocode.ell_wrappers import (
        JuliaCodePackage,
        generate_julia_function,
        modify_julia_function,
        write_test_case,
        evaluate_output,
    )
    HAVE_ELL_WRAPPERS = True
except ImportError:
    HAVE_ELL_WRAPPERS = False
    JuliaCodePackage = None
    generate_julia_function = None
    modify_julia_function = None
    write_test_case = None
    evaluate_output = None

def generate_module_file(module_name: str, filepath: str, with_tests: bool = False):
    if module_name not in _db.modules:
        raise ValueError(f"Module '{module_name}' not found.")
    functions = [
        f for f in _db.functions.values()
        if module_name in (f.modules if hasattr(f, "modules") else [])
    ]
    if not functions:
        raise ValueError(f"No functions found in module '{module_name}'.")
    # Write atomically: write to a temp file in the same directory then fsync and rename
    import tempfile
    import hashlib
    dirpath = os.path.dirname(os.path.abspath(filepath)) or os.getcwd()
    basename = os.path.basename(filepath)
    fd, tmp_path = tempfile.mkstemp(prefix=basename + '.', dir=dirpath, text=True)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(f"module {module_name}\n\n")
            for func in functions:
                f.write(f"# Function: {func.name}\n")
                f.write(f"# Description: {func.description}\n")
                f.write(func.code_snippet.strip() + "\n\n")
                if with_tests and func.unit_tests:
                    for test in func.unit_tests:
                        f.write(f"# Test: {test.name}\n")
                        f.write(f"# {test.description}\n")
                        f.write(test.test_case.strip() + "\n\n")
            f.write(f"end # module {module_name}\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                # best-effort; on some platforms fsync may be unavailable
                pass
        # Rename into place atomically
        os.replace(tmp_path, filepath)

        # Compute metadata
        stat = os.stat(filepath)
        size = stat.st_size
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as r:
            for chunk in iter(lambda: r.read(8192), b''):
                sha256.update(chunk)
        digest = sha256.hexdigest()
        print(f"Generated Julia module file '{filepath}' for module '{module_name}' (with_tests={with_tests})")
        return {"filepath": filepath, "size": size, "sha256": digest}
    finally:
        # ensure temp file cleanup if rename failed
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

def get_coverage_report():
    report = []
    for func in _db.functions.values():
        test_ids = [t.test_id for t in func.unit_tests]
        total_tests = len(test_ids)
        passed = 0
        failed = 0
        for tid in test_ids:
            last_result = None
            for r in reversed(_db.test_results):
                if r.test_id == tid:
                    last_result = r
                    break
            if last_result:
                if last_result.status == TestStatusEnum.PASSED:
                    passed += 1
                elif last_result.status == TestStatusEnum.FAILED:
                    failed += 1
        coverage = (passed / total_tests * 100) if total_tests > 0 else 0
        report.append({
            "id": func.function_id,
            "name": func.name,
            "num_tests": total_tests,
            "passed": passed,
            "failed": failed,
            "coverage_percent": coverage
        })
    return report

def benchmark_function(function_id: str, input_file: str, iterations: int = 1):
    """
    Benchmark a function by running it with the provided input code N times.
    input_file: path to a file containing Julia code that calls the function (e.g., test inputs).
    Returns a dict with timing and memory stats for each run.
    This version uses the persistent Julia runner to avoid subprocess startup costs.
    """
    try:
        func = _db.functions.get(function_id)
        if not func:
            return {
                "success": False,
                "error_type": "FunctionNotFound",
                "message": f"Function ID '{function_id}' not found.",
                "suggested_action": "Check the function ID or create the function first.",
                "runs": [],
                "stderr": ""
            }
        if not os.path.exists(input_file):
            return {
                "success": False,
                "error_type": "InputFileNotFound",
                "message": f"Input file '{input_file}' not found.",
                "suggested_action": "Check the file path or generate the input file.",
                "runs": [],
                "stderr": ""
            }
        with open(input_file, "r", encoding="utf-8") as f:
            input_code = f.read()

        # --- Input validation: ensure input file is not empty and calls the target function ---
        if not input_code.strip():
            return {
                "success": False,
                "error_type": "EmptyInputFile",
                "message": f"Input file '{input_file}' is empty.",
                "suggested_action": "Provide a Julia input file that calls the target function (e.g., `println(myfunc(args))`).",
                "runs": [],
                "stderr": ""
            }

        func_name = getattr(func, 'name', None)
        if func_name:
            try:
                import re

                def _strip_strings_and_comments(code_text: str) -> str:
                    # remove triple-quoted strings
                    code_text = re.sub(r'""".*?"""', '', code_text, flags=re.S)
                    # remove single/double quoted strings
                    code_text = re.sub(r"'(?:\\.|[^'])*'", '', code_text)
                    code_text = re.sub(r'"(?:\\.|[^"])*"', '', code_text)
                    # remove comments
                    code_text = re.sub(r'#.*', '', code_text)
                    return code_text

                # Remove lines that are function declarations to avoid false positives
                lines = input_code.splitlines()
                filtered = []
                func_decl_re = re.compile(r'^\s*function\b')
                single_line_decl_re = re.compile(r'^\s*[A-Za-z_][A-Za-z0-9_!]*\s*\([^)]*\)\s*=')
                for ln in lines:
                    s = ln.strip()
                    if func_decl_re.match(s) or single_line_decl_re.match(s):
                        # skip declaration lines
                        continue
                    filtered.append(ln)

                cleaned = '\n'.join(filtered)
                cleaned = _strip_strings_and_comments(cleaned)

                # Look for module-qualified or plain calls: e.g., name(  or Module.name(
                pattern = re.compile(r'(?:\b|\.)' + re.escape(func_name) + r'\s*\(')
                if not pattern.search(cleaned):
                    return {
                        "success": False,
                        "error_type": "InputDoesNotCallFunction",
                        "message": f"Input file '{input_file}' does not appear to call function '{func_name}'.",
                        "suggested_action": "Ensure the input file invokes the function at least once, e.g., add a line `println(<function_name>(...))`.",
                        "runs": [],
                        "stderr": ""
                    }
            except Exception:
                # If validation fails for unexpected reasons, proceed but include no blocking error
                pass

        # Compose Julia script: function code + input code wrapped in @time
        julia_script = f"""
{func.code_snippet}

for i in 1:{iterations}
    println("===BENCHMARK_RUN_START===")
    @time begin
{input_code}
    end
    println("===BENCHMARK_RUN_END===")
end
"""

        # Use persistent runner to evaluate the script and capture printed output
        from src.autocode import julia_runner
        success, output = julia_runner.run_julia(julia_script, timeout=60.0)

        if not success:
            # Try to parse common Julia error patterns for actionable feedback
            import re
            error_msg = output.strip().splitlines()[-1] if output.strip() else "Unknown Julia error."
            if "syntax error" in output.lower():
                suggested = "Check your function and input code for syntax errors."
                error_type = "JuliaSyntaxError"
            elif "methoderror" in output:
                suggested = "Check that the function is called with correct argument types."
                error_type = "JuliaMethodError"
            elif "loaderror" in output:
                suggested = "Check for missing modules or bad includes in your code."
                error_type = "JuliaLoadError"
            else:
                suggested = "Check the full Julia error output for details."
                error_type = "JuliaError"
            return {
                "success": False,
                "error_type": error_type,
                "message": error_msg,
                "suggested_action": suggested,
                "runs": [],
                "stderr": output
            }

        stdout = output
        # Parse output for @time results
        import re
        pattern = r"===BENCHMARK_RUN_START===\s*(.*?)\s*===BENCHMARK_RUN_END==="
        runs = re.findall(pattern, stdout, re.DOTALL)
        results = []
        for run in runs:
            time_line = None
            for line in run.splitlines():
                if "seconds" in line and "allocation" in line:
                    time_line = line.strip()
                    break
            results.append({
                "raw_output": run.strip(),
                "time_line": time_line
            })
        return {
            "success": True,
            "runs": results,
            "stderr": ""
        }
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return {
            "success": False,
            "error_type": "PythonException",
            "message": str(e),
            "suggested_action": "Check the Python traceback for details and report this as a bug if unexpected.",
            "runs": [],
            "stderr": tb
        }


def property_test_function(function_id: str, num_tests: int = 50, seed: int = 42):
    """
    Generate and run property-based tests for a Julia function using a fixed random seed.
    Returns a list of test results (pass/fail and any error messages).
    This version uses the persistent Julia runner to avoid spawning Julia processes.

    Additional debug/logging and a fallback subprocess.run are included to help
    diagnose hangs/timeouts when using the persistent runner.
    """
    func = _db.functions.get(function_id)
    if not func:
        return {
            "success": False,
            "error_type": "function_not_found",
            "message": f"Function ID {function_id} not found.",
            "suggested_action": "Check the function ID or create the function first."
        }

    # --- Check for macros in the function code and warn the user if any are found ---
    macro_pattern = r"@(\w+)"
    macros_found = set(re.findall(macro_pattern, func.code_snippet))
    if macros_found:
        print(f"[WARNING] The function code uses the following Julia macros: {', '.join('@'+m for m in macros_found)}")
        print("[WARNING] If these macros are from external packages, you may need to manually add the appropriate 'using ...' statement to your function code.")
        print("[WARNING] Property-based testing will proceed, but may fail if required macros are not imported.")

    # --- Determine the function name to call: prefer parsing it from the code snippet ---
    try:
        from src.autocode.julia_parsers import parse_julia_function
        parsed = parse_julia_function(func.code_snippet)
        if parsed and parsed.get('name'):
            call_name = parsed['name']
        else:
            call_name = func.name
    except Exception:
        call_name = func.name

    # --- Argument generation based on signature ---
    sig = getattr(func, "signature", None)
    if not sig or not sig.get("arg_names"):
        predecl_lines = ["arg = nothing"]
        assign_lines = ["arg = rand(-1000:1000)"]
        call_args = "arg"
        arg_print = '", arg=", arg'
    else:
        assign_lines = []
        call_args_list = []
        arg_prints = []
        predecl_lines = []
        for i, (name, typ) in enumerate(zip(sig["arg_names"], sig["arg_types"])):
            var = f"arg{i+1}"
            if typ is None or (isinstance(typ, str) and typ.lower().startswith("int")):
                expr = f"{var} = rand(-1000:1000)"
            elif isinstance(typ, str) and "matrix" in typ.lower():
                expr = f"{var} = rand(-10.0:0.1:10.0, 3, 3)"
            elif isinstance(typ, str) and "float" in typ.lower():
                expr = f"{var} = rand() * 2000 - 1000"
            elif isinstance(typ, str) and "vector" in typ.lower():
                expr = f"{var} = rand(-10.0:0.1:10.0, 5)"
            else:
                expr = f"{var} = rand(-1000:1000)"
            assign_lines.append(expr)
            predecl_lines.append(f"{var} = nothing")
            call_args_list.append(var)
            arg_prints.append(f'\", {name}=\", {var}')
        call_args = ", ".join(call_args_list)
        arg_print = "".join(arg_prints)

    predecl_block = "\n        ".join(predecl_lines)
    assign_block = "\n            ".join(assign_lines)
    julia_script = f"""

using Random
Random.seed!({seed})

{func.code_snippet}

function _property_test_runner()
    for i in 1:{num_tests}
        {predecl_block}
        try
            {assign_block}
            result = {call_name}({call_args})
            @assert !isnothing(result)
            println("PROPERTY_TEST_PASS i=", i, {arg_print})
        catch err
            println("PROPERTY_TEST_FAIL i=", i, {arg_print}, " error=", err)
        end
    end

end

_property_test_runner()
"""

    # --- Debugging: write the script to a temp file for inspection and as a fallback ---
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jl', delete=False) as tmpf:
        tmpf.write(julia_script)
        tmpfile = tmpf.name
    print(f"[DEBUG] Property test script written to: {tmpfile} (size={os.path.getsize(tmpfile)})")
    print("[DEBUG] Script preview:\n" + (julia_script[:2000]))

    # Quick sanity-run with subprocess.run to see if the script itself executes outside
    try:
        print("[DEBUG] Running quick subprocess sanity-check for the Julia script...")
        proc = subprocess.run(["julia", tmpfile], capture_output=True, text=True, timeout=10)
        print(f"[DEBUG] Subprocess returncode={proc.returncode}")
        if proc.stdout:
            print("[DEBUG] Subprocess stdout sample:\n", "\n".join(proc.stdout.splitlines()[:10]))
        if proc.stderr:
            print("[DEBUG] Subprocess stderr sample:\n", "\n".join(proc.stderr.splitlines()[:10]))
    except FileNotFoundError:
        print("[DEBUG] Julia executable not found for subprocess sanity check.")
    except subprocess.TimeoutExpired:
        print("[DEBUG] Subprocess sanity-check timed out (script may be long-running).")
    except Exception as e:
        print(f"[DEBUG] Subprocess sanity-check raised exception: {e}")

    # Use persistent runner
    from src.autocode import julia_runner
    print("[DEBUG] Sending script to persistent Julia runner (timeout=60s)")
    try:
        success, output = julia_runner.run_julia(julia_script, timeout=60.0)
    except Exception as e:
        print(f"[DEBUG] Persistent runner raised exception: {e}")
        # Cleanup temp file
        try:
            os.remove(tmpfile)
        except Exception:
            pass
        return {
            "success": False,
            "error_type": "python_exception",
            "message": str(e),
            "suggested_action": "Check the Python test harness and file operations."
        }

    print(f"[DEBUG] Persistent runner returned success={success}; output sample:\n{output.splitlines()[:20]}")

    results = []
    if not success:
        # On failure include stderr output for diagnosis
        try:
            # include last 2000 chars to avoid huge payloads
            stderr_snip = output[-2000:]
        except Exception:
            stderr_snip = output
        print(f"[DEBUG] Persistent runner failure output:\n{stderr_snip}")
        try:
            os.remove(tmpfile)
        except Exception:
            pass
        # Heuristics for common Julia errors
        error_type = "julia_error"
        message = stderr_snip or "Property-based test failed with unknown error."
        suggested_action = "Check the function code and property test logic for errors."
        if stderr_snip:
            if "AssertionError" in stderr_snip:
                error_type = "assertion_failure"
                suggested_action = "Check the property test assertions and expected outputs."
            elif "syntax error" in stderr_snip or "ParseError" in stderr_snip:
                error_type = "syntax_error"
                suggested_action = "Check the function code for syntax errors."
            elif "UndefVarError" in stderr_snip or "not defined" in stderr_snip:
                error_type = "undefined_variable"
                suggested_action = "Check for typos or missing definitions in the function or test."
            elif "LoadError" in stderr_snip:
                error_type = "load_error"
                suggested_action = "Check included files and their paths."
        return {
            "success": False,
            "error_type": error_type,
            "message": message,
            "suggested_action": suggested_action
        }

    stdout = output
    for line in stdout.splitlines():
        if line.startswith("PROPERTY_TEST_PASS"):
            results.append({"status": "pass", "info": line})
        elif line.startswith("PROPERTY_TEST_FAIL"):
            results.append({"status": "fail", "info": line})

    try:
        os.remove(tmpfile)
    except Exception:
        pass

    return {"success": True, "results": results, "stderr": ""}

# Models and parsers are imported from src.autocode at module top; no local shims required.


# --- Command Registry Implementation ---
COMMAND_REGISTRY = {}

def register_command(name=None):
    """Decorator to register a function as a command in the registry."""
    def decorator(func):
        cmd_name = name or func.__name__
        COMMAND_REGISTRY[cmd_name] = func
        return func
    return decorator

def list_commands():
    """Return a list of all registered commands and their docstrings."""
    return [
        {
            "name": name,
            "doc": (func.__doc__ or "").strip()
        }
        for name, func in COMMAND_REGISTRY.items()
    ]

_db = None
load_db()
if _db is None:
    _db = CodeDatabase()
    save_db()


# --- Register public API functions in the command registry ---
@register_command()
def add_function(name: str, description: str, code: str, modules: Optional[List[str]] = None, tags: Optional[List[str]] = None) -> str:
    """Add a new function to the database."""
    func = _db.add_function(name, description, code, modules, tags)
    save_db()
    return func.function_id

@register_command()
def add_function_to_module(function_id: str, module_name: str):
    """Add a function to a module."""
    _db.add_function_to_module(function_id, module_name)
    save_db()

@register_command()
def add_dependency(function_id: str, depends_on_id: str):
    """Add a dependency from one function to another."""
    result = _db.add_dependency(function_id, depends_on_id)
    save_db()
    return result


@register_command()
def remove_dependency(function_id: str, depends_on_id: str):
    """Remove a dependency from one function to another."""
    result = _db.remove_dependency(function_id, depends_on_id)
    save_db()
    return result


@register_command()
def find_cycles():
    """Return list of dependency cycles detected in the DB."""
    return _db.find_cycles()


@register_command()
def detect_recursion(function_id: str):
    """Heuristic detection of direct/mutual recursion for a specific function."""
    return _db.detect_recursion_in_function(function_id)

@register_command()
def add_tag(function_id: str, tag: str):
    """Add a tag to a function."""
    _db.add_tag(function_id, tag)
    save_db()

@register_command()
def list_tags():
    """List all tags in the database."""
    return _db.list_tags()

@register_command()
def list_functions_by_tag(tag: str):
    """List all functions with a given tag."""
    return _db.list_functions_by_tag(tag)

@register_command()
def list_dependencies(function_id: str):
    """List all dependencies for a function."""
    return _db.list_dependencies(function_id)

@register_command()
def visualize_dependencies(filepath: str):
    """Write a DOT/Graphviz file visualizing function dependencies."""
    _db.visualize_dependencies(filepath)

@register_command()
def list_modules():
    """List all modules in the database."""
    return _db.list_modules()

@register_command()
def list_functions(module: Optional[str] = None, tag: Optional[str] = None):
    """List all functions, optionally filtered by module or tag."""
    return _db.list_functions(module, tag)

@register_command()
def get_function(function_id: str):
    """Get details of a function by ID."""
    func = _db.functions.get(function_id)
    if not func:
        return None
    if not hasattr(func, "tags") or func.tags is None:
        func.tags = []
    return {
        "id": func.function_id,
        "name": func.name,
        "description": func.description,
        "code": func.code_snippet,
        "modules": func.modules,
        "tags": func.tags
    }

@register_command()
def modify_function(function_id: str, modifier: str, description: str, code: str):
    """Modify the code of an existing function."""
    _db.modify_function(function_id, modifier, description, code)
    save_db()

    # Print updated test and coverage report after code change
    try:
        print_test_and_coverage_report(_db)
    except Exception as e:
        print(f"[WARN] Could not print test/coverage report: {e}")

@register_command()
def add_test(function_id: str, name: str, description: str, test_code: str) -> str:
    """Add a unit test to a function."""
    print(f"[DEBUG] add_test called with function_id={function_id}")
    test = _db.add_unit_test(function_id, name, description, test_code)
    if test is None:
        print(f"[DEBUG] add_test: Function ID {function_id} not found.")
        raise ValueError(f"Function ID {function_id} not found.")
    print(f"[DEBUG] add_test: Test {test.test_id} added to function {function_id}")
    save_db()
    # Print updated test and coverage report after adding a test
    try:
        print_test_and_coverage_report(_db)
    except Exception as e:
        print(f"[WARN] Could not print test/coverage report: {e}")
    return test.test_id

@register_command()
def run_tests(function_id: str = None):
    """Run all unit tests, or tests for a specific function."""
    print(f"[DEBUG] run_tests called with function_id={function_id}")
    if function_id:
        func = _db.functions.get(function_id)
        if func:
            print(f"[DEBUG] run_tests: Function {function_id} has {len(func.unit_tests)} tests.")
        else:
            print(f"[DEBUG] run_tests: Function {function_id} not found.")
    else:
        print(f"[DEBUG] run_tests: Running tests for all functions.")
    results = _db.execute_tests(function_id)
    print(f"[DEBUG] run_tests: {len(results)} results generated.")
    save_db()
    # If results are error dicts, propagate as-is
    formatted = []
    for r in results:
        try:
            # If it's a structured error dict, propagate as-is
            if isinstance(r, dict) and ("error_type" in r or "success" in r):
                # Ensure all keys are serializable
                formatted.append({str(k): v for k, v in r.items()})
            # If it's a TestResult or similar, format as dict
            elif hasattr(r, 'test_id'):
                output = getattr(r, 'actual_result', None)
                # If output is a dict, ensure all keys are strings
                if isinstance(output, dict):
                    output = {str(k): v for k, v in output.items()}
                formatted.append({
                    "test_id": getattr(r, 'test_id', None),
                    "status": getattr(r, 'status', None).value if hasattr(r, 'status') else None,
                    "output": output
                })
            else:
                # Fallback: string representation
                formatted.append({"output": str(r)})
        except Exception as e:
            # If any entry is malformed, skip and log as error result
            formatted.append({
                "success": False,
                "error_type": "malformed_test_result",
                "message": f"Malformed test result entry: {str(e)}",
                "suggested_action": "Purge or repair legacy test results in the database."
            })
    return formatted

@register_command()
def get_test_results(function_id: str = None):
    """Get the last test results for all or a specific function."""
    print(f"[DEBUG] get_test_results called with function_id={function_id}")
    print(f"[DEBUG] get_test_results: _db.test_results has {len(_db.test_results)} results total.")
    results = []
    for result in _db.test_results:
        print(f"[DEBUG] get_test_results: result.function_id={result.function_id}, status={result.status.value}")
        if function_id is None or result.function_id == function_id:
            results.append({
                "test_id": result.test_id,
                "status": result.status.value,
                "output": result.actual_result
            })
    print(f"[DEBUG] get_test_results: returning {len(results)} results for function_id={function_id}")
    return results

@register_command()
def list_modifications(function_id: str):
    """List all modifications for a function."""
    return [
        {
            "id": mod.modification_id,
            "modifier": mod.modifier,
            "description": mod.description
        }
        for mod in _db.modifications
        if mod.function_id == function_id
    ]

@register_command()
def purge_tests(function_id: str):
    """Remove all unit tests and test results for a function."""
    func = _db.functions.get(function_id)
    if not func:
        print(f"[DEBUG] purge_tests: Function ID {function_id} not found.")
        return
    num_tests = len(func.unit_tests)
    func.unit_tests.clear()
    before = len(_db.test_results)
    _db.test_results = [r for r in _db.test_results if r.function_id != function_id]
    after = len(_db.test_results)
    print(f"[DEBUG] purge_tests: Removed {num_tests} unit tests and {before - after} test results for function {function_id}.")
    save_db()
    # Print updated test and coverage report after purging tests
    try:
        print_test_and_coverage_report(_db)
    except Exception as e:
        print(f"[WARN] Could not print test/coverage report: {e}")

# Register the command listing function itself
@register_command()
def list_commands_command():
    """List all available commands and their docstrings."""
    return list_commands()


# --- Automated Documentation Generator ---
@register_command()
def generate_function_doc_command(function_id: str, format: str = 'markdown'):
    """
    Generate comprehensive documentation for a function, including code, docstring, tags, modules, tests, test results, and modification history.
    Args:
        function_id (str): The function's unique ID.
        format (str): 'markdown' (default) or 'json'.
    Returns:
        dict: {'doc': <documentation string or object>}
    """
    func = _db.functions.get(function_id)
    if not func:
        return {'doc': f"Function ID {function_id} not found."}

    # Extract docstring from code if present
    from src.autocode.julia_parsers import extract_julia_docstring
    code_lines = func.code_snippet.splitlines()
    docstring = None
    if code_lines:
        docstring, _ = extract_julia_docstring(code_lines, 0)
    if not docstring:
        docstring = func.description or "Not available."

    # Gather test cases and results
    tests = []
    for test in getattr(func, 'unit_tests', []):
        # Find latest result for this test
        latest_result = None
        for r in reversed(_db.test_results):
            if r.test_id == test.test_id:
                latest_result = r
                break
        tests.append({
            'name': test.name,
            'description': test.description,
            'test_code': test.test_case,
            'last_result': {
                'status': latest_result.status.value if latest_result else 'Not run',
                'output': latest_result.actual_result if latest_result else ''
            } if latest_result else None
        })

    # Gather modification history
    modifications = [
        {
            'modifier': mod.modifier,
            'description': mod.description,
            'date': getattr(mod, 'modification_date', None)
        }
        for mod in getattr(_db, 'modifications', [])
        if getattr(mod, 'function_id', None) == function_id
    ]

    # Compose documentation
    doc_md = f"""# Function: {func.name}\n\n"""
    doc_md += f"**ID:** `{func.function_id}`\n\n"
    doc_md += f"**Description:** {func.description}\n\n"
    doc_md += f"**Modules:** {', '.join(func.modules) if func.modules else 'None'}\n\n"
    doc_md += f"**Tags:** {', '.join(func.tags) if func.tags else 'None'}\n\n"
    doc_md += f"**Signature:** {func.signature if func.signature else 'Not available'}\n\n"
    doc_md += f"## Docstring\n\n{docstring}\n\n"
    doc_md += f"## Code\n\n```julia\n{func.code_snippet}\n```\n\n"
    doc_md += f"## Unit Tests\n\n"
    if tests:
        for t in tests:
            doc_md += f"### {t['name']}\n- Description: {t['description']}\n- Code:\n```julia\n{t['test_code']}\n```\n- Last Result: {t['last_result']['status']}\n  - Output: {t['last_result']['output']}\n\n"
    else:
        doc_md += "No unit tests available.\n\n"
    doc_md += f"## Modification History\n\n"
    if modifications:
        for m in modifications:
            doc_md += f"- {m['date']}: {m['modifier']} — {m['description']}\n"
    else:
        doc_md += "No modifications recorded.\n"

    if format == 'json':
        return {
            'doc': {
                'id': func.function_id,
                'name': func.name,
                'description': func.description,
                'modules': func.modules,
                'tags': func.tags,
                'signature': func.signature,
                'docstring': docstring,
                'code': func.code_snippet,
                'unit_tests': tests,
                'modifications': modifications
            }
        }
    else:
        return {'doc': doc_md}

def test_function():
    code_db = CodeDatabase()
    print(code_db)

    description = "calculate the factorial of a non-negative integer"
    print(f"Generating Julia function for: {description}")
    generated_code_message = generate_julia_function(description)
    generated_code = generated_code_message.parsed

    func = code_db.add_function(generated_code.function_name, generated_code.short_description, generated_code.code)
    
    code_db.add_unit_test(func.function_id, generated_code.test_name, generated_code.test_description, generated_code.tests)
    
    max_attempts = 5
    attempt = 0
    while attempt < max_attempts:
        print(f"\nAttempt {attempt + 1} of {max_attempts}")
        
        print("Executing Tests...")
        results = code_db.execute_tests()
        
        failed_tests = [r for r in results if r.status == TestStatusEnum.FAILED]
        
        if not failed_tests:
            print("All tests passed!")
            break
            
        print(f"Failed tests: {len(failed_tests)}")
        for result in failed_tests:
            print(f"Test {result.test_id} failed: {result.actual_result}")
        
        fix_description = f"Fix the function. Current tests failed with: {[r.actual_result for r in failed_tests]}"
        print(f"\nRequesting fix: {fix_description}")
        fixed_code_message = modify_julia_function(fix_description)
        fixed_code = fixed_code_message.parsed.code
        
        code_db.modify_function(func.function_id, "AI", f"Fix attempt {attempt + 1}", fixed_code)
        
        attempt += 1
    
    if attempt == max_attempts:
        print("\nMaximum fix attempts reached without success")
    else:
        print(f"\nFixed in {attempt + 1} attempts")