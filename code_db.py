import ell
import subprocess
import tempfile
import os
import datetime
import uuid
from typing import Callable, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field
from colorama import Fore, Style, init
from tabulate import tabulate
init()

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
    # Collect data for the table
    table_data = []
    for func in code_db.functions.values():
        last_test_result = get_last_test_result(code_db, func.function_id)
        dot_color = get_dot_color(last_test_result)
        table_data.append([func.function_id, func.name, func.description, dot_color])

    # Define table headers
    headers = [f"{Fore.CYAN}Function ID{Style.RESET_ALL}", f"{Fore.CYAN}Name{Style.RESET_ALL}", f"{Fore.CYAN}Description{Style.RESET_ALL}", f"{Fore.CYAN}Status{Style.RESET_ALL}"]

    # Print the table
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

                
# Sample Usage

def test_function():
    code_db = CodeDatabase()
    print(code_db)

    # Step 1: Generate a Julia function
    description = "calculate the factorial of a non-negative integer"
    print(f"Generating Julia function for: {description}")
    generated_code_message = generate_julia_function(description)
    generated_code = generated_code_message.parsed

    # Step 2: Add the function to CodeDatabase
    func = code_db.add_function(generated_code.function_name, generated_code.short_description, generated_code.code)
    
    # Step 3: Add unit tests for the function
    code_db.add_unit_test(func.function_id, generated_code.test_name, generated_code.test_description, generated_code.tests)
    
    # Step 4: Test-Fix Loop
    max_attempts = 5
    attempt = 0
    while attempt < max_attempts:
        print(f"\nAttempt {attempt + 1} of {max_attempts}")
        
        # Execute tests
        print("Executing Tests...")
        results = code_db.execute_tests()
        
        # Check if any tests failed
        failed_tests = [r for r in results if r.status == TestStatusEnum.FAILED]
        
        if not failed_tests:
            print("All tests passed!")
            break
            
        print(f"Failed tests: {len(failed_tests)}")
        for result in failed_tests:
            print(f"Test {result.test_id} failed: {result.actual_result}")
        
        # Ask AI to fix the code
        fix_description = f"Fix the function. Current tests failed with: {[r.actual_result for r in failed_tests]}"
        print(f"\nRequesting fix: {fix_description}")
        fixed_code_message = modify_julia_function(fix_description)
        fixed_code = fixed_code_message.parsed.code
        
        # Update function with fix
        code_db.modify_function(func.function_id, "AI", f"Fix attempt {attempt + 1}", fixed_code)
        
        attempt += 1
    
    if attempt == max_attempts:
        print("\nMaximum fix attempts reached without success")
    else:
        print(f"\nFixed in {attempt + 1} attempts")



# Run the integrated process
if __name__ == "__main__":
    test_function()