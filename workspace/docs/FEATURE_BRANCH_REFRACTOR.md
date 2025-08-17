# Feature branch: refactor/split-code_db

Goal

- Break `code_db.py` into smaller, well-scoped modules to improve maintainability and enable incremental refactors without breaking the codebase.

Branch name

- `refactor/split-code_db`

Scope (first pass)

1. Extract models and simple data classes (no external subprocess calls):
   - `Function`, `UnitTest`, `TestResult`, `Modification`, `Module` → `src/autocode/models.py`
2. Extract Julia parsing utilities (pure Python helpers):
   - `parse_julia_file`, `parse_julia_function`, `extract_julia_docstring` → `src/autocode/julia_parsers.py`
3. Add import shims in `code_db.py` that re-export names during the transition to avoid breaking imports.

Why these first

- Models and parsers are low-risk: they are mostly pure Python and have few external dependencies. Moving them first gives clear testable milestones.

Step-by-step plan

1. Create branch: `git checkout -b refactor/split-code_db`.
2. Add `src/autocode/__init__.py` (package) if not already present.
3. Implement `src/autocode/models.py` and move model classes. Add `from .models import *` shim in `code_db.py`.
4. Run tests: `python -m pytest -q` and `python -c "import code_db; code_db.run_tests()"` (or the project's test wrapper).
5. Fix import paths and adjust any relative references.
6. Repeat for `julia_parsers.py`.
7. Commit each extraction with a focused message:
   - `refactor(models): extract models to src/autocode/models.py and add shim`
   - `refactor(parsers): extract julia parsers to src/autocode/julia_parsers.py and add shim`
8. When all pieces moved and imports updated across the repo, remove shims and tidy `code_db.py`.

Testing and validation

- Run full test suite after each commit.
- Smoke test the MCP server and CLI: run `mcp_autocode_server.py` ping and sample `tools/call` requests.

Rollback and safety

- Keep changes small and atomic. If tests fail, revert the offending commit and fix imports in a dedicated follow-up commit.
- Push the branch early and open a draft PR for CI feedback.

PR checklist

- All tests pass locally.
- Linting and type checks (if present) pass.
- `CHANGELOG` or PR description documents behavioral changes and migration notes.

If you want, I can start by creating `src/autocode/models.py` and a shim in `code_db.py` now and run tests. Which step should I take first?
