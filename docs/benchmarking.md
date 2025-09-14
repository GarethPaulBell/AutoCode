# Benchmarking inputs

Expected input types

- The `benchmark-function` command expects a path to a Julia source file containing executable code that calls the target function under test. The file should be UTF-8 encoded and non-empty.
- Typical content: a small script that constructs appropriate arguments and calls the function, for example:

```julia
# example_input.jl
args = (1, 2)
println(my_function(args...))
```

Validation and error messages

- EmptyInputFile: The input file exists but is empty. Suggested action: provide a file with a call to the function.
- InputFileNotFound: The given input file path does not exist. Suggested action: check the path or create the input file.
- InputDoesNotCallFunction: The input file does not appear to call the requested function (heuristic check). Suggested action: add a line that calls the function, e.g. `println(my_function(...))`.
- FunctionNotFound: The requested function ID does not exist in the DB. Suggested action: verify the function ID or add the function first.
- JuliaSyntaxError / JuliaMethodError / JuliaLoadError: Julia-side errors detected when executing the script. Suggested actions are included in the returned error response and `stderr` contains the Julia output for diagnostics.

How to run (CLI)

Use the CLI command:

```powershell
python code_db_cli.py benchmark-function --function-id <FUNCTION_ID> --input-file path/to/example_input.jl --iterations 5
```

If the tool returns an error dict, it will include `error_type`, `message`, and `suggested_action`. Use these to resolve the issue before re-running the benchmark.
