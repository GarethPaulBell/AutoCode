# Developer Guide — common workflows

This guide provides concise, runnable steps for common developer tasks: setting up the workspace, running the MCP server, generating functions, running tests (including streamed test execution), exporting/importing, and committing changes.

Prerequisites

- Python 3.11 (used for tooling in this repo).
- Julia (for running generated unit tests). On Windows, use `juliaup` to manage versions.

Quick workspace setup

1. Create or activate a Python virtualenv (optional but recommended):

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt  # if present
   ```

2. Ensure Julia is installed and up to date (tests require a recent 1.11.x):

   ```powershell
   julia --version
   juliaup update
   ```

Run the MCP server (local testing)

- Start the server (stdio JSON-RPC):

  ```powershell
  python .\mcp_autocode_server.py
  ```

- Ping the server (quick check):

  ```powershell
  echo '{"jsonrpc":"2.0","id":1,"method":"ping"}' | python .\mcp_autocode_server.py
  ```

- List available tools:

  ```powershell
  echo '{"jsonrpc":"2.0","id":10,"method":"tools/list"}' | python .\mcp_autocode_server.py
  ```

Invoke tools (examples)

- List functions via the MCP `tools/call` API:

  ```powershell
  echo '{"jsonrpc":"2.0","id":11,"method":"tools/call","params":{"name":"list_functions","arguments":{}}}' | python .\mcp_autocode_server.py
  ```

- Generate a function (non-streaming call will return created function metadata; streaming variant available):

  ```powershell
  echo '{"jsonrpc":"2.0","id":12,"method":"tools/call","params":{"name":"generate_function","arguments":{"description":"Merge two sorted arrays into a single sorted array","module":"array_utils"}}}' | python .\mcp_autocode_server.py
  ```

Streamed operations

- Some tools support streaming (caller sends `params.stream=true`). When streaming, the server returns a short JSON-RPC success and then emits `tools/stream` events with `chunk` and `complete` events. Example (PowerShell):

  ```powershell
  echo '{"jsonrpc":"2.0","id":20,"method":"tools/call","params":{"name":"run_tests","arguments":{},"stream":true}}' | python .\mcp_autocode_server.py
  ```

  An MCP client should read lines from the server stdout and handle `method: "tools/stream"` events to receive progress and per-test results.

Run tests locally (Python wrapper)

- The DB provides a Python entrypoint to run tests; this will invoke Julia for each unit test:

  ```powershell
  python -c "import json,code_db; print(json.dumps(code_db.run_tests(), ensure_ascii=False))"
  ```

- If you see Julia-related errors, run `juliaup update` (Windows) or install/update Julia via your package manager.

Generating functions via CLI (helper scripts)

- The repo includes CLI helpers (see `code_db_cli.py`) to generate functions or tests from descriptions. Examples:

  ```powershell
  python code_db_cli.py generate-function --description "merge two sorted arrays into a single sorted array" --module "array_utils"
  python code_db_cli.py generate-test --function-id <FUNCTION_ID> --name "basic" --description "simple smoke test"
  ```

Export / import

- Export a function to JSON (useful for review or moving between projects):

  ```powershell
  python code_db_cli.py export-function --function-id <FUNCTION_ID> --file exported_function.json
  ```

- Import a previously exported function:

  ```powershell
  python code_db_cli.py import-function --file exported_function.json
  ```

Committing changes

- The code DB is persisted to `code_db.pkl` by default. Generated functions/tests and other state changes must be committed to git if you want them tracked alongside code changes.

  ```powershell
  git add -A
  git commit -m "Describe changes"
  ```

Notes and developer tips

- Streaming: the MCP server's stream events are JSON objects with form:

  ```json
  { "jsonrpc": "2.0", "method": "tools/stream", "params": { "callId": <id>, "event": "chunk"|"complete"|"error", "data": {...} } }
  ```

- Tests run in temporary Julia scripts; look at stdout/stderr captured by the runner for debugging failing tests.
- If you need the server to be long-running for an MCP client, launch it directly and connect via stdio; do not pipe a single request as that terminates the server when the pipe closes.

Further additions

- I can expand this into a dedicated `CONTRIBUTING.md` that covers code style, tests, workflow for accepting AI-generated fixes, and CI recommendations. Say the word and I will add it.
