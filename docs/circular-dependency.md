# Circular Dependency & Recursion Detection

This document describes the basic tools added to detect and manage circular dependencies and simple recursion heuristics.

CLI commands
-----------

- detect-cycles
  - Usage: `python code_db_cli.py detect-cycles`
  - Description: Scans the function dependency graph and prints any cycles found. Each cycle is shown as a sequence of function IDs.

- detect-recursion
  - Usage: `python code_db_cli.py detect-recursion --function-id <FUNCTION_ID>`
  - Description: Performs a heuristic analysis for direct recursion (looks for `functionName(` patterns in the code) and checks for mutual recursion cycles involving this function.

- add-dependency
  - Usage: `python code_db_cli.py add-dependency --function-id <F> --depends-on-id <G>`
  - Description: Adds a dependency from F to G. The command will refuse to add a dependency that would create a circular dependency and will print a structured error explaining the reason and suggested remediation.

- remove-dependency
  - Usage: `python code_db_cli.py remove-dependency --function-id <F> --depends-on-id <G>`
  - Description: Removes the dependency edge from F -> G if present.

Programmatic API
----------------

These functions are available by importing `code_db` (top-level module):

- `code_db.find_cycles()` -> list of cycles (each cycle is a list of function IDs)
- `code_db.detect_recursion(function_id)` -> dict: `{"direct": bool, "mutual_cycles": [ ... ]}`
- `code_db.remove_dependency(function_id, depends_on_id)` -> structured dict response

Examples
--------

1. Detect cycles via CLI

```bash
python code_db_cli.py detect-cycles
```

2. Detect recursion for a function via Python

```python
import code_db
res = code_db.detect_recursion('<FUNCTION_ID>')
print(res)
```

Notes & Caveats
----------------
- Recursion detection is a lightweight heuristic. It detects direct recursion by simple pattern matching and mutual recursion via recorded dependencies. It may produce false positives (e.g. name appears in comments) and won't catch dynamically-invoked call sites.
- For more accurate static analysis, consider using `src/autocode/julia_parsers.py` to extract call sites and build a call graph.

Follow-ups
----------
- Add unit tests for `find_cycles` and `detect_recursion_in_function` (recommended).
- Expose the new APIs via the MCP server.
- Improve static analysis to derive call graphs from function code.
