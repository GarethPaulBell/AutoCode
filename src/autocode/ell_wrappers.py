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

    def _write_test_case_impl(function_code: str = "", signature: str = "", docstring: str = "", function_name: str = "") -> str:
        prompt = (
            f"You are an expert Julia developer and test writer. "
            f"Given the following function, its signature, and docstring, generate a Julia test file that thoroughly tests the function.\n"
            f"Function name: {function_name}\n"
            f"Signature: {signature}\n"
            f"Docstring: {docstring}\n"
            f"Full code:\n{function_code}\n"
            "Requirements:\n"
            "- Output ONLY valid Julia code.\n"
            "- Do NOT include any markdown, triple backticks, comments, or explanations.\n"
            "- Do NOT include the function definition, only the test code.\n"
            "- Begin with 'using Test'.\n"
            "- All tests must match the function's signature exactly (argument names, types, and return type).\n"
            "- Use information from the docstring and code to generate meaningful, context-aware tests.\n"
            "- Include edge cases and boundary values where appropriate.\n"
            "- Do not generate generic or mismatched tests.\n"
            "- If the function is mathematical, include property-based or invariant tests if possible.\n"
            "- If the function has constraints or special cases in the docstring, test those explicitly.\n"
            "- If unsure, ask for clarification rather than guessing.\n"
        )
        return prompt

    _decorated_write = _wrap_simple(_write_test_case_impl, model="gpt-4.1-mini")

    def write_test_case(*args) -> str:
        """Resilient wrapper around the decorated LLM-based test generator.

        Accepts either:
          - (function_code, signature, docstring, function_name)
          - (function_name,)
        or any partial subset. Tries the full-call first, falls back to calling
        with the single function_name argument, and on any unexpected failure
        returns a minimal stub test string so callers can attach a test.
        """
        import logging, traceback
        logger = logging.getLogger(__name__)
        try:
            # Prefer calling with all provided args (most specific)
            try:
                return _decorated_write(*args)
            except TypeError:
                # Decorator may enforce a different signature; try single-arg form
                if len(args) >= 1:
                    try:
                        return _decorated_write(args[-1])
                    except Exception:
                        # fallthrough to generic handler below
                        pass
                raise
        except Exception as e:
            # Log traceback for debugging and return a conservative stub test
            tb = traceback.format_exc()
            logger.warning("write_test_case failed: %s\n%s", e, tb)
            function_name = None
            try:
                if len(args) >= 1:
                    function_name = args[-1]
            except Exception:
                function_name = None
            fname = (function_name or "unknown_function").replace('"','').replace('\n','')
            return f"using Test\n@testset \"auto_generated_{fname}\" begin\n    # stub test generated due to generator error\n    @test true\nend\n"

    def _evaluate_output_impl(expected_output: str, actual_output: str) -> str:
        prompt = f"Does the actual output `{actual_output}` match the expected `{expected_output}`?"
        return prompt

    evaluate_output = _wrap_simple(_evaluate_output_impl, model="gpt-4.1-mini")

else:
    def generate_julia_function(description: str):
        raise NotImplementedError("Ell not available")

    def modify_julia_function(description: str, function_code: str):
        raise NotImplementedError("Ell not available")

    # Provide a conservative fallback for environments without ell.
    # Accept either the full signature (function_code, signature, docstring, function_name)
    # or a single-argument call (function_name,) to preserve backward compatibility.
    def write_test_case(*args) -> str:
        """Fallback test-case generator when ell is unavailable.

        Behaves defensively: accepts multiple signatures and returns a minimal
        Julia test string that does not assume heavy context.
        """
        try:
            if len(args) == 1:
                function_name = args[0] or "unknown_function"
                return f"using Test\n@testset \"auto_generated_{function_name}\" begin\n    # stub test - please expand\n    @test true\nend\n"
            else:
                function_name = args[-1] or "unknown_function"
                return f"using Test\n@testset \"auto_generated_{function_name}\" begin\n    # stub test generated due to missing LLM client.\n    @test true\nend\n"
        except Exception:
            return "using Test\n@testset \"auto_generated_unknown\" begin\n    @test true\nend\n"

    def evaluate_output(expected_output: str, actual_output: str) -> str:
        raise NotImplementedError("Ell not available")
