import ell
import subprocess
import tempfile
import os
import datetime
import uuid
from typing import Callable, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field

# Enums for Test Status
from enum import Enum

class TestStatusEnum(Enum):
    PASSED = "Passed"
    FAILED = "Failed"
    PENDING = "Pending"
    RUNNING = "Running"

# Data Models

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
        self.test_case = test_case  # Julia test case code as a string

    def run_test(self, function_code: str) -> TestResult:
        """
        Run the unit test by executing the function and test case in Julia.

        :param function_code: The Julia code of the function under test.
        :return: An instance of TestResult containing the outcome.
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
                status=status
            )

        except Exception as e:
            # Handle any unexpected exceptions during test execution
            print(f"Exception during test execution: {e}")
            return TestResult(
                test_id=self.test_id,
                function_id=self.function_id,
                actual_result=str(e),
                status=TestStatusEnum.FAILED
            )

        finally:
            # Clean up the temporary Julia script file
            os.remove(temp_filename)

    def __repr__(self):
        return (f"<UnitTest {self.test_id}: {self.name} for Function {self.function_id}>")

class Function:
    def __init__(self, name: str, description: str, code_snippet: str):
        self.function_id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.code_snippet = code_snippet
        self.creation_date = datetime.datetime.now()
        self.last_modified_date = self.creation_date
        self.unit_tests: List[UnitTest] = []

    def add_unit_test(self, test: UnitTest):
        self.unit_tests.append(test)
        print(f"Added UnitTest {test.test_id} to Function {self.function_id}")

    def modify_code(self, new_code_snippet: str):
        self.code_snippet = new_code_snippet
        self.last_modified_date = datetime.datetime.now()
        print(f"Function {self.function_id} code modified.")

    def __repr__(self):
        return (f"<Function {self.function_id}: {self.name}, "
                f"Last Modified: {self.last_modified_date.isoformat()}>")

class CodeDatabase:
    def __init__(self):
        self.db_name = "AutomatedDevDB"
        self.db_version = "1.0"
        self.created_date = datetime.datetime.now()
        self.last_modified_date = self.created_date
        self.functions: Dict[str, Function] = {}
        self.modifications: List[Modification] = []
        self.test_results: List[TestResult] = []

    def add_function(self, name: str, description: str, code_snippet: str) -> Function:
        func = Function(name, description, code_snippet)
        self.functions[func.function_id] = func
        self.last_modified_date = datetime.datetime.now()
        print(f"Added Function {func.function_id}: {name}")
        return func

    def add_unit_test(self, function_id: str, name: str, description: str, test_case: Callable[[Callable], bool]) -> Optional[UnitTest]:
        func = self.functions.get(function_id)
        if not func:
            print(f"Function ID {function_id} not found.")
            return None
        test = UnitTest(function_id, name, description, test_case)
        func.add_unit_test(test)
        self.last_modified_date = datetime.datetime.now()
        print(f"Added UnitTest {test.test_id} to Function {function_id}")
        return test

    def execute_tests(self):
        print("Executing all unit tests...")
        for func in self.functions.values():
            for test in func.unit_tests:
                result = test.run_test(func.code_snippet)
                self.test_results.append(result)
                print(f"Test Result: {result}")

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

    def __repr__(self):
        return (f"<CodeDatabase: {self.db_name} v{self.db_version}, "
                f"Created: {self.created_date.isoformat()}, "
                f"Last Modified: {self.last_modified_date.isoformat()}, "
                f"Functions: {len(self.functions)}>")

class JuliaCodePackage(BaseModel):
    code: str = Field(description="The function.")
    tests: str = Field(description="A single test case for the function that uses @assert.")
    test_name: str = Field(description="A concise test name in snake_case.")
    test_description: str = Field(description="A concise test description.")
    input_types: str = Field(description="The input types for the function.")
    return_types: str = Field(description="The expected output types for the function.")
    short_description: str = Field(description="A short description of the function.")
    function_name: str = Field(description="The name of the function.")


# Step 1: Generate a Julia function based on a description
@ell.complex(model="gpt-4o", response_format=JuliaCodePackage)
def generate_julia_function(description: str):
    """You are a Julia programmer, and you need to generate a function based on a description and a SINGLE test case."""
    prompt = f"Write a Julia function to {description}"
    # The decorator is assumed to send this prompt to GPT-4 and return the generated code
    return prompt

@ell.complex(model="gpt-4o", response_format=JuliaCodePackage)
def modify_julia_function(description: str, function_code: str):
    """You are a Julia programmer, and you need to modify a function based on the description. Maintain the existing function signature."""
    prompt = f"Modify the BODY of the Julia function {function_code} based on the following description: {description}"
        
    # The decorator is assumed to send this prompt to GPT-4 and return the generated code
    return prompt

# Step 2: Test the generated function
@ell.simple(model="gpt-4o")
def write_test_case(function_name: str) -> str:
    """Write a test case for the function."""
    prompt = f"Write a Julia test case to verify the `{function_name}` function"
    return prompt

# Step 3: Evaluate the output of the function
@ell.simple(model="gpt-4o")
def evaluate_output(expected_output: str, actual_output: str) -> str:
    """Evaluate whether the output matches the expectation."""
    prompt = f"Does the actual output `{actual_output}` match the expected `{expected_output}`?"
    return prompt

# Sample Usage

def test_function():
    code_db = CodeDatabase()
    print(code_db)

    # Step 1: Generate a Julia function
    description = "calculate the square of a number"
    print(f"Generating Julia function for: {description}")
    generated_code_message = generate_julia_function(description)
    generated_code = generated_code_message.parsed

    print(f"Generated Code:\n{generated_code.code}\n")
    print(f"Generated Tests:\n{generated_code.tests}\n")
    print(f"Generated Input Types:\n{generated_code.input_types}\n")
    print(f"Generated Return Types:\n{generated_code.return_types}\n")
    print(f"Short Description\n{generated_code.short_description}\n")
    print(f"Generated Function Name:\n{generated_code.function_name}\n")


    
    # Step 2: Add the function to CodeDatabase
    func = code_db.add_function(generated_code.function_name, generated_code.short_description,generated_code.code)
    
    # Step 3: Add unit tests for the function
    code_db.add_unit_test(func.function_id, generated_code.test_name, generated_code.test_description, generated_code.tests)
    # code_db.add_unit_test(func.function_id, "TestFactorial_Negative", "Test factorial with negative integer", test_calculate_sum_negative)
    
   
    # Step 4: Execute all tests
    print("\nExecuting Tests...")
    code_db.execute_tests()

   
    
    # Step 5: Modify the function (e.g., add logging)
    new_description = "take the absolute value of the number before squaring it"
    print(f"\nModifying Julia function: {description} to {new_description}")
    modified_code_message = modify_julia_function(new_description, generated_code.code)
    modified_code = modified_code_message.parsed.code
    print(f"Modified Code:\n{modified_code}\n")
    code_db.modify_function(func.function_id, "Alice", "Added logging to the factorial function", modified_code)
    
    ## Step 6: Add a new unit test after modification
    #code_db.add_unit_test(func.function_id, "TestFactorial_Logging", "Test factorial with logging", test_calculate_sum_logging)
    
    # Step 7: Execute all tests again to verify modifications
    print("\nExecuting Tests After Modification...")
    code_db.execute_tests()
    
    # Step 8: Display all test results
    print("\nAll Test Results:")
    for result in code_db.test_results:
        print(result)
    
    # Step 9: Display all modifications
    print("\nAll Modifications:")
    for mod in code_db.modifications:
        print(mod)

# Run the integrated process
if __name__ == "__main__":
    test_function()