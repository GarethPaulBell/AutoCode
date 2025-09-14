"""
Model Context Protocol (MCP) server exposing AutoCode code_db operations as tools.

Implements a minimal subset of the MCP spec (tools/list, tools/call, initialize, shutdown, ping)
over JSON-RPC 2.0 via stdio so that an MCP-compatible client can discover and invoke
code manipulation and test generation functions.

Run (PowerShell):
  python .\mcp_autocode_server.py

Then configure your MCP client to launch this command as a server.

NOTE: This is a lightweight implementation without advanced features
(streaming, cancellation, session persistence beyond code_db, structured logs).
"""
from __future__ import annotations

import sys
import json
import traceback
import threading
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Callable, Optional

# Ensure repository root is on sys.path so local top-level modules (e.g., code_db) can be imported
# This makes the script runnable directly without requiring the user to set PYTHONPATH.
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

import code_db  # Reuse existing database and generation functions
from . import julia_linter

JSONRPC = "2.0"

def _write(obj: dict):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _error_response(id_, code: int, message: str, data: Any = None):
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": JSONRPC, "id": id_, "error": err}


def _success(id_, result: Any):
    return {"jsonrpc": JSONRPC, "id": id_, "result": result}


def _structured_success(result: Any, **metadata) -> dict:
    """Create a structured success response."""
    return {
        "ok": True,
        "result": result,
        **metadata
    }


def _structured_error(error_type: str, message: str, suggested_action: str = None, details: Any = None) -> dict:
    """Create a structured error response."""
    error = {
        "type": error_type,
        "message": message
    }
    if suggested_action:
        error["suggested_action"] = suggested_action
    if details:
        error["details"] = details
    return {
        "ok": False,
        "error": error
    }


def _convert_to_serializable(obj: Any) -> Any:
    """Convert common non-serializable objects (pydantic models, dataclasses, tuples) into JSON-serializable types."""
    try:
        # pydantic v2
        if hasattr(obj, 'model_dump'):
            return obj.model_dump()
        # pydantic v1
        if hasattr(obj, 'dict') and callable(getattr(obj, 'dict')):
            return obj.dict()
        if isinstance(obj, dict):
            return {str(k): _convert_to_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple, set)):
            return [_convert_to_serializable(v) for v in obj]
        # materialize generators/iterators (but not strings/bytes)
        if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, dict, list, tuple, set)):
            try:
                return [_convert_to_serializable(v) for v in obj]
            except TypeError:
                # not actually iterable (e.g., int), fallthrough
                pass
        # dataclass-like
        if hasattr(obj, '__dict__'):
            try:
                return {k: _convert_to_serializable(v) for k, v in obj.__dict__.items()}
            except Exception:
                pass
        # fallback for simple scalars
        return obj
    except Exception:
        return str(obj)


class Tool:
    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict,
        handler: Callable[[dict], Any],
        streaming: bool = False,
        stream_handler: Optional[Callable[[int, dict, 'AutoCodeMCPServer'], None]] = None,
    ):
        """Represents a callable MCP tool.

        streaming: marks if tool supports streaming when caller sets params.stream=true
        stream_handler: function spawning streaming work (receives original request id)
        """
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler
        self.streaming = streaming
        self.stream_handler = stream_handler


class AutoCodeMCPServer:
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.shutdown_flag = False
        self.active_streams: Dict[int, Dict[str, Any]] = {}  # callId -> {cancel: bool, started: ts}
        # Logging setup
        self.log_path = os.environ.get("MCP_AUTOCODE_LOG", "autocode_mcp.log")
        self._log_lock = threading.Lock()
        # Register tools after initial state is configured
        self._register_tools()
        self.log("server_start", {"pid": os.getpid(), "log_path": self.log_path})

    # ---------------- Tool registration -----------------
    def _register(self, tool: Tool):
        self.tools[tool.name] = tool

    def _register_tools(self):

        self._register(Tool(
            "generate_function_doc",
            "Generate comprehensive documentation for a function, including code, docstring, tags, modules, tests, test results, and modification history.",
            {
                "type": "object",
                "properties": {
                    "function_id": {"type": "string", "description": "The function's unique ID."},
                    "format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown", "description": "Output format: 'markdown' or 'json' (default: markdown)."}
                },
                "required": ["function_id"]
            },
            lambda a: (lambda result: _structured_success(result, function_id=a["function_id"], format=a.get("format", "markdown")) if not isinstance(result["doc"], str) or not result["doc"].startswith("Function ID") else _structured_error("FunctionNotFound", result["doc"], "Check the function ID or create the function first"))(code_db.generate_function_doc_command(a["function_id"], a.get("format", "markdown")))
        ))
        self._register(Tool(
            "list_functions",
            "List functions (optionally filtered by module or tag).",
            {
                "type": "object",
                "properties": {
                    "module": {"type": ["string", "null"], "description": "Module name filter"},
                    "tag": {"type": ["string", "null"], "description": "Tag filter"}
                },
                "required": []
            },
            lambda args: _structured_success(code_db.list_functions(module=args.get("module"), tag=args.get("tag")), count=len(code_db.list_functions(module=args.get("module"), tag=args.get("tag"))))
        ))

        # Expose the code_db command registry as a tool
        self._register(Tool(
            "list_code_db_commands",
            "List all available code_db command registry entries and their docstrings.",
            {"type": "object", "properties": {}, "required": []},
            lambda args: _structured_success({"commands": code_db.list_commands_command()}, command_count=len(code_db.list_commands_command()))
        ))

        self._register(Tool(
            "delete_function",
            "Delete a function by ID, cleaning up all associated data (unit tests, tags, dependencies, modules).",
            {"type": "object", "properties": {"function_id": {"type": "string"}}, "required": ["function_id"]},
            lambda a: _structured_success({"deleted": True}, function_id=a["function_id"]) if code_db._db.delete_function(a["function_id"]) else _structured_error("FunctionNotFound", f"Function {a['function_id']} not found", "Check the function ID")
        ))

        self._register(Tool(
            "get_function",
            "Get full details of a function by ID.",
            {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
            lambda args: _structured_success(code_db.get_function(args["id"])) if code_db.get_function(args["id"]) else _structured_error("FunctionNotFound", f"Function {args['id']} not found", "Check the function ID or create the function first")
        ))

        self._register(Tool(
            "generate_function",
            "Generate a new Julia function from a natural language description and add it to the DB. (Supports streaming)",
            {"type": "object", "properties": {"description": {"type": "string"}, "module": {"type": ["string", "null"]}}, "required": ["description"]},
            self._tool_generate_function,
            streaming=True,
            stream_handler=self._stream_generate_function
        ))

        self._register(Tool(
            "add_function",
            "Add a function with provided name, description, and code.",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "code": {"type": "string"},
                    "modules": {"type": ["array", "null"], "items": {"type": "string"}},
                    "tags": {"type": ["array", "null"], "items": {"type": "string"}}
                },
                "required": ["name", "description", "code"]
            },
            lambda a: (lambda fid: _structured_success({"function_id": fid}, function_id=fid))(code_db.add_function(a["name"], a["description"], a["code"], a.get("modules"), a.get("tags")))
        ))

        self._register(Tool(
            "modify_function",
            "Modify the code for an existing function (overwrites code).",
            {"type": "object", "properties": {"id": {"type": "string"}, "modifier": {"type": "string"}, "description": {"type": "string"}, "code": {"type": "string"}}, "required": ["id", "modifier", "description", "code"]},
            lambda a: _structured_success({"status": "modified"}, function_id=a["id"]) if (code_db.get_function(a["id"]) and (code_db.modify_function(a["id"], a["modifier"], a["description"], a["code"]) or True)) else _structured_error("FunctionNotFound", f"Function {a['id']} not found", "Check the function ID or create the function first")
        ))

        self._register(Tool(
            "generate_test",
            "Generate a test for a function name and attach it.",
            {"type": "object", "properties": {"function_id": {"type": "string"}, "name": {"type": "string"}, "description": {"type": "string"}}, "required": ["function_id", "name", "description"]},
            self._tool_generate_test
        ))

        self._register(Tool(
            "mcp_autocode_run_tests",
            "Run tests for a function, module, or all. (Supports streaming)",
            {"type": "object", "properties": {"function_id": {"type": ["string", "null"]}, "module": {"type": ["string", "null"]}, "project_toml_path": {"type": ["string", "null"], "description": "Path to Project.toml file to include package dependencies"}}, "required": []},
            self._tool_run_tests,
            streaming=True,
            stream_handler=self._stream_run_tests
        ))

        self._register(Tool(
            "search_functions",
            "Keyword search across name, description, code.",
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            lambda a: _structured_success(code_db.search_functions(a["query"]), query=a["query"], result_count=len(code_db.search_functions(a["query"])))  # type: ignore[arg-type]
        ))

        self._register(Tool(
            "semantic_search",
            "Semantic search for similar functions.",
            {"type": "object", "properties": {"query": {"type": "string"}, "top_k": {"type": "integer", "default": 5}}, "required": ["query"]},
            lambda a: _structured_success(code_db.semantic_search_functions(a["query"], top_k=a.get("top_k", 5)), query=a["query"], top_k=a.get("top_k", 5))
        ))

        self._register(Tool(
            "export_function",
            "Export a function (with tests) to JSON file.",
            {"type": "object", "properties": {"function_id": {"type": "string"}, "file": {"type": "string"}}, "required": ["function_id", "file"]},
            lambda a: (lambda result: _structured_success(result, **result) if result.get("success") else _structured_error(result.get("error_type", "UnknownError"), result.get("message", "Export failed"), result.get("suggested_action"), result))(code_db.export_function(a["function_id"], a["file"]))
        ))

        self._register(Tool(
            "import_function",
            "Import a function (with tests) from JSON file.",
            {"type": "object", "properties": {"file": {"type": "string"}}, "required": ["file"]},
            lambda a: (lambda result: _structured_success(result, **result) if result.get("success") else _structured_error(result.get("error_type", "UnknownError"), result.get("message", "Import failed"), result.get("suggested_action"), result))(code_db.import_function(a["file"]))
        ))

        self._register(Tool(
            "coverage_report",
            "Get coverage (tests passed/failed) for all functions.",
            {"type": "object", "properties": {}, "required": []},
            lambda a: _structured_success(code_db.get_coverage_report(), function_count=len(code_db.get_coverage_report().get("functions", [])))
        ))

        # Optional extra tools (non-streaming for now)
        if hasattr(code_db, "benchmark_function"):
            self._register(Tool(
                "benchmark_function",
                "Run benchmark for a function with a Julia input file.",
                {"type": "object", "properties": {"function_id": {"type": "string"}, "input_file": {"type": "string"}, "iterations": {"type": "integer", "default": 1}}, "required": ["function_id", "input_file"]},
                lambda a: code_db.benchmark_function(a["function_id"], a["input_file"], a.get("iterations", 1))
            ))
        if hasattr(code_db, "property_test_function"):
            self._register(Tool(
                "property_test",
                "Run property-based tests for a function. (Supports streaming)",
                {"type": "object", "properties": {"function_id": {"type": "string"}, "num_tests": {"type": "integer", "default": 50}, "seed": {"type": "integer", "default": 42}}, "required": ["function_id"]},
                lambda a: code_db.property_test_function(a["function_id"], a.get("num_tests", 50), a.get("seed", 42)),
                streaming=True,
                stream_handler=self._stream_property_test
            ))

        # Dependency related tools
        if hasattr(code_db, "list_dependencies"):
            self._register(Tool(
                "list_dependencies",
                "List dependencies for a function.",
                {"type": "object", "properties": {"function_id": "string"}, "required": ["function_id"]},
                lambda a: _structured_success({"dependencies": code_db.list_dependencies(a["function_id"])}, function_id=a["function_id"], dependency_count=len(code_db.list_dependencies(a["function_id"])))
            ))
        if hasattr(code_db, "remove_dependency"):
            self._register(Tool(
                "remove_dependency",
                "Remove a dependency between two functions.",
                {"type": "object", "properties": {"function_id": {"type": "string"}, "depends_on_id": {"type": "string"}}, "required": ["function_id", "depends_on_id"]},
                lambda a: (lambda result: _structured_success(result, **result) if result.get("success") else _structured_error(result.get("error_type", "UnknownError"), result.get("message", "Remove dependency failed"), result.get("suggested_action"), result))(code_db.remove_dependency(a["function_id"], a["depends_on_id"]))
            ))
        if hasattr(code_db, "find_cycles"):
            self._register(Tool(
                "find_cycles",
                "Detect and return dependency cycles in the DB.",
                {"type": "object", "properties": {}, "required": []},
                lambda a: _structured_success({"cycles": code_db.find_cycles()}, cycle_count=len(code_db.find_cycles()))
            ))
        if hasattr(code_db, "detect_recursion"):
            self._register(Tool(
                "detect_recursion",
                "Detect direct or mutual recursion for a function.",
                {"type": "object", "properties": {"function_id": {"type": "string"}}, "required": ["function_id"]},
                lambda a: _structured_success(code_db.detect_recursion(a["function_id"]), function_id=a["function_id"])
            ))
        if hasattr(code_db, "visualize_dependencies"):
            self._register(Tool(
                "visualize_dependencies",
                "Write a DOT file showing dependencies (and optionally return its content).",
                {"type": "object", "properties": {"file": {"type": "string"}, "return_content": {"type": "boolean", "default": False}}, "required": ["file"]},
                self._tool_visualize_dependencies
            ))

    # ---------------- Tool handlers needing logic -----------------
    def _tool_generate_function(self, args: dict):
        desc = args["description"]
        module = args.get("module")
        try:
            result = code_db.generate_julia_function(desc)
            parsed = result.parsed

            # Lint the generated code for compatibility issues
            lint_result = julia_linter.lint_julia_code(parsed.code, fix=True)

            # If linting found errors and we're configured to block unsafe code, reject the function
            if not lint_result.success:
                error_messages = [issue.message for issue in lint_result.issues if issue.severity == 'error']
                return _structured_error(
                    "LintingFailed",
                    f"Generated function contains compatibility errors: {', '.join(error_messages)}",
                    "The generated code has compatibility issues that cannot be automatically fixed. Try a different description or check the linting configuration.",
                    {
                        "description": desc,
                        "lint_issues": [{"type": i.type, "message": i.message, "severity": i.severity} for i in lint_result.issues]
                    }
                )

            # Use fixed code if available, otherwise use original
            final_code = lint_result.fixed_code if lint_result.fixed_code else parsed.code

            # If fixes were applied, update the parsed result
            if lint_result.fixed_code:
                # Re-parse the fixed code to update function name and other metadata if needed
                # For now, we'll assume the fixes don't change the function signature significantly
                parsed.code = final_code

            modules = [module] if module else None
            fid = code_db.add_function(parsed.function_name, parsed.short_description, final_code, modules)

            response_data = {
                "function_id": fid,
                "name": parsed.function_name,
                "short_description": parsed.short_description,
                "code": final_code,
                "test": parsed.tests,
                "modules": modules or []
            }

            # Include linting information if there were warnings or fixes applied
            if lint_result.issues:
                response_data["lint_warnings"] = [
                    {"type": i.type, "message": i.message, "severity": i.severity}
                    for i in lint_result.issues if i.severity == 'warning'
                ]
                if lint_result.fixed_code:
                    response_data["lint_fixes_applied"] = True

            return _structured_success(response_data, function_id=fid)

        except Exception as e:
            return _structured_error("GenerationFailed", f"Failed to generate function: {str(e)}", "Check the description or try a simpler one", {"description": desc})

    def _tool_generate_test(self, args: dict):
        fid = args["function_id"]
        func = code_db.get_function(fid)
        if not func:
            return _structured_error("FunctionNotFound", f"Function {fid} not found", "Check the function ID or create the function first")

        # Attempt to provide signature/docstring to the test generator. If missing, try to parse from code.
        try:
            signature = func.get("signature") if isinstance(func, dict) else getattr(func, "signature", None)
            docstring = func.get("docstring") if isinstance(func, dict) else getattr(func, "docstring", None)
            function_code = func.get("code") if isinstance(func, dict) else getattr(func, "code_snippet", None)
            function_name = func.get("name") if isinstance(func, dict) else getattr(func, "name", None)
        except Exception:
            signature = docstring = function_code = function_name = None

        # If write_test_case expects (function_code, signature, docstring, function_name)
        # and code_db.write_test_case is available, call it defensively.
        if not (hasattr(code_db, "write_test_case") and code_db.write_test_case is not None):
            return _structured_error("NotAvailable", "Test generation not available on this server", "Install/configure the LLM client or enable test generation in this server")

        try:
            # Ensure required pieces are present; try to extract using julia_parsers as fallback
            if not signature or not docstring:
                try:
                    from src.autocode.julia_parsers import parse_julia_function, extract_julia_docstring
                    if function_code:
                        parsed = parse_julia_function(function_code)
                        signature = signature or (parsed.get("declaration") if parsed else "")
                        ds, _ = extract_julia_docstring(function_code.splitlines(), 0)
                        docstring = docstring or ds
                except Exception:
                    # Leave signature/docstring as-is; the underlying generator should handle or error clearly
                    pass
            try:
                test_code = code_db.write_test_case(function_code or "", signature or "", docstring or "", function_name or "")
            except TypeError as e:
                # Fallback: maybe write_test_case has a simpler signature (function_name only)
                try:
                    test_code = code_db.write_test_case(function_name or "")
                except Exception as e2:
                    # As a last-resort, generate a minimal stub test so the flow remains usable
                    test_code = (
                        f"using Test\n@testset \"auto_generated_{function_name or 'unknown'}\" begin\n"
                        "    # stub test generated due to generator error\n"
                        "    @test true\nend\n"
                    )
                    # Return structured response including the original exception
                    return _structured_error("GeneratorError", f"Test generation failed: {str(e)}", "Try with more function context or check LLM configuration", {"fallback_stub_generated": True, "stub_code": test_code})
            except Exception as e:
                # General failure: provide stub test and structured error details
                test_code = (
                    f"using Test\n@testset \"auto_generated_{function_name or 'unknown'}\" begin\n"
                    "    # stub test generated due to generator failure\n"
                    "    @test true\nend\n"
                )
                return _structured_error("GeneratorFailure", f"Test generation failed: {str(e)}", "Check LLM configuration or try manual test creation", {"fallback_stub_generated": True, "stub_code": test_code})

            # Attempt to attach the test and return structured success
            try:
                test_id = code_db.add_test(fid, args.get("name", f"auto_generated_{function_name or 'test'}"), args.get("description", "Auto-generated test"), test_code)
                return _structured_success({"test_id": test_id, "code": test_code}, test_id=test_id, function_id=fid)
            except Exception as e:
                # If attaching the test fails, return the code plus error metadata
                return _structured_error("AttachTestFailed", f"Generated test but failed to attach: {str(e)}", "Check function exists and try again", {"generated_code": test_code})
        except Exception as e:
            # Catch-all to ensure structured response on unexpected failures
            test_code = (
                f"using Test\n@testset \"auto_generated_{function_name or 'unknown'}\" begin\n"
                "    # stub test generated due to unexpected server error\n"
                "    @test true\nend\n"
            )
            return _structured_error("UnexpectedError", f"Unexpected error during test generation: {str(e)}", "Report this issue or try again", {"fallback_stub_generated": True, "stub_code": test_code})

    def _tool_run_tests(self, args: dict):
        """Non-streaming wrapper that calls code_db.run_tests and returns JSON-serializable results.
        The streaming path remains implemented in _stream_run_tests.
        """
        try:
            fid = args.get("function_id")
            module = args.get("module")
            project_toml_path = args.get("project_toml_path")
            
            # Parse dependencies from Project.toml if provided
            dependencies = []
            if project_toml_path:
                try:
                    from .persistence import parse_project_toml
                    project_root = Path(project_toml_path).parent if project_toml_path else None
                    parsed = parse_project_toml(project_root)
                    dependencies = parsed.get("deps", [])
                except Exception as e:
                    print(f"Warning: Could not parse Project.toml: {e}")
            
            # If module is specified, we need to filter functions by module
            if module:
                # Get all functions in the specified module
                all_funcs = code_db.list_functions(module=module)
                if not all_funcs:
                    return _structured_error("NoFunctionsFound", f"No functions found in module '{module}'", "Check the module name or add functions to this module")
                func_ids = [f['id'] for f in all_funcs]
                # Run tests for all functions in the module
                maybe_results = []
                for func_id in func_ids:
                    results = code_db.run_tests(func_id, dependencies=dependencies)
                    maybe_results.extend(results)
            else:
                maybe_results = code_db.run_tests(fid, dependencies=dependencies) if fid else code_db.run_tests(dependencies=dependencies)

            # If the code_db returns a generator (streaming), exhaust it and collect textual lines
            results_list = []
            try:
                if hasattr(maybe_results, '__iter__') and not isinstance(maybe_results, (list, tuple)):
                    # it's an iterator/generator - consume it
                    for item in maybe_results:
                        # try to convert common container types
                        results_list.append(_convert_to_serializable(item))
                else:
                    results_list = _convert_to_serializable(maybe_results)
            except TypeError:
                # Not iterable - attempt to serialize directly
                results_list = _convert_to_serializable(maybe_results)

            return _structured_success({"results": results_list}, test_count=len(results_list) if isinstance(results_list, list) else 1)
        except Exception as e:
            tb = traceback.format_exc()
            return _structured_error("TestExecutionFailed", f"Failed to run tests: {str(e)}", "Check function exists and Julia environment is properly configured", {"traceback": tb})

    # ---------------- Streaming handlers -----------------
    def _stream_generate_function(self, call_id: int, args: dict, server: 'AutoCodeMCPServer'):
        desc = args["description"]
        module = args.get("module")
        # Emit progress
        self._emit_stream(call_id, "chunk", {"progress": 0.05, "message": "requesting model"})
        try:
            result = code_db.generate_julia_function(desc)
        except Exception as e:
            self._emit_stream(call_id, "error", {"error": str(e)})
            return
        parsed = result.parsed
        code_lines = parsed.code.splitlines()
        total = len(code_lines)
        for i, line in enumerate(code_lines, 1):
            if self._is_cancelled(call_id):
                self._emit_stream(call_id, "cancelled", {"at": i})
                return
            self._emit_stream(call_id, "chunk", {"type": "code_line", "line_no": i, "line": line, "progress": 0.1 + 0.6 * (i/total)})
            time.sleep(0.005)  # tiny delay to show streaming
        modules = [module] if module else None
        fid = code_db.add_function(parsed.function_name, parsed.short_description, parsed.code, modules)
        self._emit_stream(call_id, "chunk", {"progress": 0.9, "message": "function stored", "function_id": fid})
        self._emit_stream(call_id, "complete", {
            "function_id": fid,
            "name": parsed.function_name,
            "short_description": parsed.short_description,
            "code": parsed.code,
            "test": parsed.tests,
            "modules": modules or []
        })

    def _stream_run_tests(self, call_id: int, args: dict, server: 'AutoCodeMCPServer'):
        target_fid = args.get("function_id")
        target_module = args.get("module")
        project_toml_path = args.get("project_toml_path")
        
        # Parse dependencies from Project.toml if provided
        dependencies = []
        if project_toml_path:
            try:
                from .persistence import parse_project_toml
                project_root = Path(project_toml_path).parent if project_toml_path else None
                parsed = parse_project_toml(project_root)
                dependencies = parsed.get("deps", [])
            except Exception as e:
                print(f"Warning: Could not parse Project.toml: {e}")
        
        try:
            # Build list of (function, tests)
            all_funcs = []
            if target_module:
                # Get all functions in the specified module
                module_funcs = code_db.list_functions(module=target_module)
                if not module_funcs:
                    self._emit_stream(call_id, "complete", {"results": [], "message": f"no functions in module '{target_module}'"})
                    return
                for f_data in module_funcs:
                    f_obj = code_db._db.functions.get(f_data['function_id'])
                    if f_obj:
                        all_funcs.append(f_obj)
            elif target_fid:
                f_obj = code_db._db.functions.get(target_fid)  # type: ignore[attr-defined]
                if f_obj:
                    all_funcs.append(f_obj)
            else:
                all_funcs = list(code_db._db.functions.values())  # type: ignore[attr-defined]
            
            total_tests = sum(len(f.unit_tests) for f in all_funcs)
            if total_tests == 0:
                self._emit_stream(call_id, "complete", {"results": [], "message": "no tests"})
                return
            done = 0
            aggregated = []
            # Clear old results for streamed functions (optional)
            if target_fid:
                code_db._db.test_results = [r for r in code_db._db.test_results if r.function_id != target_fid]  # type: ignore[attr-defined]
            elif target_module:
                # Clear results for all functions in the module
                module_func_ids = {f.function_id for f in all_funcs}
                code_db._db.test_results = [r for r in code_db._db.test_results if r.function_id not in module_func_ids]  # type: ignore[attr-defined]
            else:
                func_ids = {f.function_id for f in all_funcs}
                code_db._db.test_results = [r for r in code_db._db.test_results if r.function_id not in func_ids]  # type: ignore[attr-defined]
            
            for func in all_funcs:
                for ut in func.unit_tests:
                    if self._is_cancelled(call_id):
                        self._emit_stream(call_id, "cancelled", {"completed": done, "total": total_tests})
                        return
                    res = ut.run_test(func.code_snippet, dependencies)
                    code_db._db.test_results.append(res)  # type: ignore[attr-defined]
                    chunk = {"test_id": res.test_id, "function_id": res.function_id, "status": res.status.value, "output": res.actual_result}
                    aggregated.append(chunk)
                    done += 1
                    self._emit_stream(call_id, "chunk", {"index": done, "total": total_tests, "result": chunk, "progress": done/total_tests})
                    code_db.save_db()  # persist incrementally
            self._emit_stream(call_id, "complete", {"results": aggregated, "total": total_tests})
        except Exception as e:
            self._emit_stream(call_id, "error", {"error": str(e)})

    def _stream_property_test(self, call_id: int, args: dict, server: 'AutoCodeMCPServer'):
        try:
            fid = args["function_id"]
            num_tests = args.get("num_tests", 50)
            seed = args.get("seed", 42)
            # Run full property test (returns aggregated results)
            result = code_db.property_test_function(fid, num_tests=num_tests, seed=seed)
            if not result.get("success"):
                self._emit_stream(call_id, "error", {"stderr": result.get("stderr")})
                return
            results = result.get("results", [])
            total = len(results)
            for i, r in enumerate(results, 1):
                if self._is_cancelled(call_id):
                    self._emit_stream(call_id, "cancelled", {"completed": i-1, "total": total})
                    return
                self._emit_stream(call_id, "chunk", {"index": i, "total": total, "status": r.get("status"), "info": r.get("info"), "progress": i/total})
            self._emit_stream(call_id, "complete", {"total": total, "passes": sum(1 for r in results if r.get("status") == "pass"), "fails": sum(1 for r in results if r.get("status") == "fail")})
        except Exception as e:
            self._emit_stream(call_id, "error", {"error": str(e)})

    def _tool_visualize_dependencies(self, args: dict):
        file_path = args["file"]
        try:
            code_db.visualize_dependencies(file_path)
            out = {"file": file_path, "written": True}
            if args.get("return_content"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        out["content"] = f.read()
                except Exception as e:
                    out["content_error"] = str(e)
            return _structured_success(out, filepath=file_path)
        except Exception as e:
            return _structured_error("VisualizationFailed", f"Failed to visualize dependencies: {str(e)}", "Check file permissions and path", {"filepath": file_path})

    # ---------------- Stream helpers -----------------
    def _emit_stream(self, call_id: int, event: str, data: dict):
        payload = {
            "jsonrpc": JSONRPC,
            "method": "tools/stream",
            "params": {"callId": call_id, "event": event, "data": data}
        }
        _write(payload)
        self.log("stream_event", {"callId": call_id, "event": event, "data": data})

    def _is_cancelled(self, call_id: int) -> bool:
        meta = self.active_streams.get(call_id)
        return bool(meta and meta.get("cancel"))

    def _start_stream(self, rid: int, tool: Tool, arguments: dict):
        self.active_streams[rid] = {"cancel": False, "started": time.time(), "tool": tool.name}
        self.log("stream_start", {"callId": rid, "tool": tool.name, "arguments": arguments})
        def runner():
            try:
                tool.stream_handler(rid, arguments, self)  # type: ignore[arg-type]
            finally:
                # mark finished
                self.active_streams.pop(rid, None)
                self.log("stream_end", {"callId": rid, "tool": tool.name})
        t = threading.Thread(target=runner, daemon=True)
        t.start()

    # ---------------- JSON-RPC dispatch -----------------
    def handle_request(self, req: dict):
        rid = req.get("id")
        method = req.get("method")
        self.log("request", {"id": rid, "method": method, "raw": req})
        try:
            if method == "initialize":
                return _success(rid, {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "autocode-mcp", "version": "0.1.0"},
                    "capabilities": {"tools": {"listChanged": False}}
                })
            if method == "shutdown":
                self.shutdown_flag = True
                return _success(rid, {})
            if method == "ping":
                return _success(rid, {"pong": True})
            if method == "tools/list":
                tools_list = [
                    {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
                    for t in self.tools.values()
                ]
                return _success(rid, {"tools": tools_list})
            if method == "tools/call":
                params = req.get("params") or {}
                name = params.get("name")
                arguments = params.get("arguments") or {}
                stream_flag = bool(params.get("stream"))
                if name not in self.tools:
                    return _error_response(rid, -32601, f"Unknown tool '{name}'")
                tool = self.tools[name]
                required = tool.input_schema.get("required", [])
                for r in required:
                    if r not in arguments:
                        return _error_response(rid, -32602, f"Missing required argument '{r}'")
                if stream_flag:
                    if not tool.streaming or not tool.stream_handler:
                        return _error_response(rid, -32602, f"Tool '{name}' does not support streaming")
                    self._start_stream(rid, tool, arguments)
                    return _success(rid, {"streaming": True})
                result = tool.handler(arguments)
                self.log("tool_call", {"id": rid, "tool": name, "arguments": arguments, "result_summary_keys": list(result.keys()) if isinstance(result, dict) else None})
                return _success(rid, {"content": [{"type": "json", "json": result}]})
            if method == "tools/cancel":
                params = req.get("params") or {}
                call_id = params.get("callId")
                if call_id in self.active_streams:
                    self.active_streams[call_id]["cancel"] = True
                    self.log("stream_cancel", {"callId": call_id})
                    return _success(rid, {"cancelled": True, "callId": call_id})
                return _success(rid, {"cancelled": False, "reason": "not_found", "callId": call_id})
            return _error_response(rid, -32601, f"Unknown method '{method}'")
        except Exception as e:
            tb = traceback.format_exc()
            self.log("error", {"id": rid, "method": method, "error": str(e)})
            return _error_response(rid, -32000, f"Exception: {e}", data=tb)

    def serve(self):
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except Exception:
                _write(_error_response(None, -32700, "Parse error"))
                self.log("parse_error", {"line": line})
                continue
            if isinstance(req, list):  # batch
                responses = [self.handle_request(r) for r in req]
                _write(responses)
                self.log("batch", {"size": len(req)})
            else:
                resp = self.handle_request(req)
                if resp is not None:
                    _write(resp)
            if self.shutdown_flag:
                self.log("server_shutdown", {})
                break

    # ---------------- Logging utility -----------------
    def log(self, event: str, data: dict):
        try:
            record = {
                "ts": datetime.utcnow().isoformat()+"Z",
                "event": event,
                "data": data
            }
            line = json.dumps(record, ensure_ascii=False)
            with self._log_lock:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception:
            # Last resort: swallow logging errors to not break protocol
            pass


def main():
    server = AutoCodeMCPServer()
    server.serve()


if __name__ == "__main__":
    main()
