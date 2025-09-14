
# AutoCode Development Roadmap (User-Tested Priorities)

This roadmap is now driven by real-world road testing and user pain points. Items below are prioritized based on actual workflow bottlenecks, missing features, and usability issues encountered by target users.

---

## Phase 1: Critical Usability & Robustness (Immediate)

- **[x] Fix Test Generation (Top Priority)**
    - Root-cause: AI test-generation tool (`mcp_autocode_generate_test`) currently crashes with missing-argument errors (example: "_write_test_case_impl() missing 3 required positional arguments: 'signature', 'docstring', and 'function_name'") which prevents automated test creation.
    - Goals:
        - Make test-generation a reliable, core feature: generated tests must match function signatures, include docstrings where available, and be attachable to functions as unit tests.
        - Add validation and graceful fallback: if auto-generation fails, return structured error with cause, stack, and suggested action (retry with more context / generate stub tests).
    - Acceptance criteria:
        - `mcp_autocode_generate_test` completes without uncaught exceptions on representative functions.
        - Generated tests run under the existing Julia test harness and attach to the function record.
    - Progress:
        - Standardized `_tool_generate_test` to always return structured responses with fields `{test_id, code, warning?, error?}` instead of raising for predictable failures.
        - Added unit tests under `tests/test_mcp_generate_test_responses.py` covering missing function, generator not available, generator TypeError fallback, generator exception, and failure to attach test. These tests validate the response shape and warnings.
        - Remaining: validate that generated tests run in the Julia harness for representative functions (end-to-end integration).

- **[x] Improve File Export / Import Reliability**
    - Root-cause: `mcp_autocode_generate_module_file` reported success but did not create the expected file on disk.
    - Goals:
        - Ensure export operations are atomic and verify file creation (write-to-temp + fsync + rename pattern) before returning success.
        - Return clear metadata on success (filepath, size, sha256) or a structured error if writing failed.
    - Acceptance criteria:
        - Exports create files in the workspace path when requested and the CLI/API returns the file path in the response.
        - CLI shows a follow-up hint (e.g., "Run `python code_db_cli.py open-file <path>` to view").
    - Notes (implementation progress):
        - Implemented atomic write pattern for exports: write-to-temp file in the destination directory, fsync, and atomic rename via os.replace.
        - `generate_module_file`, `export_module`, and `export_function` now return structured metadata on success: {"success": True, "filepath": ..., "size": ..., "sha256": ...}.
        - CLI (`code_db_cli.py`) now surfaces the returned filepath, size, sha256 and prints a follow-up hint to open the file.
        - Next steps: add a unit test that calls export functions and validates metadata (size & sha256), and improve MCP tool responses to always include structured error metadata on failure.

- **[ ] Error Handling & Verbose Feedback**
    - Root-cause: some tools return empty results or silent successes/failures with no actionable message.
    - Goals:
        - Adopt structured responses for all MCP tools: {ok: bool, result: ..., error: {type, message, suggested_action, details?}}
        - On failure, include short logs (truncated) and next steps. On success, include contextual metadata (created/modified paths, IDs, counts).
    - Acceptance criteria:
        - No tool returns bare "None" or empty payloads when an error is possible.
        - CLI surfaces the structured error in human-readable format and provides a machine-friendly --json flag.

- **[ ] Julia Language Compatibility & Linting**
    - Root-cause: generated Julia code uses constructs not supported by some Julia versions (e.g., JS-style regex flags like `/.../u`) and parameter names shadowing built-ins.
    - Goals:
        - Add a Julia-specific linter/compatibility checker that runs after generation and before commit/export. The checker should detect unsupported regex flags, naming conflicts, and common version incompatibilities.
        - Provide automatic fixes where safe (rename shadowing parameters with configurable suffix) and structured warnings otherwise.
    - Acceptance criteria:
        - Linter runs as part of generation and export workflows and blocks unsafe code by default.

- **[ ] Workflow & MCP Integration Improvements**
    - Root-cause: no direct way to run tests through MCP; manual extraction and local Julia runs are required.
    - Goals:
        - Add `mcp_autocode_run_tests` wiring that accepts function IDs or module names and streams test output back to the client.
        - Improve integration with Julia package system: allow passing a Project.toml context or adding `using` statements automatically in harnesses.
        - Improve default harness generation for benchmarking and test-running so most functions can be exercised automatically.
    - Acceptance criteria:
        - `mcp_autocode_run_tests` is available and successfully runs unit tests for a function/module and returns structured results.


---

## Phase 2: Workflow Intelligence & Advanced Search (Short-Term)

- **[ ] Code Similarity & Duplication Detection**
    - On adding a new function, automatically check for semantically similar functions in the database.
    - Warn and suggest reuse to prevent duplication.

- **[ ] Semantic Search Ranking & Filtering**
    - Improve semantic search to rank by true relevance and allow filtering by module/tag.
    - Make tag-based search and auto-suggestion prominent in the UI/CLI.

- **[ ] Tag System Enhancements**
    - Enforce or suggest tags on function creation. Allow searching, filtering, and reporting by tag.

- **[ ] Dependency Visualization & Analysis**
    - Generate dependency graphs with built-in viewer and cycle/bottleneck detection.
    - Summarize dependency health and highlight issues.

---

## Phase 3: Deep IDE Integration (Medium-Term)

- **[ ] VS Code Extension: Core Features**
    - **[ ] Custom Sidebar Panel:** Browse, search, and view functions/modules from the AutoCode database.
    - **[ ] Command Palette Integration:** Expose key actions like `search-functions` and `get-function`.

- **[ ] VS Code Extension: Editor Enhancements**
    - **[ ] CodeLens Actions:** In-editor buttons for `Save to AutoCode`, `Run AutoCode tests`, `View modification history`.
    - **[ ] Inline Diagnostics:** Show test coverage, last modification date, and other metadata directly in the editor.

---

## Phase 4: Advanced Refactoring & AI (Long-Term)

- **[ ] Automated Refactoring Tools**
    - **[ ] Safe Rename:** Rename a function and update all call sites in the database.
    - **[ ] Extract Function:** Select code and extract to a new function in the database.

- **[ ] Intelligent Autocompletion**
    - Use semantic search to suggest entire relevant functions as you type.

- **[ ] Enhanced Test Generation**
    - Support property-based, randomized, and edge-case test generation for Julia and future languages.

---

## Future Vision: Polyglot & Extensibility

- **[ ] Pluggable Language Architecture**
    - Refactor core logic to be language-agnostic. Isolate language-specific components into plugins.

- **[ ] Add Python Support**
    - Implement a Python plugin (parser, test runner, etc.) as a proof-of-concept for polyglot support.
