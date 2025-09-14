# Benchmarking inputs

Expected input types


```julia
# example_input.jl
args = (1, 2)
println(my_function(args...))
```

Validation and error messages


How to run (CLI)

Use the CLI command:

```powershell
python code_db_cli.py benchmark-function --function-id <FUNCTION_ID> --input-file path/to/example_input.jl --iterations 5
```

If the tool returns an error dict, it will include `error_type`, `message`, and `suggested_action`. Use these to resolve the issue before re-running the benchmark.
# Benchmarking inputs and validation

This document describes what input the benchmarking tool expects, how inputs are validated, and the error messages you may receive when something goes wrong. The goal is to provide clear, actionable feedback so automated agents and human users can fix issues quickly.

## Accepted input types

- Script file (recommended): a path to a Julia source file (UTF-8) which runs the target function under test. The file must contain code that constructs arguments and invokes the function. Example:

```julia
# example_input.jl
args = (1, 2)
println(my_function(args...))
```

- Inline code snippet (agent-driven): some clients may pass a short Julia snippet or payload instead of a filepath. The server will validate that the snippet is parseable and calls the function.

- Function-only benchmark: in some workflows you may want to benchmark a stored function directly. In this case pass the `--function-id` and omit `--input-file`; the server will attempt to run a small harness calling the function if a default harness exists.

## Validation checks and structured error responses

When benchmarking runs, the server performs a sequence of validation checks. If a check fails, the server returns a structured error with `error_type`, `message`, and `suggested_action` fields. Common error types:

- `InputFileNotFound`: The specified input file path does not exist. Suggested action: verify the path or create the input file.
- `EmptyInputFile`: The input file exists but is empty. Suggested action: provide a valid Julia script which calls the function.
- `InputDoesNotCallFunction`: Heuristic detection shows the input does not call the requested function. Suggested action: add an explicit call (e.g. `println(my_function(...))`) or pass a harness that imports the function's module.
- `FunctionNotFound`: The `function_id` provided is not present in the database. Suggested action: check the ID, or add/import the function first.
- `InvalidInputType`: The provided input is not a valid file path or recognized snippet. Suggested action: supply a file path or a valid Julia snippet.
- `JuliaSyntaxError` / `JuliaMethodError` / `JuliaLoadError`: Errors thrown by Julia when loading or executing the harness/script. Suggested action: inspect the returned `stderr`/`stdout` and fix syntax or runtime issues. The server includes the captured Julia error output.

Example error response (JSON-like):

```json
{
	"ok": false,
	"error_type": "InputDoesNotCallFunction",
	"message": "The input file does not appear to call function 'my_function'",
	"suggested_action": "Add a call to my_function in the input file, e.g. println(my_function(...))"
}
```

## Best practices for harness scripts

- Keep the harness small and focused — only construct inputs and call the function. Avoid long-running initialization or interactive prompts.
- Ensure deterministic inputs for consistent benchmarks.
- If the function relies on specific packages, include `using` statements at the top of the harness so the Julia environment can load dependencies.

## CLI usage

PowerShell example:

```powershell
python code_db_cli.py benchmark-function --function-id <FUNCTION_ID> --input-file path/to/example_input.jl --iterations 5
```

If the server supports benchmarking by function ID only (no input file), omit `--input-file` and ensure a default harness exists for the function.

## Notes for integrators / agents

- The benchmarking endpoint should return structured JSON so agents can programmatically decide next steps (retry with a corrected harness, report failure, or abort).
- If a harness fails due to missing packages, the server should include a `dependencies` hint in the error (if available) listing missing packages.

## Implementation checklist for the MCP server

- Validate input file path and contents prior to executing Julia.
- Heuristically verify that the harness calls the requested function (or allow an explicit `--force` flag to skip heuristics).
- Return consistent, structured errors with `error_type`, `message`, and `suggested_action`.
- Optionally include captured `stderr` and a short snippet of failing code in responses.
