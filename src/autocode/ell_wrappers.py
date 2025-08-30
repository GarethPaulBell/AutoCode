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

try:
    import ell
    HAVE_ELL = True
except ImportError:
    HAVE_ELL = False
    ell = None

try:
    import openai
    HAVE_OPENAI = True
except Exception:
    HAVE_OPENAI = False


class JuliaCodePackage(BaseModel):
    code: str = Field(description="The function.")
    tests: str = Field(description="A single test case for the function that uses @assert.")
    test_name: str = Field(description="A concise test name in snake_case.")
    test_description: str = Field(description="A concise test description.")
    input_types: str = Field(description="The input types for the function.")
    return_types: str = Field(description="The expected output types for the function.")
    short_description: str = Field(description="A short description of the function.")
    function_name: str = Field(description="The name of the function.")


# If ell is available try to construct an explicit client object (prefer OpenAI-based client)
_ell_client = None
if HAVE_ELL:
    # Prefer constructing the official OpenAI client if the package is available.
    if HAVE_OPENAI:
        try:
            from openai import OpenAI as OpenAIClient
            # Create a client using environment configuration (OPENAI_API_KEY etc.)
            _ell_client = OpenAIClient()
        except Exception:
            _ell_client = None

    # Fallback discovery for older ell versions or alternate providers
    if _ell_client is None:
        # Try a few common client constructor locations provided by ell wrappers
        tried = []
        for name in dir(ell):
            lname = name.lower()
            if 'openai' in lname:
                tried.append(name)
                cls = getattr(ell, name)
                try:
                    _ell_client = cls()  # attempt no-arg construction
                    break
                except Exception:
                    _ell_client = None
        # Search ell.clients submodule if present
        if _ell_client is None and hasattr(ell, 'clients'):
            for name in dir(ell.clients):
                lname = name.lower()
                if 'openai' in lname:
                    tried.append(f"clients.{name}")
                    cls = getattr(ell.clients, name)
                    try:
                        _ell_client = cls()
                        break
                    except Exception:
                        _ell_client = None
        # As a final attempt, if openai python package is present and ell exposes a generic client factory
        if _ell_client is None:
            try:
                _ell_client = openai
            except Exception:
                _ell_client = None


# Helper wrappers that apply decorators and attach the discovered client (if any).
def _wrap_complex(func, model: str, response_format=None):
    if not HAVE_ELL:
        return func
    client_kw = {'client': _ell_client} if _ell_client is not None else {}
    try:
        return ell.complex(model=model, response_format=response_format, **client_kw)(func)
    except Exception:
        # If decoration fails for any reason, return the plain function so code can still import/run
        return func


def _wrap_simple(func, model: str):
    if not HAVE_ELL:
        return func
    client_kw = {'client': _ell_client} if _ell_client is not None else {}
    try:
        return ell.simple(model=model, **client_kw)(func)
    except Exception:
        return func


# Define the functions and apply wrappers (so we can control client kw when available)
if HAVE_ELL:
    def _gen_impl(description: str):
        prompt = f"Write a Julia function to {description}"
        return prompt

    generate_julia_function = _wrap_complex(_gen_impl, model="gpt-5", response_format=JuliaCodePackage)

    def _modify_impl(description: str, function_code: str):
        prompt = f"Modify the BODY of the Julia function {function_code} based on the following description: {description}"
        return prompt

    modify_julia_function = _wrap_complex(_modify_impl, model="gpt-5", response_format=JuliaCodePackage)

    def _write_test_case_impl(function_name: str) -> str:
        prompt = (
            f"Write a Julia test file for the function `{function_name}`. "
            "Output ONLY valid Julia code. "
            "Do NOT include any markdown, triple backticks, comments, or explanations. "
            "Do NOT include the function definition, only the test code. "
            "Begin with 'using Test'."
        )
        return prompt

    write_test_case = _wrap_simple(_write_test_case_impl, model="gpt-4.1-mini")

    def _evaluate_output_impl(expected_output: str, actual_output: str) -> str:
        prompt = f"Does the actual output `{actual_output}` match the expected `{expected_output}`?"
        return prompt

    evaluate_output = _wrap_simple(_evaluate_output_impl, model="gpt-4.1-mini")

else:
    def generate_julia_function(description: str):
        raise NotImplementedError("Ell not available")

    def modify_julia_function(description: str, function_code: str):
        raise NotImplementedError("Ell not available")

    def write_test_case(function_name: str) -> str:
        raise NotImplementedError("Ell not available")

    def evaluate_output(expected_output: str, actual_output: str) -> str:
        raise NotImplementedError("Ell not available")
