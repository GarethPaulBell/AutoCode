import subprocess
import tempfile
import os
import datetime
import uuid
import pickle
import json
import math
import re
from typing import Callable, Dict, List, Optional
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

    def execute_tests(self, function_id: str = None):
        results = []
        if function_id:
            funcs = [self.functions.get(function_id)] if function_id in self.functions else []
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
            for test in func.unit_tests:
                result = test.run_test(func.code_snippet)
                self.test_results.append(result)
                results.append(result)
                print(f"Test Result: {result}")
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
        func = self.functions.get(function_id)
        if not func:
            raise ValueError(f"Function ID {function_id} not found.")
        if depends_on_id not in self.functions:
            raise ValueError(f"Dependency function ID {depends_on_id} not found.")
        func.add_dependency(depends_on_id)
        self.last_modified_date = datetime.datetime.now()
        print(f"Added dependency: {function_id} depends on {depends_on_id}")

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
    func = _db.functions.get(function_id)
    if not func:
        raise ValueError(f"Function ID {function_id} not found.")
    if not hasattr(func, "modules") or func.modules is None:
        func.modules = []
    if not hasattr(func, "tags") or func.tags is None:
        func.tags = []
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
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Exported function {function_id} to {filepath}")

def import_function(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
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
    print(f"Imported function '{func.name}' with new ID: {func.function_id}")
    return func.function_id

def export_module(module_name: str, filepath: str):
    if module_name not in _db.modules:
        raise ValueError(f"Module '{module_name}' not found.")
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
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Exported module '{module_name}' to {filepath}")

def import_module(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    module_name = data["module_name"]
    _db.add_module(module_name)
    new_func_ids = []
    for func_data in data.get("functions", []):
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
    print(f"Imported module '{module_name}' with {len(new_func_ids)} functions.")
    return new_func_ids

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
                test_code = write_test_case(func_data['name'])
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

def _get_embedding(text):
    # You can replace this with your own embedding model or API
    if HAVE_OPENAI:
        # Detect OpenAI API version
        openai_version = getattr(openai, "__version__", "0.0.0")
        major_version = int(openai_version.split(".")[0])
        if major_version >= 1:
            # openai>=1.0.0
            # https://github.com/openai/openai-python/blob/main/README.md#embeddings
            resp = openai.embeddings.create(input=[text], model="text-embedding-ada-002")
            return resp.data[0].embedding
        else:
            # openai<1.0.0
            resp = openai.Embedding.create(input=[text], model="text-embedding-ada-002")
            return resp["data"][0]["embedding"]
    else:
        # Fallback: hash-based pseudo-embedding (for demo only, not real semantic search)
        import hashlib
        h = hashlib.sha256(text.encode("utf-8")).digest()
        return [b/255.0 for b in h[:64]]

def _cosine_similarity(a, b):
    # Compute cosine similarity between two vectors
    dot = sum(x*y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x*x for x in a))
    norm_b = math.sqrt(sum(x*x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

# Delegate semantic search to extracted module when available
try:
    from src.autocode.semantic import semantic_search_functions as _semantic_search_functions
    def semantic_search_functions(query: str, top_k: int = 5):
        return _semantic_search_functions(_db, query, top_k)
except Exception:
    # fallback to original implementation in this file (kept for compatibility)
    pass

def semantic_search_functions(query: str, top_k: int = 5):
    """
    Returns the top_k most semantically similar functions to the query.
    """
    query_emb = _get_embedding(query)
    scored = []
    for func in _db.functions.values():
        # Combine name, description, and code for embedding
        text = f"{func.name}\n{func.description}\n{func.code_snippet}"
        func_emb = _get_embedding(text)
        score = _cosine_similarity(query_emb, func_emb)
        scored.append((score, func))
    scored.sort(reverse=True, key=lambda x: x[0])
    results = []
    for score, func in scored[:top_k]:
        results.append({
            "id": func.function_id,
            "name": func.name,
            "description": func.description,
            "modules": getattr(func, "modules", []),
            "tags": getattr(func, "tags", []),
            "similarity": score
        })
    return results

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
    with open(filepath, "w", encoding="utf-8") as f:
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
    print(f"Generated Julia module file '{filepath}' for module '{module_name}' (with_tests={with_tests})")

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
    func = _db.functions.get(function_id)
    if not func:
        raise ValueError(f"Function ID {function_id} not found.")
    if not os.path.exists(input_file):
        raise ValueError(f"Input file '{input_file}' not found.")
    with open(input_file, "r", encoding="utf-8") as f:
        input_code = f.read()

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

    results = []
    if not success:
        return {"success": False, "runs": [], "stderr": output}

    stdout = output
    # Parse output for @time results
    import re
    pattern = r"===BENCHMARK_RUN_START===\s*(.*?)\s*===BENCHMARK_RUN_END==="
    runs = re.findall(pattern, stdout, re.DOTALL)
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
    return {"success": True, "runs": results, "stderr": ""}


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
        raise ValueError(f"Function ID {function_id} not found.")

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
        return {"success": False, "results": [], "stderr": str(e)}

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
        return {"success": False, "results": [], "stderr": stderr_snip}

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

_db = None
load_db()
if _db is None:
    _db = CodeDatabase()
    save_db()

def add_function(name: str, description: str, code: str, modules: Optional[List[str]] = None, tags: Optional[List[str]] = None) -> str:
    func = _db.add_function(name, description, code, modules, tags)
    save_db()
    return func.function_id

def add_function_to_module(function_id: str, module_name: str):
    _db.add_function_to_module(function_id, module_name)
    save_db()

def add_dependency(function_id: str, depends_on_id: str):
    _db.add_dependency(function_id, depends_on_id)
    save_db()

def add_tag(function_id: str, tag: str):
    _db.add_tag(function_id, tag)
    save_db()

def list_tags():
    return _db.list_tags()

def list_functions_by_tag(tag: str):
    return _db.list_functions_by_tag(tag)

def list_dependencies(function_id: str):
    return _db.list_dependencies(function_id)

def visualize_dependencies(filepath: str):
    _db.visualize_dependencies(filepath)

def list_modules():
    return _db.list_modules()

def list_functions(module: Optional[str] = None, tag: Optional[str] = None):
    return _db.list_functions(module, tag)

def get_function(function_id: str):
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

def modify_function(function_id: str, modifier: str, description: str, code: str):
    _db.modify_function(function_id, modifier, description, code)
    save_db()

def add_test(function_id: str, name: str, description: str, test_code: str) -> str:
    print(f"[DEBUG] add_test called with function_id={function_id}")
    test = _db.add_unit_test(function_id, name, description, test_code)
    if test is None:
        print(f"[DEBUG] add_test: Function ID {function_id} not found.")
        raise ValueError(f"Function ID {function_id} not found.")
    print(f"[DEBUG] add_test: Test {test.test_id} added to function {function_id}")
    save_db()
    return test.test_id

def run_tests(function_id: str = None):
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
    return [
        {
            "test_id": r.test_id,
            "status": r.status.value,
            "output": r.actual_result
        }
        for r in results
    ]

def get_test_results(function_id: str = None):
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

def list_modifications(function_id: str):
    return [
        {
            "id": mod.modification_id,
            "modifier": mod.modifier,
            "description": mod.description
        }
        for mod in _db.modifications
        if mod.function_id == function_id
    ]

def purge_tests(function_id: str):
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