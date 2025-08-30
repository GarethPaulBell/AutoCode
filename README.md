# AutoCode

AutoCode is a Julia function database with Model Context Protocol (MCP) tools
for AI-assisted generation, testing, and discovery. It stores Julia functions
with metadata and unit tests, runs tests via Julia, and offers both keyword and
semantic search. A per-project database is used by default; a shared/global DB
is available too.

## Features

- Store Julia functions with modules, tags, tests, and modification history
- Parse Julia files and import functions
- Generate functions and tests via AI (Ell / OpenAI integration optional)
- Run unit tests in Julia subprocesses with isolation
- Coverage report across functions
- Semantic search (OpenAI embeddings or hash fallback)
- Project DB by default, shared/global DB optional
- Persistence backends: Pickle (default) or SQLite, with migration
- MCP server exposing tools over JSON-RPC 2.0

## Project Structure

- `code_db.py`: High-level API for managing the function database
- `src/autocode/`: Modular components
  - `models.py`: Pydantic-free data classes and test execution
  - `julia_parsers.py`: Parse Julia functions and docstrings
  - `persistence.py`: DB resolution, project/shared config, pickle/SQLite
    backends
  - `semantic.py`: Semantic search helpers
  - `mcp_autocode_server.py`: MCP server exposing tools
  - `ui.py`, `ell_wrappers.py`: Presentation and AI helpers
- `code_db_cli.py`: CLI to interact with the database
- `tests/`: Unit tests for components

## Requirements

- Python 3.11+
- Julia in PATH (for test execution)
- Optional Python packages: openai, colorama, tabulate, ell

Tip: You can still run most features without OpenAI; semantic search falls
back to a hash-based pseudo-embedding.

## Database Management

AutoCode supports per-project and shared databases with optional SQLite.

- Default per-project path: `<project>/.autocode/code_db.pkl`
- Default shared path (Windows): `%APPDATA%/AutoCode/code_db.sqlite`
- Backends: `pickle` (default) or `sqlite`

Resolution order for DB path:

1) Explicit `--db-path` flag or `AUTOCODE_DB` env
2) `--db-mode`/`--backend` flags or `AUTOCODE_DB_MODE`/`AUTOCODE_BACKEND` env
3) `.autocode/config.json` (project) or `%APPDATA%/AutoCode/config.json` (shared)
4) Defaults

Backups and safety:

- Atomic writes to prevent corruption
- Lock files prevent concurrent writes
- Rotating backups in `<db_dir>/backups` (keep=5 by default)
- `vacuum-db` compacts SQLite or rewrites pickle files

Legacy fallback:

- If standardized path is absent, AutoCode will import legacy `code_db.pkl` or
  `code_db.sqlite` from the project root and save it into the standardized
  location at first load.

## CLI Quickstart

Use the CLI from the repo root.

- Show current DB status (defaults to project pickle):

  ```powershell
  python code_db_cli.py status-db
  ```

- Initialize shared SQLite DB and make it the default for this session:

  ```powershell
  $env:AUTOCODE_DB_MODE = 'shared'
  $env:AUTOCODE_BACKEND = 'sqlite'
  python code_db_cli.py init-db
  python code_db_cli.py status-db
  ```

- Migrate the current DB to SQLite (in place, changes filename to `.sqlite`):

  ```powershell
  python code_db_cli.py migrate-db --to sqlite
  ```

- Compact the database:

  ```powershell
  python code_db_cli.py vacuum-db
  ```

Note: Global flags must come before the subcommand, e.g.:

```powershell
python code_db_cli.py --db-mode shared --backend sqlite init-db
```

## Worked Example: Add, Test, Search

This end-to-end example adds a function, creates a unit test, runs tests, and
performs search.

1) Create a simple Julia function file `inc.jl`:

   ```julia
   function inc(x)
       return x + 1
   end
   ```

2) Import the function, associating it with the module `math_utils`:

   ```powershell
   python code_db_cli.py import-julia-file --file inc.jl --module math_utils
   ```

   Output includes the new function ID(s).

3) Add a unit test for the function. First save the following into `test_inc.jl`:

   ```julia
   @assert inc(1) == 2
   @assert inc(-5) == -4
   println("OK")
   ```

   Then attach the test (replace FUNC_ID with your ID):

   ```powershell
   python code_db_cli.py add-test --function-id FUNC_ID --name basic \
     --description "basic increments" --test-file test_inc.jl
   ```

4) Run tests for the function:

   ```powershell
   python code_db_cli.py run-tests --function-id FUNC_ID
   ```

   You'll see test results with status and output.

5) List functions in the module and perform keyword search:

   ```powershell
   python code_db_cli.py list-functions --module math_utils
   python code_db_cli.py search-functions --query inc
   ```

6) Generate coverage report:

   ```powershell
   python code_db_cli.py coverage-report
   ```

Optional: Generate function/test via AI

- Generate a new function from a description:

  ```powershell
  python code_db_cli.py generate-function --description "compute factorial" \
    --module math_utils
  ```

- Generate a test for a function (replace FUNC_ID):

  ```powershell
  python code_db_cli.py generate-test --function-id FUNC_ID --name auto \
    --description "auto test"
  ```

## MCP Server

Run the MCP server to expose tools to compatible clients:

```powershell
python src/autocode/mcp_autocode_server.py
```

Respect the DB selection using env vars beforehand, for example:

```powershell
$env:AUTOCODE_DB_MODE = 'project'
$env:AUTOCODE_BACKEND = 'sqlite'
$env:AUTOCODE_PROJECT_ROOT = (Get-Location).Path
python src/autocode/mcp_autocode_server.py
```

## Environment Variables

- `AUTOCODE_DB`: explicit path to DB file
- `AUTOCODE_DB_MODE`: `project` or `shared`
- `AUTOCODE_BACKEND`: `pickle` or `sqlite`
- `AUTOCODE_PROJECT_ROOT`: project root directory
- `AUTOCODE_SHARED_DIR`: override shared DB directory
- `OPENAI_API_KEY`: enable real embeddings

## Tips and Troubleshooting

- Ensure `julia` is in PATH (`julia --version`) for test execution
- If a test fails with syntax or load errors, review the test code; Julia
  errors are surfaced from stderr
- For Windows include paths, AutoCode normalizes paths in test scripts
- You can export/import functions and modules to JSON for portability

## Roadmap

- Richer schema with normalized tables for the SQLite backend
- Async test execution and streaming outputs in CLI
- Project.toml integration under `[tool.autocode]` to store DB preferences
- More robust semantic search and caching
