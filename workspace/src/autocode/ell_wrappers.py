"""ELL/ell wrappers and GPT helpers extracted from `code_db.py`.

Exports:
- JuliaCodePackage (pydantic model)
- generate_julia_function
- modify_julia_function
- write_test_case
- evaluate_output

This keeps the top-level `code_db` module small and delegates AI/ell logic to a focused module.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
import ell


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
