"""Models extracted from top-level code_db.py for incremental refactor.
This file mirrors the data/model classes so the refactor can proceed safely.
"""
from __future__ import annotations

import uuid
import datetime
import tempfile
import os
import subprocess
from typing import List, Optional
from enum import Enum


class TestStatusEnum(Enum):
    PASSED = "Passed"
    FAILED = "Failed"
    PENDING = "Pending"
    RUNNING = "Running"


class TestResult:
    def __init__(self, test_id: str, function_id: str, actual_result: str, status: TestStatusEnum):
        self.result_id = str(uuid.uuid4())
        self.test_id = test_id
        self.function_id = function_id
        self.execution_date = datetime.datetime.now()
        self.actual_result = actual_result
        self.status = status

    def __repr__(self):
        return (f"<TestResult {self.result_id}: Test {self.test_id} for Function {self.function_id} "
                f"Status: {self.status.value}>")


class Modification:
    def __init__(self, function_id: str, modifier: str, description: str):
        self.modification_id = str(uuid.uuid4())
        self.function_id = function_id
        self.modifier = modifier
        self.modification_date = datetime.datetime.now()
        self.description = description

    def __repr__(self):
        return (f"<Modification {self.modification_id}: Function {self.function_id} modified by "
                f"{self.modifier} on {self.modification_date.isoformat()}>")


class UnitTest:
    def __init__(self, function_id: str, name: str, description: str, test_case: str):
        """
        Initialize a UnitTest instance.
        :param function_id: The ID of the function being tested.
        :param name: The name of the unit test.
        :param description: A brief description of the unit test.
        :param test_case: The Julia code for the test case as a string.
        """
        self.test_id = str(uuid.uuid4())
        self.function_id = function_id
        self.name = name
        self.description = description
        self.test_case = test_case

    def run_test(self, function_code: str) -> TestResult:
        """
        Run the unit test by executing the function and test case in Julia.
        """
        print(f"Running Test '{self.name}' for Function ID {self.function_id}")

        julia_script = f"""
{function_code}

{self.test_case}
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jl', delete=False) as temp_file:
            temp_file.write(julia_script)
            temp_filename = temp_file.name

        try:
            result = subprocess.run(
                ["julia", temp_filename],
                capture_output=True,
                text=True
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            if result.returncode == 0:
                status = TestStatusEnum.PASSED
                actual_result = "Test Passed."
            else:
                status = TestStatusEnum.FAILED
                actual_result = stderr if stderr else "Test Failed with unknown error."
                print(f"Test Failed: {actual_result}")

            return TestResult(
                test_id=self.test_id,
                function_id=self.function_id,
                actual_result=actual_result,
                status=status
            )

        except Exception as e:
            print(f"Exception during test execution: {e}")
            return TestResult(
                test_id=self.test_id,
                function_id=self.function_id,
                actual_result=str(e),
                status=TestStatusEnum.FAILED
            )

        finally:
            try:
                os.remove(temp_filename)
            except Exception:
                pass

    def __repr__(self):
        return (f"<UnitTest {self.test_id}: {self.name} for Function {self.function_id}>")


class Module:
    def __init__(self, name: str):
        self.module_id = str(uuid.uuid4())
        self.name = name

    def __repr__(self):
        return f"<Module {self.module_id}: {self.name}>"


class Function:
    def __init__(self, name: str, description: str, code_snippet: str, modules: Optional[List[str]] = None, tags: Optional[List[str]] = None):
        self.function_id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.code_snippet = code_snippet
        self.creation_date = datetime.datetime.now()
        self.last_modified_date = self.creation_date
        self.unit_tests: List[UnitTest] = []
        self.modules: List[str] = modules or []
        self.dependencies: List[str] = []
        self.tags: List[str] = tags or []
        self.signature: dict = self._parse_signature_from_code(code_snippet)

    def _parse_signature_from_code(self, code: str):
        import re
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
            parts = a.split("::")
            arg_names.append(parts[0].strip())
            if len(parts) > 1:
                arg_types.append(parts[1].strip())
            else:
                arg_types.append(None)
        return {"arg_names": arg_names, "arg_types": arg_types}

    def add_unit_test(self, test: UnitTest):
        self.unit_tests.append(test)
        print(f"Added UnitTest {test.test_id} to Function {self.function_id}")

    def modify_code(self, new_code_snippet: str):
        self.code_snippet = new_code_snippet
        self.last_modified_date = datetime.datetime.now()
        print(f"Function {self.function_id} code modified.")

    def add_module(self, module_name: str):
        if module_name not in self.modules:
            self.modules.append(module_name)

    def add_dependency(self, depends_on_id: str):
        if depends_on_id not in self.dependencies:
            self.dependencies.append(depends_on_id)

    def remove_dependency(self, depends_on_id: str):
        if depends_on_id in self.dependencies:
            self.dependencies.remove(depends_on_id)

    def add_tag(self, tag: str):
        if tag not in self.tags:
            self.tags.append(tag)
