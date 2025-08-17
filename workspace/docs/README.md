# Project Documentation Directory

This folder groups all human-authored documentation for the project.

Files:

- `spec.md`: Original CLI specification for the code database.
- `JSON_FORMAT_EXAMPLES.md`: Examples of JSON import/export structures.
- `SQLMODEL_MIGRATION_SUMMARY.md`: Summary of the pickle -> SQLModel migration.

Conventions:

- Add new conceptual or design docs here.
- Prefer one topic per file; use concise, task-focused titles.
- Keep large historical notes in a `/docs/archive` subfolder if they become stale.

Next Candidates:

- `ARCHITECTURE.md` (high-level module boundaries once refactored into `src/`)
- `CONTRIBUTING.md` (workflow, code style, test strategy)
- `ROADMAP.md` (planned refactors & feature milestones)

---

## MCP server & testing (quickstart)

The project provides a minimal Model Context Protocol (MCP) server that exposes the code DB operations as JSON-RPC tools. This is useful for integrating with an MCP-compatible client or for programmatic automation.

Key files:

- `mcp_autocode_server.py` — lightweight MCP server (implements `tools/list`, `tools/call`, and streaming support for `generate_function` and `run_tests`).
- `code_db.py` — core database and generation/test execution logic.

Basic usage (PowerShell):

- Start the MCP server:

```powershell
python .\mcp_autocode_server.py
```

- Ping the server (example):

```powershell
echo '{"jsonrpc":"2.0","id":1,"method":"ping"}' | python .\mcp_autocode_server.py
```

- Call the `tools/list` or invoke a tool (examples):

```powershell
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python .\mcp_autocode_server.py

echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_functions","arguments":{}}}' | python .\mcp_autocode_server.py
```

Streaming tools (e.g. `generate_function`, `run_tests`) will emit `tools/stream` events from the server. An MCP client can listen for these events to receive progress updates and per-test results in real time.

Running tests locally (Python wrapper):

The test execution harness runs Julia to execute unit tests attached to functions. To run all tests from Python:

```powershell
python -c "import json,code_db; print(json.dumps(code_db.run_tests(), ensure_ascii=False))"
```

Julia requirement:

- The test runner invokes the `julia` executable. Ensure Julia is installed and up to date (the repo's tests may require a recent 1.11.x release). If you use `juliaup` on Windows, update with:

```powershell
juliaup update
```

Notes on failures:

- The MCP server returns failing test results (and stream events) so an MCP client can react (display failures, request fixes, re-run, etc.). The project logs MCP activity to `autocode_mcp.log` by default — configure the path with the `MCP_AUTOCODE_LOG` environment variable.

Generated functions and modules:

- The code DB supports programmatic generation of functions and tests (see CLI wrappers). Generated functions are stored in the DB and can be listed with the `list_functions` tool.

If you'd like, I can add a dedicated `CONTRIBUTING.md` or a step-by-step developer guide with examples for common workflows (run server, generate function, run streamed tests, export/import).
