import ell
import subprocess
import tempfile
import os
import datetime
import uuid
import json
import math
import re
from typing import Callable, Dict, List, Optional, Union
from enum import Enum
from pydantic import Field
from colorama import Fore, Style, init
from tabulate import tabulate

# SQLModel imports
from sqlmodel import SQLModel, Field, create_engine, Session, select, Relationship
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, Table

init()

try:
    import openai
    HAVE_OPENAI = True
except ImportError:
    HAVE_OPENAI = False

# Database configuration
DATABASE_URL = "sqlite:///code_db.sqlite"
engine = None

# Julia File Parsing Functions (unchanged from original)
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

# Enums
class TestStatusEnum(Enum):
    PASSED = "Passed"
    FAILED = "Failed"
    PENDING = "Pending"
    RUNNING = "Running"

# Junction tables for many-to-many relationships
function_modules_table = Table(
    "function_modules",
    SQLModel.metadata,
    Column("function_id", String, ForeignKey("function.function_id"), primary_key=True),
    Column("module_name", String, ForeignKey("module.name"), primary_key=True),
)

function_tags_table = Table(
    "function_tags",
    SQLModel.metadata,
    Column("function_id", String, ForeignKey("function.function_id"), primary_key=True),
    Column("tag", String, primary_key=True),
)

function_dependencies_table = Table(
    "function_dependencies",
    SQLModel.metadata,
    Column("function_id", String, ForeignKey("function.function_id"), primary_key=True),
    Column("depends_on_id", String, ForeignKey("function.function_id"), primary_key=True),
)

# SQLModel Classes
class ModuleBase(SQLModel):
    name: str = Field(primary_key=True, max_length=255)

class Module(ModuleBase, table=True):
    module_id: str = Field(default_factory=lambda: str(uuid.uuid4()), max_length=36)

class FunctionBase(SQLModel):
    name: str = Field(max_length=255)
    description: str = Field(default="")
    code_snippet: str = Field(sa_column=Column(Text))
    creation_date: datetime.datetime = Field(default_factory=datetime.datetime.now)
    last_modified_date: datetime.datetime = Field(default_factory=datetime.datetime.now)
    signature_json: Optional[str] = Field(default=None, sa_column=Column(Text))

class Function(FunctionBase, table=True):
    function_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    
    # Relationships
    unit_tests: List["UnitTest"] = Relationship(back_populates="function")
    test_results: List["TestResult"] = Relationship(back_populates="function")
    modifications: List["Modification"] = Relationship(back_populates="function")

    @property
    def signature(self) -> Optional[dict]:
        if self.signature_json:
            return json.loads(self.signature_json)
        return None

    @signature.setter
    def signature(self, value: Optional[dict]):
        if value:
            self.signature_json = json.dumps(value)
        else:
            self.signature_json = None

    def _parse_signature_from_code(self, code: str):
        """
        Parse the Julia function signature from the code snippet.
        Returns a dict: {'arg_names': [...], 'arg_types': [...]} or None if not found.
        """
        # Simple regex for: function name(args...)
        match = re.search(r"function\s+(\w+)\s*\(([^)]*)\)", code)
        if not match:
            return None
        arglist = match.group(2).strip()
        if not arglist:
            return {"arg_names": [], "arg_types": []}
        args = [a.strip() for a in arglist.split(",")]
        arg_names = []
        arg_types = []
        for a in args:
            # e.g. x::Int, y::Matrix{Float64}
            parts = a.split("::")
            arg_names.append(parts[0].strip())
            if len(parts) > 1:
                arg_types.append(parts[1].strip())
            else:
                arg_types.append(None)
        return {"arg_names": arg_names, "arg_types": arg_types}

    def __init__(self, **data):
        super().__init__(**data)
        if self.code_snippet and not self.signature:
            self.signature = self._parse_signature_from_code(self.code_snippet)

class UnitTestBase(SQLModel):
    function_id: str = Field(foreign_key="function.function_id", max_length=36)
    name: str = Field(max_length=255)
    description: str = Field(default="")
    test_case: str = Field(sa_column=Column(Text))

class UnitTest(UnitTestBase, table=True):
    test_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    
    # Relationships
    function: Function = Relationship(back_populates="unit_tests")
    test_results: List["TestResult"] = Relationship(back_populates="unit_test")

    def run_test(self, function_code: str) -> "TestResult":
        """
        Run the unit test by executing the function and test case in Julia.
        """
        print(f"Running Test '{self.name}' for Function ID {self.function_id}")

        # Combine the function code and test case into one Julia script
        julia_script = f"""
{function_code}

{self.test_case}
"""

        # Write the combined Julia script to a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jl', delete=False) as temp_file:
            temp_file.write(julia_script)
            temp_filename = temp_file.name

        try:
            # Execute the Julia script using subprocess
            result = subprocess.run(
                ["julia", temp_filename],
                capture_output=True,
                text=True
            )

            # Capture stdout and stderr
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            if result.returncode == 0:
                # Test passed
                status = TestStatusEnum.PASSED
                actual_result = "Test Passed."
            else:
                # Test failed, capture the error message
                status = TestStatusEnum.FAILED
                actual_result = stderr if stderr else "Test Failed with unknown error."
                print(f"Test Failed: {actual_result}")

            return TestResult(
                test_id=self.test_id,
                function_id=self.function_id,
                actual_result=actual_result,
                status=status.value
            )

        except Exception as e:
            # Handle any unexpected exceptions during test execution
            print(f"Exception during test execution: {e}")
            return TestResult(
                test_id=self.test_id,
                function_id=self.function_id,
                actual_result=str(e),
                status=TestStatusEnum.FAILED.value
            )

        finally:
            # Clean up the temporary Julia script file
            os.remove(temp_filename)

class TestResultBase(SQLModel):
    test_id: str = Field(foreign_key="unittest.test_id", max_length=36)
    function_id: str = Field(foreign_key="function.function_id", max_length=36)
    execution_date: datetime.datetime = Field(default_factory=datetime.datetime.now)
    actual_result: str = Field(sa_column=Column(Text))
    status: str = Field(max_length=50)

class TestResult(TestResultBase, table=True):
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    
    # Relationships
    unit_test: UnitTest = Relationship(back_populates="test_results")
    function: Function = Relationship(back_populates="test_results")

class ModificationBase(SQLModel):
    function_id: str = Field(foreign_key="function.function_id", max_length=36)
    modifier: str = Field(max_length=255)
    modification_date: datetime.datetime = Field(default_factory=datetime.datetime.now)
    description: str = Field(default="")

class Modification(ModificationBase, table=True):
    modification_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    
    # Relationships
    function: Function = Relationship(back_populates="modifications")

# Database initialization
def init_db():
    global engine
    engine = create_engine(DATABASE_URL, echo=False)
    SQLModel.metadata.create_all(engine)

def get_session():
    """Get a database session"""
    if engine is None:
        init_db()
    return Session(engine)

# Helper functions for tags (stored as separate records in junction table)
def get_function_tags(session: Session, function_id: str) -> List[str]:
    """Get all tags for a function"""
    result = session.execute(
        select(function_tags_table.c.tag).where(
            function_tags_table.c.function_id == function_id
        )
    )
    return [row[0] for row in result.fetchall()]

def add_function_tag(session: Session, function_id: str, tag: str):
    """Add a tag to a function"""
    from sqlalchemy import insert
    session.execute(
        insert(function_tags_table).values(function_id=function_id, tag=tag)
    )

def remove_function_tag(session: Session, function_id: str, tag: str):
    """Remove a tag from a function"""
    from sqlalchemy import delete
    session.execute(
        delete(function_tags_table).where(
            function_tags_table.c.function_id == function_id,
            function_tags_table.c.tag == tag
        )
    )

def get_all_tags(session: Session) -> List[str]:
    """Get all unique tags"""
    result = session.execute(
        select(function_tags_table.c.tag).distinct()
    )
    return sorted([row[0] for row in result.fetchall()])

# Core database operations class
class CodeDatabase:
    def __init__(self):
        self.db_name = "AutomatedDevDB_SQLModel"
        self.db_version = "2.0"
        self.created_date = datetime.datetime.now()
        init_db()

    def add_module(self, module_name: str) -> Module:
        with get_session() as session:
            # Check if module already exists
            statement = select(Module).where(Module.name == module_name)
            existing_module = session.exec(statement).first()
            
            if existing_module:
                return existing_module
            
            module = Module(name=module_name)
            session.add(module)
            session.commit()
            session.refresh(module)
            print(f"Added Module: {module_name}")
            return module

    def add_function(self, name: str, description: str, code_snippet: str, 
                    modules: Optional[List[str]] = None, tags: Optional[List[str]] = None) -> Function:
        with get_session() as session:
            func = Function(
                name=name,
                description=description,
                code_snippet=code_snippet
            )
            session.add(func)
            session.flush()  # Get the ID
            
            # Add modules
            if modules:
                for module_name in modules:
                    # Check if module exists, create if not
                    module_statement = select(Module).where(Module.name == module_name)
                    existing_module = session.exec(module_statement).first()
                    
                    if not existing_module:
                        module = Module(name=module_name)
                        session.add(module)
                        session.flush()
                    
                    # Add relationship
                    from sqlalchemy import insert
                    session.execute(
                        insert(function_modules_table).values(
                            function_id=func.function_id, 
                            module_name=module_name
                        )
                    )
            
            # Add tags
            if tags:
                for tag in tags:
                    add_function_tag(session, func.function_id, tag)
            
            session.commit()
            session.refresh(func)
            print(f"Added Function {func.function_id}: {name} (Modules: {modules}, Tags: {tags})")
            return func

    def add_unit_test(self, function_id: str, name: str, description: str, test_case: str) -> Optional[UnitTest]:
        with get_session() as session:
            # Check if function exists
            statement = select(Function).where(Function.function_id == function_id)
            func = session.exec(statement).first()
            if not func:
                print(f"Function ID {function_id} not found.")
                return None
            
            test = UnitTest(
                function_id=function_id,
                name=name,
                description=description,
                test_case=test_case
            )
            session.add(test)
            session.commit()
            session.refresh(test)
            print(f"Added UnitTest {test.test_id} to Function {function_id}")
            return test

    def execute_tests(self, function_id: str = None):
        results = []
        with get_session() as session:
            if function_id:
                # Get specific function
                statement = select(Function).where(Function.function_id == function_id)
                funcs = [session.exec(statement).first()]
                if not funcs[0]:
                    return results
                
                # Remove previous results for this function
                from sqlalchemy import delete
                session.execute(
                    delete(TestResult).where(TestResult.function_id == function_id)
                )
            else:
                # Get all functions
                statement = select(Function)
                funcs = session.exec(statement).all()
                
                # Remove all previous results
                from sqlalchemy import delete
                session.execute(delete(TestResult))

            for func in funcs:
                if not func:
                    continue
                
                # Get unit tests for this function
                test_statement = select(UnitTest).where(UnitTest.function_id == func.function_id)
                tests = session.exec(test_statement).all()
                
                for test in tests:
                    result = test.run_test(func.code_snippet)
                    session.add(result)
                    session.flush()  # Get the result ID
                    # Extract data while session is active
                    results.append({
                        "test_id": result.test_id,
                        "function_id": result.function_id,
                        "status": result.status,
                        "actual_result": result.actual_result,
                        "execution_date": result.execution_date,
                        "result_id": result.result_id
                    })
                    print(f"Test Result: {result}")
            
            session.commit()
        return results

    def modify_function(self, function_id: str, modifier: str, description: str, new_code_snippet: str):
        with get_session() as session:
            statement = select(Function).where(Function.function_id == function_id)
            func = session.exec(statement).first()
            if not func:
                print(f"Function ID {function_id} not found.")
                return
            
            func.code_snippet = new_code_snippet
            func.last_modified_date = datetime.datetime.now()
            func.signature = func._parse_signature_from_code(new_code_snippet)
            
            modification = Modification(
                function_id=function_id,
                modifier=modifier,
                description=description
            )
            session.add(modification)
            session.commit()
            print(f"Logged Modification for Function {function_id}")

    def add_function_to_module(self, function_id: str, module_name: str):
        with get_session() as session:
            # Check if function exists
            statement = select(Function).where(Function.function_id == function_id)
            func = session.exec(statement).first()
            if not func:
                print(f"Function ID {function_id} not found.")
                return
            
            # Check if module exists, create if not
            module_statement = select(Module).where(Module.name == module_name)
            existing_module = session.exec(module_statement).first()
            
            if not existing_module:
                module = Module(name=module_name)
                session.add(module)
                session.flush()
            
            # Add relationship
            from sqlalchemy import insert
            session.execute(
                insert(function_modules_table).values(
                    function_id=function_id, 
                    module_name=module_name
                )
            )
            session.commit()
            print(f"Added Function {function_id} to Module {module_name}")

    def add_dependency(self, function_id: str, depends_on_id: str):
        with get_session() as session:
            # Check both functions exist
            statement1 = select(Function).where(Function.function_id == function_id)
            statement2 = select(Function).where(Function.function_id == depends_on_id)
            func1 = session.exec(statement1).first()
            func2 = session.exec(statement2).first()
            
            if not func1:
                raise ValueError(f"Function ID {function_id} not found.")
            if not func2:
                raise ValueError(f"Dependency function ID {depends_on_id} not found.")
            
            from sqlalchemy import insert
            session.execute(
                insert(function_dependencies_table).values(
                    function_id=function_id,
                    depends_on_id=depends_on_id
                )
            )
            session.commit()
            print(f"Added dependency: {function_id} depends on {depends_on_id}")

    def add_tag(self, function_id: str, tag: str):
        with get_session() as session:
            statement = select(Function).where(Function.function_id == function_id)
            func = session.exec(statement).first()
            if not func:
                raise ValueError(f"Function ID {function_id} not found.")
            
            add_function_tag(session, function_id, tag)
            session.commit()
            print(f"Added tag '{tag}' to function {function_id}")

    def list_tags(self):
        with get_session() as session:
            return get_all_tags(session)

    def list_functions_by_tag(self, tag: str):
        with get_session() as session:
            # Join with function_tags_table
            statement = select(Function).join(
                function_tags_table,
                Function.function_id == function_tags_table.c.function_id
            ).where(function_tags_table.c.tag == tag)
            
            funcs = session.exec(statement).all()
            return [
                {
                    "id": func.function_id,
                    "name": func.name,
                    "description": func.description,
                    "modules": self._get_function_modules(session, func.function_id),
                    "tags": get_function_tags(session, func.function_id)
                }
                for func in funcs
            ]

    def _get_function_modules(self, session: Session, function_id: str) -> List[str]:
        """Get all modules for a function"""
        result = session.execute(
            select(function_modules_table.c.module_name).where(
                function_modules_table.c.function_id == function_id
            )
        )
        return [row[0] for row in result.fetchall()]

    def list_dependencies(self, function_id: str):
        with get_session() as session:
            result = session.execute(
                select(function_dependencies_table.c.depends_on_id).where(
                    function_dependencies_table.c.function_id == function_id
                )
            )
            return [row[0] for row in result.fetchall()]

    def visualize_dependencies(self, filepath: str):
        with get_session() as session:
            result = session.execute(select(function_dependencies_table))
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("digraph dependencies {\n")
                for row in result.fetchall():
                    f.write(f'    "{row.function_id}" -> "{row.depends_on_id}";\n')
                f.write("}\n")
            print(f"Dependency graph written to {filepath}")

    def list_modules(self):
        with get_session() as session:
            statement = select(Module)
            modules = session.exec(statement).all()
            return [{"id": m.module_id, "name": m.name} for m in modules]

    def list_functions(self, module: Optional[str] = None, tag: Optional[str] = None):
        with get_session() as session:
            statement = select(Function)
            
            # Apply filters
            if module:
                statement = statement.join(
                    function_modules_table,
                    Function.function_id == function_modules_table.c.function_id
                ).where(function_modules_table.c.module_name == module)
            
            if tag:
                statement = statement.join(
                    function_tags_table,
                    Function.function_id == function_tags_table.c.function_id
                ).where(function_tags_table.c.tag == tag)
            
            funcs = session.exec(statement).all()
            return [
                {
                    "id": func.function_id,
                    "name": func.name,
                    "description": func.description,
                    "modules": self._get_function_modules(session, func.function_id),
                    "tags": get_function_tags(session, func.function_id)
                }
                for func in funcs
            ]

    def __repr__(self):
        with get_session() as session:
            func_count = len(session.exec(select(Function)).all())
            module_count = len(session.exec(select(Module)).all())
            tag_count = len(get_all_tags(session))
            
            return (f"<CodeDatabase: {self.db_name} v{self.db_version}, "
                    f"Created: {self.created_date.isoformat()}, "
                    f"Functions: {func_count}, Modules: {module_count}, Tags: {tag_count}>")

# Initialize global database instance
_db = CodeDatabase()

# Helper functions to maintain API compatibility
def add_function(name: str, description: str, code: str, modules: Optional[List[str]] = None, tags: Optional[List[str]] = None) -> str:
    func = _db.add_function(name, description, code, modules, tags)
    return func.function_id

def add_function_to_module(function_id: str, module_name: str):
    _db.add_function_to_module(function_id, module_name)

def add_dependency(function_id: str, depends_on_id: str):
    _db.add_dependency(function_id, depends_on_id)

def add_tag(function_id: str, tag: str):
    _db.add_tag(function_id, tag)

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
    with get_session() as session:
        statement = select(Function).where(Function.function_id == function_id)
        func = session.exec(statement).first()
        if not func:
            return None
        
        return {
            "id": func.function_id,
            "name": func.name,
            "description": func.description,
            "code": func.code_snippet,
            "modules": _db._get_function_modules(session, func.function_id),
            "tags": get_function_tags(session, func.function_id)
        }

def modify_function(function_id: str, modifier: str, description: str, code: str):
    _db.modify_function(function_id, modifier, description, code)

def add_test(function_id: str, name: str, description: str, test_code: str) -> str:
    print(f"[DEBUG] add_test called with function_id={function_id}")
    test = _db.add_unit_test(function_id, name, description, test_code)
    if test is None:
        print(f"[DEBUG] add_test: Function ID {function_id} not found.")
        raise ValueError(f"Function ID {function_id} not found.")
    print(f"[DEBUG] add_test: Test {test.test_id} added to function {function_id}")
    return test.test_id

def run_tests(function_id: str = None):
    print(f"[DEBUG] run_tests called with function_id={function_id}")
    results = _db.execute_tests(function_id)
    print(f"[DEBUG] run_tests: {len(results)} results generated.")
    return [
        {
            "test_id": r["test_id"],
            "status": r["status"],
            "output": r["actual_result"]
        }
        for r in results
    ]

def get_test_results(function_id: str = None):
    print(f"[DEBUG] get_test_results called with function_id={function_id}")
    with get_session() as session:
        statement = select(TestResult)
        if function_id:
            statement = statement.where(TestResult.function_id == function_id)
        
        results = session.exec(statement).all()
        print(f"[DEBUG] get_test_results: returning {len(results)} results for function_id={function_id}")
        return [
            {
                "test_id": result.test_id,
                "status": result.status,
                "output": result.actual_result
            }
            for result in results
        ]

def list_modifications(function_id: str):
    with get_session() as session:
        statement = select(Modification).where(Modification.function_id == function_id)
        modifications = session.exec(statement).all()
        return [
            {
                "id": mod.modification_id,
                "modifier": mod.modifier,
                "description": mod.description
            }
            for mod in modifications
        ]

def purge_tests(function_id: str):
    with get_session() as session:
        print(f"[DEBUG] purge_tests: Function ID {function_id}")
        
        # Delete unit tests
        from sqlalchemy import delete
        unit_tests_deleted = session.execute(
            delete(UnitTest).where(UnitTest.function_id == function_id)
        )
        
        # Delete test results
        test_results_deleted = session.execute(
            delete(TestResult).where(TestResult.function_id == function_id)
        )
        
        session.commit()
        print(f"[DEBUG] purge_tests: Removed unit tests and test results for function {function_id}.")

# Additional functions that need to be implemented...
# (search_functions, semantic_search_functions, import/export functions, etc.)
# For now, let's implement the basic ones:

def search_functions(query: str, created_after: str = None, modified_after: str = None, test_status: str = None):
    query_lower = query.lower()
    with get_session() as session:
        statement = select(Function)
        funcs = session.exec(statement).all()
        
        results = []
        for func in funcs:
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
                
                # Test status check would require querying test results
                if test_status:
                    test_statement = select(TestResult).where(
                        TestResult.function_id == func.function_id
                    ).order_by(TestResult.execution_date.desc())
                    last_result = session.exec(test_statement).first()
                    if not last_result or last_result.status.lower() != test_status.lower():
                        continue
                
                results.append({
                    "id": func.function_id,
                    "name": func.name,
                    "description": func.description,
                    "modules": _db._get_function_modules(session, func.function_id),
                    "tags": get_function_tags(session, func.function_id)
                })
        
        return results

# ELL functions and additional utilities
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
    
    with get_session() as session:
        statement = select(Function)
        funcs = session.exec(statement).all()
        
        for func in funcs:
            # Combine name, description, and code for embedding
            text = f"{func.name}\n{func.description}\n{func.code_snippet}"
            func_emb = _get_embedding(text)
            score = _cosine_similarity(query_emb, func_emb)
            scored.append((score, func))
    
    scored.sort(reverse=True, key=lambda x: x[0])
    results = []
    
    with get_session() as session:
        for score, func in scored[:top_k]:
            results.append({
                "id": func.function_id,
                "name": func.name,
                "description": func.description,
                "modules": _db._get_function_modules(session, func.function_id),
                "tags": get_function_tags(session, func.function_id),
                "similarity": score
            })
    return results

from pydantic import BaseModel

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

# Import/Export functions
def export_function(function_id: str, filepath: str):
    with get_session() as session:
        statement = select(Function).where(Function.function_id == function_id)
        func = session.exec(statement).first()
        if not func:
            raise ValueError(f"Function ID {function_id} not found.")
        
        # Get related data
        modules = _db._get_function_modules(session, func.function_id)
        tags = get_function_tags(session, func.function_id)
        
        # Get unit tests
        test_statement = select(UnitTest).where(UnitTest.function_id == function_id)
        tests = session.exec(test_statement).all()
        
        data = {
            "function_id": func.function_id,
            "name": func.name,
            "description": func.description,
            "code_snippet": func.code_snippet,
            "creation_date": func.creation_date.isoformat(),
            "last_modified_date": func.last_modified_date.isoformat(),
            "modules": modules,
            "tags": tags,
            "unit_tests": [
                {
                    "test_id": t.test_id,
                    "name": t.name,
                    "description": t.description,
                    "test_case": t.test_case
                }
                for t in tests
            ]
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Exported function {function_id} to {filepath}")

def import_function(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    func_id = add_function(
        name=data["name"],
        description=data["description"],
        code=data["code_snippet"],
        modules=data.get("modules", []),
        tags=data.get("tags", [])
    )
    
    for t in data.get("unit_tests", []):
        add_test(
            function_id=func_id,
            name=t["name"],
            description=t["description"],
            test_code=t["test_case"]
        )
    
    print(f"Imported function '{data['name']}' with new ID: {func_id}")
    return func_id

def export_module(module_name: str, filepath: str):
    with get_session() as session:
        # Check if module exists
        module_statement = select(Module).where(Module.name == module_name)
        module = session.exec(module_statement).first()
        if not module:
            raise ValueError(f"Module '{module_name}' not found.")
        
        # Get functions in this module
        statement = select(Function).join(
            function_modules_table,
            Function.function_id == function_modules_table.c.function_id
        ).where(function_modules_table.c.module_name == module_name)
        
        functions = session.exec(statement).all()
        
        data = {
            "module_name": module_name,
            "functions": []
        }
        
        for func in functions:
            # Get unit tests for this function
            test_statement = select(UnitTest).where(UnitTest.function_id == func.function_id)
            tests = session.exec(test_statement).all()
            
            data["functions"].append({
                "function_id": func.function_id,
                "name": func.name,
                "description": func.description,
                "code_snippet": func.code_snippet,
                "creation_date": func.creation_date.isoformat(),
                "last_modified_date": func.last_modified_date.isoformat(),
                "modules": _db._get_function_modules(session, func.function_id),
                "tags": get_function_tags(session, func.function_id),
                "unit_tests": [
                    {
                        "test_id": t.test_id,
                        "name": t.name,
                        "description": t.description,
                        "test_case": t.test_case
                    }
                    for t in tests
                ]
            })
        
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
        func_id = add_function(
            name=func_data["name"],
            description=func_data["description"],
            code=func_data["code_snippet"],
            modules=func_data.get("modules", []),
            tags=func_data.get("tags", [])
        )
        
        for t in func_data.get("unit_tests", []):
            add_test(
                function_id=func_id,
                name=t["name"],
                description=t["description"],
                test_code=t["test_case"]
            )
        
        new_func_ids.append(func_id)
    
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
    _db.add_module(final_module_name)
    
    new_func_ids = []
    for func_data in parsed_data['functions']:
        # Create function object
        func_id = add_function(
            name=func_data['name'],
            description=func_data['description'],
            code=func_data['code'],
            modules=[final_module_name],
            tags=['julia', 'imported']
        )
        
        # Generate basic test if requested
        if generate_tests:
            try:
                test_code = write_test_case(func_data['name'])
                if test_code:
                    add_test(
                        function_id=func_id,
                        name=f"test_{func_data['name']}_basic",
                        description=f"Auto-generated basic test for {func_data['name']}",
                        test_code=test_code
                    )
            except Exception as e:
                print(f"Warning: Could not generate test for {func_data['name']}: {e}")
        
        new_func_ids.append(func_id)
        print(f"Imported function '{func_data['name']}' with ID: {func_id}")
    
    print(f"Imported {len(new_func_ids)} functions from Julia file '{filepath}' into module '{final_module_name}'")
    return new_func_ids

# Display functions
def pretty_print_function(code_db: CodeDatabase, function_id: str):
    with get_session() as session:
        statement = select(Function).where(Function.function_id == function_id)
        func = session.exec(statement).first()
        if not func:
            print(f"{Fore.RED}Function ID {function_id} not found.{Style.RESET_ALL}")
            return

        print(f"{Fore.CYAN}\n\nFunction ID: {func.function_id}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Name: {func.name}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Description: {func.description}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Creation Date: {func.creation_date.isoformat()}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Last Modified Date: {func.last_modified_date.isoformat()}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}\nCode Snippet:\n ```julia\n {func.code_snippet}{Style.RESET_ALL}```")

        # Get unit tests
        test_statement = select(UnitTest).where(UnitTest.function_id == function_id)
        tests = session.exec(test_statement).all()
        
        print(f"{Fore.YELLOW}\nUnit Tests:{Style.RESET_ALL}")
        for test in tests:
            print(f"{Fore.GREEN}Test ID: {test.test_id}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Name: {test.name}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Description: {test.description}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Test Case:\n{test.test_case}{Style.RESET_ALL}")
            print()

        # Get modifications
        mod_statement = select(Modification).where(Modification.function_id == function_id)
        modifications = session.exec(mod_statement).all()
        
        print(f"{Fore.YELLOW}Modifications:{Style.RESET_ALL}")
        for mod in modifications:
            print(f"{Fore.MAGENTA}Modification ID: {mod.modification_id}{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}Modifier: {mod.modifier}{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}Description: {mod.description}{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}Modification Date: {mod.modification_date.isoformat()}{Style.RESET_ALL}")
            print()

        # Get test results
        result_statement = select(TestResult).where(TestResult.function_id == function_id)
        results = session.exec(result_statement).all()
        
        print(f"{Fore.YELLOW}Test Results:{Style.RESET_ALL}")
        for result in results:
            print(f"{Fore.BLUE}Result ID: {result.result_id}{Style.RESET_ALL}")
            print(f"{Fore.BLUE}Test ID: {result.test_id}{Style.RESET_ALL}")
            print(f"{Fore.BLUE}Actual Result: {result.actual_result}{Style.RESET_ALL}")
            print(f"{Fore.BLUE}Status: {result.status}{Style.RESET_ALL}")
            print(f"{Fore.BLUE}Execution Date: {result.execution_date.isoformat()}{Style.RESET_ALL}")
            print()

def pretty_print_functions_table(code_db: CodeDatabase):
    table_data = []
    with get_session() as session:
        statement = select(Function)
        funcs = session.exec(statement).all()
        
        for func in funcs:
            last_test_result = get_last_test_result(session, func.function_id)
            dot_color = get_dot_color(last_test_result)
            table_data.append([func.function_id, func.name, func.description, dot_color])

    headers = [f"{Fore.CYAN}Function ID{Style.RESET_ALL}", f"{Fore.CYAN}Name{Style.RESET_ALL}", f"{Fore.CYAN}Description{Style.RESET_ALL}", f"{Fore.CYAN}Status{Style.RESET_ALL}"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))

def get_last_test_result(session: Session, function_id: str) -> str:
    statement = select(TestResult).where(
        TestResult.function_id == function_id
    ).order_by(TestResult.execution_date.desc())
    result = session.exec(statement).first()
    return result.status if result else ""

def get_dot_color(status: str) -> str:
    if status == TestStatusEnum.PASSED.value:
        return f"{Fore.GREEN}✔{Style.RESET_ALL}"
    elif status == TestStatusEnum.FAILED.value:
        return f"{Fore.RED}✘{Style.RESET_ALL}"
    else:
        return ""

def generate_module_file(module_name: str, filepath: str, with_tests: bool = False):
    with get_session() as session:
        # Check if module exists
        module_statement = select(Module).where(Module.name == module_name)
        module = session.exec(module_statement).first()
        if not module:
            raise ValueError(f"Module '{module_name}' not found.")
        
        # Get functions in this module
        statement = select(Function).join(
            function_modules_table,
            Function.function_id == function_modules_table.c.function_id
        ).where(function_modules_table.c.module_name == module_name)
        
        functions = session.exec(statement).all()
        if not functions:
            raise ValueError(f"No functions found in module '{module_name}'.")
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"module {module_name}\n\n")
            for func in functions:
                f.write(f"# Function: {func.name}\n")
                f.write(f"# Description: {func.description}\n")
                f.write(func.code_snippet.strip() + "\n\n")
                
                if with_tests:
                    test_statement = select(UnitTest).where(UnitTest.function_id == func.function_id)
                    tests = session.exec(test_statement).all()
                    for test in tests:
                        f.write(f"# Test: {test.name}\n")
                        f.write(f"# {test.description}\n")
                        f.write(test.test_case.strip() + "\n\n")
            f.write(f"end # module {module_name}\n")
        print(f"Generated Julia module file '{filepath}' for module '{module_name}' (with_tests={with_tests})")

def get_coverage_report():
    report = []
    with get_session() as session:
        statement = select(Function)
        funcs = session.exec(statement).all()
        
        for func in funcs:
            # Get unit tests for this function
            test_statement = select(UnitTest).where(UnitTest.function_id == func.function_id)
            tests = session.exec(test_statement).all()
            test_ids = [t.test_id for t in tests]
            total_tests = len(test_ids)
            
            passed = 0
            failed = 0
            for tid in test_ids:
                # Get latest result for this test
                result_statement = select(TestResult).where(
                    TestResult.test_id == tid
                ).order_by(TestResult.execution_date.desc())
                last_result = session.exec(result_statement).first()
                
                if last_result:
                    if last_result.status == TestStatusEnum.PASSED.value:
                        passed += 1
                    elif last_result.status == TestStatusEnum.FAILED.value:
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

# Data migration function
def migrate_from_pickle(pickle_file: str = "code_db.pkl"):
    """
    Migrate data from the old pickle format to SQLModel.
    """
    if not os.path.exists(pickle_file):
        print(f"Pickle file {pickle_file} not found. Starting with empty database.")
        return
    
    print(f"Migrating data from {pickle_file}...")
    
    import pickle
    with open(pickle_file, "rb") as f:
        old_db = pickle.load(f)
    
    # Clear existing database
    with get_session() as session:
        from sqlalchemy import delete
        session.execute(delete(TestResult))
        session.execute(delete(UnitTest))
        session.execute(delete(Modification))
        session.execute(delete(function_tags_table))
        session.execute(delete(function_modules_table))
        session.execute(delete(function_dependencies_table))
        session.execute(delete(Function))
        session.execute(delete(Module))
        session.commit()
    
    # Migrate modules
    if hasattr(old_db, 'modules') and old_db.modules:
        for module_name, module_obj in old_db.modules.items():
            _db.add_module(module_name)
    
    # Migrate functions
    if hasattr(old_db, 'functions') and old_db.functions:
        old_to_new_ids = {}  # Map old IDs to new IDs
        
        for old_func in old_db.functions.values():
            modules = getattr(old_func, 'modules', [])
            tags = getattr(old_func, 'tags', [])
            
            new_func = _db.add_function(
                name=old_func.name,
                description=old_func.description,
                code_snippet=old_func.code_snippet,
                modules=modules,
                tags=tags
            )
            old_to_new_ids[old_func.function_id] = new_func.function_id
            
            # Set timestamps
            with get_session() as session:
                statement = select(Function).where(Function.function_id == new_func.function_id)
                func = session.exec(statement).first()
                if func:
                    func.creation_date = old_func.creation_date
                    func.last_modified_date = old_func.last_modified_date
                    session.commit()
            
            # Migrate unit tests
            for old_test in old_func.unit_tests:
                _db.add_unit_test(
                    function_id=new_func.function_id,
                    name=old_test.name,
                    description=old_test.description,
                    test_case=old_test.test_case
                )
        
        # Migrate dependencies (after all functions are created)
        for old_func in old_db.functions.values():
            if hasattr(old_func, 'dependencies') and old_func.dependencies:
                new_func_id = old_to_new_ids[old_func.function_id]
                for old_dep_id in old_func.dependencies:
                    if old_dep_id in old_to_new_ids:
                        new_dep_id = old_to_new_ids[old_dep_id]
                        _db.add_dependency(new_func_id, new_dep_id)
    
    # Migrate test results
    if hasattr(old_db, 'test_results') and old_db.test_results:
        with get_session() as session:
            for old_result in old_db.test_results:
                # Find the new test ID based on function mapping
                if old_result.function_id in old_to_new_ids:
                    new_func_id = old_to_new_ids[old_result.function_id]
                    
                    # Find matching test by name/description
                    test_statement = select(UnitTest).where(UnitTest.function_id == new_func_id)
                    tests = session.exec(test_statement).all()
                    
                    # For now, just link to first test if exists
                    if tests:
                        new_result = TestResult(
                            test_id=tests[0].test_id,
                            function_id=new_func_id,
                            actual_result=old_result.actual_result,
                            status=old_result.status.value,
                            execution_date=old_result.execution_date
                        )
                        session.add(new_result)
            session.commit()
    
    # Migrate modifications
    if hasattr(old_db, 'modifications') and old_db.modifications:
        with get_session() as session:
            for old_mod in old_db.modifications:
                if old_mod.function_id in old_to_new_ids:
                    new_func_id = old_to_new_ids[old_mod.function_id]
                    new_mod = Modification(
                        function_id=new_func_id,
                        modifier=old_mod.modifier,
                        description=old_mod.description,
                        modification_date=old_mod.modification_date
                    )
                    session.add(new_mod)
            session.commit()
    
    print(f"Migration completed! Migrated {len(old_to_new_ids)} functions.")

def test_function():
    code_db = CodeDatabase()
    print(code_db)

    description = "calculate the factorial of a non-negative integer"
    print(f"Generating Julia function for: {description}")
    generated_code_message = generate_julia_function(description)
    generated_code = generated_code_message.parsed

    func_id = add_function(generated_code.function_name, generated_code.short_description, generated_code.code)
    
    add_test(func_id, generated_code.test_name, generated_code.test_description, generated_code.tests)
    
    max_attempts = 5
    attempt = 0
    while attempt < max_attempts:
        print(f"\nAttempt {attempt + 1} of {max_attempts}")
        
        print("Executing Tests...")
        results = run_tests(func_id)
        
        failed_tests = [r for r in results if r["status"] == TestStatusEnum.FAILED.value]
        
        if not failed_tests:
            print("All tests passed!")
            break
            
        print(f"Failed tests: {len(failed_tests)}")
        for result in failed_tests:
            print(f"Test {result['test_id']} failed: {result['output']}")
        
        fix_description = f"Fix the function. Current tests failed with: {[r['output'] for r in failed_tests]}"
        print(f"\nRequesting fix: {fix_description}")
        fixed_code_message = modify_julia_function(fix_description)
        fixed_code = fixed_code_message.parsed.code
        
        modify_function(func_id, "AI", f"Fix attempt {attempt + 1}", fixed_code)
        
        attempt += 1
    
    if attempt == max_attempts:
        print("\nMaximum fix attempts reached without success")
    else:
        print(f"\nFixed in {attempt + 1} attempts")

if __name__ == "__main__":
    # Migrate existing data if pickle file exists
    migrate_from_pickle()
    test_function()
