import ell
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

# Use models from the extracted package instead of local duplicates
from src.autocode.models import (
    TestStatusEnum,
    TestResult,
    Modification,
    UnitTest,
    Module,
    Function,
)

DB_PATH = "code_db.pkl"

def save_db():
    with open(DB_PATH, "wb") as f:
        pickle.dump(_db, f)

def load_db():
    global _db
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            _db_loaded = pickle.load(f)
            if isinstance(_db_loaded, CodeDatabase):
                # Patch for legacy DBs: ensure modules attribute exists
                if not hasattr(_db_loaded, "modules") or _db_loaded.modules is None:
                    _db_loaded.modules = {}
                # Patch for legacy DBs: ensure tags attribute exists
                if not hasattr(_db_loaded, "tags") or _db_loaded.tags is None:
                    _db_loaded.tags = set()
                # Patch all functions to ensure tags attribute exists
                for func in getattr(_db_loaded, "functions", {}).values():
                    if not hasattr(func, "tags") or func.tags is None:
                        func.tags = []
                _db = _db_loaded

# Julia File Parsing Functions
def parse_julia_function(func_text: str) -> dict:
    """
    Parse a Julia function text to extract function name, arguments, and body.
    Returns a dict with function info.
    """
    # Remove comments and clean up the text
    lines = func_text.strip().split('\n')
    
    # Find the function declaration line
    func_declaration = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('function ') and not stripped.startswith('function('):
            func_declaration = stripped
            break
    
    if not func_declaration:
        return None
    
    # Extract function name from declaration
    # Handle patterns like: function name(...) or function name(...)::ReturnType
    func_match = re.match(r'function\s+([a-zA-Z_][a-zA-Z0-9_!]*)', func_declaration)
    if not func_match:
        return None
    
    func_name = func_match.group(1)
    
    return {
        'name': func_name,
        'code': func_text.strip(),
        'declaration': func_declaration
    }

def extract_julia_docstring(lines: List[str], start_idx: int) -> tuple:
    """
    Extract docstring from Julia code starting at given index.
    Returns (docstring, next_line_index) tuple.
    """
    docstring_parts = []
    i = start_idx
    
    # Look backwards from function line to find preceding comments
    while i >= 0:
        line = lines[i].strip()
        if not line:
            i -= 1
            continue
        elif line.startswith('#'):
            # Extract comment content
            comment_text = line[1:].strip()
            # Look for description patterns
            if comment_text.lower().startswith('description:'):
                docstring_parts.insert(0, comment_text[12:].strip())
            elif comment_text.lower().startswith('function:'):
                # Skip function name declarations
                pass
            else:
                # General comment
                docstring_parts.insert(0, comment_text)
            i -= 1
            continue
        elif line.startswith('"""'):
            # Multi-line docstring found
            docstring_lines = []
            j = i + 1
            while j < len(lines) and not lines[j].strip().endswith('"""'):
                docstring_lines.append(lines[j].strip())
                j += 1
            if j < len(lines):
                # Handle closing """ on same line as content
                last_line = lines[j].strip()
                if last_line != '"""':
                    docstring_lines.append(last_line[:-3].strip())
            docstring_parts = docstring_lines
            break
        elif line.startswith('function '):
            # Reached function declaration
            break
        else:
            # Non-comment, non-function line - stop looking
            break
    
    # Combine docstring parts
    if docstring_parts:
        return " ".join(docstring_parts).strip(), i
    else:
        return "Julia function", i

def parse_julia_file(filepath: str) -> dict:
    """
    Parse a Julia file and extract functions, module info, and docstrings.
    Returns a dict with module name and list of functions.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise ValueError(f"Error reading Julia file: {e}")
    
    lines = content.split('\n')
    result = {
        'module_name': None,
        'functions': []
    }
    
    # Extract module name if present
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('module ') and not stripped.startswith('module('):
            module_match = re.match(r'module\s+([a-zA-Z_][a-zA-Z0-9_]*)', stripped)
            if module_match:
                result['module_name'] = module_match.group(1)
                break
    
    # Find all function definitions
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for function declarations
        if line.startswith('function ') and not line.startswith('function('):
            # Extract any preceding docstring/comments (look backwards from current line)
            docstring, _ = extract_julia_docstring(lines, i-1)
            
            # Find the complete function body
            func_lines = []
            func_started = False
            indent_level = 0
            
            j = i
            while j < len(lines):
                current_line = lines[j]
                stripped_current = current_line.strip()
                
                if not func_started and stripped_current.startswith('function '):
                    func_started = True
                
                if func_started:
                    func_lines.append(current_line)
                    
                    # Count indentation changes
                    if stripped_current.startswith('function '):
                        indent_level += 1
                    elif stripped_current == 'end' or stripped_current.startswith('end '):
                        indent_level -= 1
                        if indent_level == 0:
                            break
                j += 1
            
            if func_lines:
                func_text = '\n'.join(func_lines)
                func_info = parse_julia_function(func_text)
                if func_info:
                    func_info['description'] = docstring
                    result['functions'].append(func_info)
            
            i = j + 1
        else:
            i += 1
    
    return result

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
        print(f"Added Function {func.function_id}: {name} (Modules: {modules}, Tags: {tags})")
        return func

    def add_unit_test(self, function_id: str, name: str, description: str, test_case: str) -> Optional[UnitTest]:
        func = self.functions.get(function_id)
        if not func:
            print(f"Function ID {function_id} not found.")
            return None
        test = UnitTest(function_id, name, description, test_case)
        func.add_unit_test(test)
        self.last_modified_date = datetime.datetime.now()
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
        "creation_date": func.creation_date.isoformat(),
        "last_modified_date": func.last_modified_date.isoformat(),
        "modules": func.modules,
        "tags": func.tags,
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
        tags=data.get("tags", [])
    )
    _db.functions[func.function_id] = func
    for t in data.get("unit_tests", []):
        test = UnitTest(
            function_id=func.function_id,
            name=t["name"],
            description=t["description"],
            test_case=t["test_case"]
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

class JuliaCodePackage(BaseModel):
    code: str = Field(description="The function.")
    tests: str = Field(description="A single test case for the function that uses @assert.")
    test_name: str = Field(description="A concise test name in snake_case.")
    test_description: str = Field(description="A concise test description.")
    input_types: str = Field(description="The input types for the function.")
    return_types: str = Field(description="The expected output types for the function.")
    short_description: str = Field(description="A short description of the function.")
    function_name: str = Field(description="The name of the function.")

@ell.complex(model="gpt-4o", response_format=JuliaCodePackage)
def generate_julia_function(description: str):
    prompt = f"Write a Julia function to {description}"
    return prompt

@ell.complex(model="gpt-4o", response_format=JuliaCodePackage)
def modify_julia_function(description: str, function_code: str):
    prompt = f"Modify the BODY of the Julia function {function_code} based on the following description: {description}"
    return prompt

@ell.simple(model="gpt-4o")
def write_test_case(function_name: str) -> str:
    prompt = (
        f"Write a Julia test file for the function `{function_name}`. "
        "Output ONLY valid Julia code. "
        "Do NOT include any markdown, triple backticks, comments, or explanations. "
        "Do NOT include the function definition, only the test code. "
        "Begin with 'using Test'."
    )
    return prompt

@ell.simple(model="gpt-4o")
def evaluate_output(expected_output: str, actual_output: str) -> str:
    prompt = f"Does the actual output `{actual_output}` match the expected `{expected_output}`?"
    return prompt

def pretty_print_function(code_db: CodeDatabase, function_id: str):
    func = code_db.functions.get(function_id)
    if not func:
        print(f"{Fore.RED}Function ID {function_id} not found.{Style.RESET_ALL}")
        return

    print(f"{Fore.CYAN}\n\nFunction ID: {func.function_id}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Name: {func.name}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Description: {func.description}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Creation Date: {func.creation_date.isoformat()}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Last Modified Date: {func.last_modified_date.isoformat()}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}\nCode Snippet:\n ```julia\n {func.code_snippet}{Style.RESET_ALL}```")

    print(f"{Fore.YELLOW}\nUnit Tests:{Style.RESET_ALL}")
    for test in func.unit_tests:
        print(f"{Fore.GREEN}Test ID: {test.test_id}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Name: {test.name}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Description: {test.description}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Test Case:\n{test.test_case}{Style.RESET_ALL}")
        print()

    print(f"{Fore.YELLOW}Modifications:{Style.RESET_ALL}")
    for mod in code_db.modifications:
        if mod.function_id == function_id:
            print(f"{Fore.MAGENTA}Modification ID: {mod.modification_id}{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}Modifier: {mod.modifier}{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}Description: {mod.description}{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}Modification Date: {mod.modification_date.isoformat()}{Style.RESET_ALL}")
            print()

    print(f"{Fore.YELLOW}Test Results:{Style.RESET_ALL}")
    for result in code_db.test_results:
        if result.function_id == function_id:
            print(f"{Fore.BLUE}Result ID: {result.result_id}{Style.RESET_ALL}")
            print(f"{Fore.BLUE}Test ID: {result.test_id}{Style.RESET_ALL}")
            print(f"{Fore.BLUE}Actual Result: {result.actual_result}{Style.RESET_ALL}")
            print(f"{Fore.BLUE}Status: {result.status.value}{Style.RESET_ALL}")
            print(f"{Fore.BLUE}Execution Date: {result.execution_date.isoformat()}{Style.RESET_ALL}")
            print()

def pretty_print_functions_table(code_db: CodeDatabase):
    table_data = []
    for func in code_db.functions.values():
        last_test_result = get_last_test_result(code_db, func.function_id)
        dot_color = get_dot_color(last_test_result)
        table_data.append([func.function_id, func.name, func.description, dot_color])

    headers = [f"{Fore.CYAN}Function ID{Style.RESET_ALL}", f"{Fore.CYAN}Name{Style.RESET_ALL}", f"{Fore.CYAN}Description{Style.RESET_ALL}", f"{Fore.CYAN}Status{Style.RESET_ALL}"]

    print(tabulate(table_data, headers=headers, tablefmt="grid"))

def get_last_test_result(code_db: CodeDatabase, function_id: str) -> str:
    for result in code_db.test_results[::-1]:
        if result.function_id == function_id:
            return result.status.value
    return ""

def get_dot_color(status: str) -> str:
    if status == TestStatusEnum.PASSED.value:
        return f"{Fore.GREEN}✔{Style.RESET_ALL}"
    elif status == TestStatusEnum.FAILED.value:
        return f"{Fore.RED}✘{Style.RESET_ALL}"
    else:
        return ""

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
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jl', delete=False) as temp_file:
        temp_file.write(julia_script)
        temp_filename = temp_file.name

    results = []
    try:
        proc = subprocess.run(
            ["julia", temp_filename],
            capture_output=True,
            text=True
        )
        stdout = proc.stdout
        # Parse output for @time results
        import re
        pattern = r"===BENCHMARK_RUN_START===\s*(.*?)\s*===BENCHMARK_RUN_END==="
        runs = re.findall(pattern, stdout, re.DOTALL)
        for run in runs:
            # @time output is typically: "  0.000012 seconds (2 allocations: 80 bytes)"
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
            "success": proc.returncode == 0,
            "runs": results,
            "stderr": proc.stderr
        }
    finally:
        os.remove(temp_filename)

def property_test_function(function_id: str, num_tests: int = 50, seed: int = 42):
    """
    Generate and run property-based tests for a Julia function using a fixed random seed.
    Returns a list of test results (pass/fail and any error messages).
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

    # --- Argument generation based on signature ---
    sig = getattr(func, "signature", None)
    if not sig or not sig.get("arg_names"):
        arg_expr = "rand(-1000:1000)"
        call_args = "arg"
        arg_decl = "arg = " + arg_expr
        arg_print = '", arg=", arg'
    else:
        arg_exprs = []
        call_args = []
        arg_prints = []
        for i, (name, typ) in enumerate(zip(sig["arg_names"], sig["arg_types"])):
            var = f"arg{i+1}"
            if typ is None or typ.lower().startswith("int"):
                expr = f"{var} = rand(-1000:1000)"
            elif "matrix" in (typ or "").lower():
                expr = f"{var} = rand(-10.0:0.1:10.0, 3, 3)"
            elif "float" in (typ or "").lower():
                expr = f"{var} = rand() * 2000 - 1000"
            elif "vector" in (typ or "").lower():
                expr = f"{var} = rand(-10.0:0.1:10.0, 5)"
            else:
                expr = f"{var} = rand(-1000:1000)"
            arg_exprs.append(expr)
            call_args.append(var)
            arg_prints.append(f'", {name}=", {var}')
        arg_decl = "\n            ".join(arg_exprs)
        call_args = ", ".join(call_args)
        arg_print = "".join(arg_prints)

    julia_script = f"""

using Random
Random.seed!({seed})

{func.code_snippet}

function _property_test_runner()
    for i in 1:{num_tests}
        try
            {arg_decl}
            result = {func.name}({call_args})
            @assert !isnothing(result)
            println("PROPERTY_TEST_PASS i=", i{arg_print})
        catch err
            println("PROPERTY_TEST_FAIL i=", i{arg_print}, " error=", err)
        end
    end

end

_property_test_runner()
"""
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jl', delete=False) as temp_file:
        temp_file.write(julia_script)
        temp_filename = temp_file.name

    results = []
    try:
        proc = subprocess.run(
            ["julia", temp_filename],
            capture_output=True,
            text=True
        )
        stdout = proc.stdout
        for line in stdout.splitlines():
            if line.startswith("PROPERTY_TEST_PASS"):
                results.append({"status": "pass", "info": line})
            elif line.startswith("PROPERTY_TEST_FAIL"):
                results.append({"status": "fail", "info": line})
        return {
            "success": proc.returncode == 0,
            "results": results,
            "stderr": proc.stderr
        }
    finally:
        os.remove(temp_filename)

# Shim: import models from new package location to maintain compatibility during refactor
try:
    from src.autocode.models import (
        TestStatusEnum,
        TestResult,
        Modification,
        UnitTest,
        Module,
        Function
    )
except Exception:
    # Fallback to local definitions if not yet moved
    pass

# Shim: import julia parser helpers if present
try:
    from src.autocode.julia_parsers import parse_julia_file, parse_julia_function, extract_julia_docstring
except Exception:
    pass

# Shim: persistence helpers
try:
    from src.autocode.persistence import save_db as _p_save_db, load_db as _p_load_db, DB_PATH as DB_PATH_SHIM
    def save_db():
        # preserve original no-arg API by delegating to persistence.save_db with the in-memory _db
        return _p_save_db(_db)
    def load_db():
        # delegate to persistence loader and assign to _db if present
        loaded = _p_load_db()
        if loaded is not None:
            globals()['_db'] = loaded
        return loaded
    if 'DB_PATH' not in globals():
        DB_PATH = DB_PATH_SHIM
except Exception:
    pass

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