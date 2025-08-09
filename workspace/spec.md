# Specification: CLI Interface for `code_db.py`

## Overview
This document specifies the requirements and design for a Command-Line Interface (CLI) to interact with `code_db.py`, a Python module for managing a code database (functions, tests, results, modifications, and modules).

## Requirements
- The CLI must allow users to add, modify, list, and query functions in the code database.
- Users must be able to add and run unit tests, view test results, and track modifications.
- The CLI must support organizing functions into modules (tags) and querying by module.
- The CLI should provide clear help messages and error handling.
- All operations should be accessible via subcommands and options.
- The CLI must support dependency tracking between functions.

## Command Structure

```
code_db_cli.py <command> [options]
```

### Core Commands

- `add-function`  
  Add a new function to the database.
  - Options: `--name`, `--description`, `--code-file`, `--modules` (comma-separated list)
- `list-functions`  
  List all functions with summary info.
  - Options: `--module` (filter by module name)
- `show-function`  
  Show details for a specific function.
  - Options: `--id`
- `modify-function`  
  Modify an existing function.
  - Options: `--id`, `--modifier`, `--description`, `--code-file`
- `add-test`  
  Add a unit test to a function.
  - Options: `--function-id`, `--name`, `--description`, `--test-file`
- `run-tests`  
  Run all or specific tests.
  - Options: `--function-id` (optional)
- `show-results`  
  Show test results.
  - Options: `--function-id` (optional)
- `list-modifications`  
  List modifications for a function.
  - Options: `--function-id`
- `list-modules`  
  List all modules (tags) in the database.
- `add-function-to-module`  
  Add an existing function to a module.
  - Options: `--function-id`, `--module`
- `generate-function`  
  Generate a new Julia function from a description and add it to the database.
  - Options: `--description`, `--module` (optional)
- `generate-test`  
  Generate a unit test for a function using AI.
  - Options: `--function-id`, `--name`, `--description`
- `purge-tests`  
  Remove all tests and test results for a function.
  - Options: `--function-id`
- `fix-test`  
  Regenerate a failing test for a function using AI.
  - Options: `--function-id`, `--test-id`
- `export-function`  
  Export a function (with tests and metadata) to a JSON file.
  - Options: `--function-id`, `--file`
- `import-function`  
  Import a function (with tests and metadata) from a JSON file.
  - Options: `--file`
- `export-module`  
  Export a module (all functions and tests) to a JSON file.
  - Options: `--module`, `--file`
- `import-module`  
  Import a module (all functions and tests) from a JSON file.
  - Options: `--file`
- `generate-module-file`  
  Output all functions in a module as a single Julia file, optionally with tests.
  - Options: `--module`, `--file`, `--with-tests` (flag, optional)
- `add-dependency`  
  Add a dependency from one function to another.
  - Options: `--function-id`, `--depends-on-id`
- `list-dependencies`  
  List all dependencies for a function.
  - Options: `--function-id`
- `visualize-dependencies`  
  Output a DOT/Graphviz file visualizing function dependencies.
  - Options: `--file` (output file, e.g. dependencies.dot)
- `coverage-report`  
  Show test coverage for all functions.
  - Options: none

### Global Options

- `-h`, `--help`  
  Show help message.

## Example Usage

```sh
python code_db_cli.py add-function --name "symbolic_derivative" --description "Computes symbolic derivative..." --code-file symbolic_derivative.jl --modules "math,calculus"
python code_db_cli.py list-functions
python code_db_cli.py list-functions --module "math"
python code_db_cli.py list-modules
python code_db_cli.py add-function-to-module --function-id FUNC123 --module "algorithms"
python code_db_cli.py show-function --id FUNC123
python code_db_cli.py add-test --function-id FUNC123 --name "test_derivative" --description "Test for derivative" --test-file test_derivative.jl
python code_db_cli.py run-tests --function-id FUNC123
python code_db_cli.py show-results --function-id FUNC123
python code_db_cli.py generate-function --description "merge two sorted arrays into a single sorted array" --module "array_utils"
python code_db_cli.py export-function --function-id FUNC123 --file exported_function.json
python code_db_cli.py import-function --file exported_function.json
python code_db_cli.py export-module --module "array_utils" --file exported_array_utils.json
python code_db_cli.py import-module --file exported_array_utils.json
python code_db_cli.py generate-module-file --module "array_utils" --file array_utils.jl --with-tests
python code_db_cli.py add-dependency --function-id FUNC123 --depends-on-id FUNC456
python code_db_cli.py list-dependencies --function-id FUNC123
python code_db_cli.py visualize-dependencies --file dependencies.dot
python code_db_cli.py coverage-report
```

## Extensibility Notes

- The CLI should be implemented using Python's `argparse` or `click` for easy extension.
- New commands (e.g., export, import, search) can be added as subcommands.
- The CLI should be modular, with each command mapped to a function in `code_db.py`.
- Support for additional languages or test frameworks can be added via plugins or configuration.
- The module/tag system allows for flexible grouping and querying of functions for use at the command line.

## Cool Ideas for Future Functionality

- **Export/Import Functions and Modules**  
  Already implemented: Export/import functions or modules (with tests and metadata) as JSON files for sharing and backup.

- **Search and Filter**  
  Add a `search-functions` command to search by keyword in name, description, or code.  
  Allow filtering by creation/modification date, test status, or modifier.

- **Module Bundling**  
  Add a `generate-module-file` command to output all functions in a module as a single Julia file, optionally with tests.

- **Function/Module Documentation**  
  Generate Markdown or HTML documentation for a function or module, including code, description, tests, and modification history.

- **Function Versioning**  
  Track and display version history for each function, with the ability to revert to previous versions.

- **Test Coverage Reporting**  
  Show which functions have tests, how many tests, and their pass/fail rates.  
  Add a `coverage-report` command.

- **Tagging and Metadata**  
  Allow arbitrary tags (not just modules) for functions (e.g., "experimental", "deprecated", "fast", "pure").  
  Add a `list-tags` and `add-tag` command.

- **Interactive Shell**  
  Launch an interactive shell (`code_db_cli.py shell`) for exploring and manipulating the database with tab completion.

  **Requirements:**
  - The CLI must provide a `shell` subcommand that launches an interactive prompt.
  - The shell should support all major commands (add-function, list-functions, show-function, add-test, run-tests, etc.) as shell commands.
  - Tab completion for commands and arguments (e.g., function IDs, module names).
  - Command history and editing (arrow keys, etc.).
  - Inline help (`help` or `?` command).
  - Graceful exit (`exit` or `quit` command).
  - Error handling and informative feedback for invalid commands.
  - Optional: colored output for better readability.

  **Example Usage:**
  ```
  $ python code_db_cli.py shell
  Welcome to the code_db interactive shell. Type help or ? to list commands.

  code_db> list-functions
  ID: FUNC123 | Name: symbolic_derivative | Desc: Computes symbolic derivative... | Modules: math, calculus

  code_db> show-function --id FUNC123
  ID: FUNC123
  Name: symbolic_derivative
  Description: Computes symbolic derivative...
  Code:
  function symbolic_derivative(...)
      ...
  end

  code_db> add-function --name foo --description "Example function" --code-file foo.jl
  Function added with ID: FUNC456

  code_db> run-tests --function-id FUNC456
  Test: TEST789 | Status: Passed | Output: Test Passed.

  code_db> help
  Available commands:
    add_function
    add_function_to_module
    add_test
    add_dependency
    coverage_report
    export_function
    export_module
    fix_test
    generate_function
    generate_module_file
    generate_test
    import_function
    import_module
    list_dependencies
    list_functions
    list_modifications
    list_modules
    purge_tests
    run_tests
    search_functions
    show_function
    show_results
    visualize_dependencies
    exit
    help
    quit

  code_db> exit
  Exiting shell.
  ```

- **Integration with Git**  
  Optionally sync the database or exported modules with a Git repository for version control.

- **Dependency Tracking**  
  Allow functions to declare dependencies on other functions in the database.  
  Add a `list-dependencies` and `visualize-dependencies` command.

  Additional features:

  Command | Purpose | Key Options | Why it matters to an LLM workflow
lint-function | Run a style/​static‑analysis linter on function code | --function-id, --fix (auto‑apply) | Feeds clean, idiomatic code back to the model; reduces hallucinated style drift
security-audit | Scan for known vulnerabilities / insecure patterns | `--scope [function | module], --report-file`
benchmark-function | Time and memory micro‑benchmark | --function-id, --input-file, --iterations | Lets the model iteratively optimize for speed or footprint
optimize-function | Ask LLM to rewrite for performance while preserving tests | --function-id, `--strategy [speed | memory]`
refactor-module | Cohesive refactor (rename, extract, dedup) guided by LLM | --module, --plan-only | Keeps growing codebases maintainable
generate-docs | Produce Markdown/HTML docs incl. examples & dependency graph | --scope, `--format [md | html], --file`
semantic-search | Embedding‑based fuzzy lookup over names, docs & code | --query, --top-k | Finds relevant snippets beyond exact keywords
ask-llm | Chat with the model about a function/module context | --function-id or --module, interactive prompt | Quick Q&A without leaving CLI
property-test | Generate Hypothesis/QuickCheck‑style property tests | --function-id, --num-tests | Surfaces edge cases traditional unit tests miss
complexity-report | Cyclomatic & cognitive complexity metrics | --scope, --threshold | Early warning for functions that will confuse the model later
dead-code-prune | Detect & flag unused functions via dependency graph | --auto-remove (optional) | Keeps DB lean; improves generation accuracy
sync-git | Import/export functions directly from a Git repo branch | --repo, --branch, `--direction [pull | push]`
ci-hook | Emit shell commands for test/​lint/​coverage to drop into CI | --file .ci_snippet.sh | Operationalizes model‑driven quality gates
schedule-tests | Cron‑like scheduling for run-tests / coverage-report | --cron "0 2 * * *" | Continuous regression guardrails
visualize-history | Generate a time‑series graph of modifications & test status | --function-id, --file history.svg | Spot trends & instability at a glance
license-check | Ensure generated code complies with chosen license list | --scope, --allow MIT,Apache-2.0 | Prevents accidental license contamination
multi-language-support | Set default lang per function and invoke correct toolchain | `--language [julia | python