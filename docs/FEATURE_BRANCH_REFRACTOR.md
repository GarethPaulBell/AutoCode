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

Progress so far

- Branch and commits
  - Work is being performed on branch `sql-lite-db` (refactor commits were made and later merged into `main` during an earlier workflow). The in-progress refactor is tracked in this repository.

- Files created / extracted
  - `src/autocode/models.py` — extracted model and data classes (`Function`, `UnitTest`, `TestResult`, `Modification`, `Module`).
  - `src/autocode/julia_parsers.py` — extracted Julia parsing helpers (`parse_julia_file`, `parse_julia_function`, `extract_julia_docstring`).
  - `src/autocode/persistence.py` — extracted save/load helpers (`save_db(db, path=None)`, `load_db(path=None)`) and `DB_PATH` constant.
  - Added `docs/DEVELOPER_GUIDE.md` and expanded `docs/README.md` with MCP quickstart notes.

- Code changes and compatibility shims
  - Added import shims in `code_db.py` to re-export names from the new modules so existing imports continue to work during the transition.
  - A backward-compatible wrapper for the previous zero-argument `save_db()`/`load_db()` API was added in `code_db.py` to delegate to `src.autocode.persistence` and avoid runtime breakage.

- Other changes
  - Fixed an initialization bug in `mcp_autocode_server.py` (ensures attributes are initialized before tool registration) and validated the server ping.
  - Generated several sample functions and tests via the MCP server; these were saved into the project's DB (`code_db.pkl`).
  - Updated a failing unit test stored in the DB (changed to assert on the returned Dict from `show_fields`) and re-ran tests successfully for that case.
  - Added `workspace/.venv/` to `.gitignore` and untracked the virtualenv to allow merges on Windows (avoids file-lock issues for `python.exe`).

- Test status (latest run)
  - `python -c "import json,code_db; print(json.dumps(code_db.run_tests(), ensure_ascii=False))"` — reported 3 tests run and passed.
  - `python -m pytest -q` — returned no collected tests in this run and exited with code 1 (investigation pending; this is likely because the project's test-runner is used instead of collecting pytest-style tests in the workspace layout).

Known issues / risks

- Refactor in-progress: many parts of `code_db.py` still remain in place and rely on backward-compatible shims. Continue to migrate pieces incrementally and run tests after each change.
- Persistence API: `src/autocode/persistence.save_db` targets an explicit `db` argument; a shim wrapper was added to preserve old zero-argument semantics. Ensure there are no remaining calls that bypass the shim or expect different behavior.
- Test discovery: pytest returned no tests in the last run. Confirm test locations and pytest collection rules; adapt or add pytest-compatible tests if desired.

Next steps

1. Continue extracting low-risk modules (CLI helpers, persistence internals, test orchestration) one at a time with shims and run tests after each extraction.
2. Consolidate and remove shims once the repo imports are updated across all callers.
3. Address pytest collection behavior if the repo should run tests via `pytest` directly (adjust `tests/` or `conftest.py` as needed).
4. Run full CI (or locally repeat the project test-runner plus `pytest`) before opening a PR.

If you want I can:

- Re-run the full test suite now and show the full pytest output.
- Continue with the next extraction step (pick a target file to move).
- Create a small checklist PR draft that documents what remains to be moved.

Which would you like next?
