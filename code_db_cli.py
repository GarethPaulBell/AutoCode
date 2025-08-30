import argparse
import sys
import shlex
import cmd
import os, json, difflib
import subprocess
import pkg_resources
from pathlib import Path

from src.autocode.persistence import (
    init_db as db_init,
    status_db as db_status,
    migrate_db as db_migrate,
    vacuum_db as db_vacuum,
    unlock_db as db_unlock,
    resolve_db as db_resolve,
)

try:
    import code_db
except ImportError:
    print("Error: code_db.py module not found or import failed.")
    exit(1)

STATE_PATH = os.path.expanduser("~/.code_db_cli_state.json")

def _load_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"focus": {"function_id": None, "module": None}, "recent_functions": [], "pinned_functions": []}

def _save_state(state):
    try:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    except Exception:
        pass
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def _push_recent(function_id):
    state = _load_state()
    rec = state.get("recent_functions", [])
    if function_id:
        if function_id in rec:
            rec.remove(function_id)
        rec.insert(0, function_id)
        state["recent_functions"] = rec[:20]
        _save_state(state)

def _resolve_function_id(id_or_name):
    state = _load_state()
    if not id_or_name:
        return state.get("focus", {}).get("function_id")
    try:
        f = code_db.get_function(id_or_name)
        if f:
            return id_or_name
    except Exception:
        pass
    try:
        funcs = code_db.list_functions()
        candidates = [f for f in funcs if f.get("name","").lower() == str(id_or_name).lower()]
        if len(candidates) == 1:
            return candidates[0]["id"]
    except Exception:
        pass
    return id_or_name

def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error reading file '{path}': {e}")
        exit(1)

def parse_modules_arg(modules_arg):
    if not modules_arg:
        return []
    if isinstance(modules_arg, list):
        return modules_arg
    return [m.strip() for m in modules_arg.split(",") if m.strip()]

def main():
    parser = argparse.ArgumentParser(
        description="CLI for managing the code database via code_db.py"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- Global DB control flags (optional for all commands) ---
    parser.add_argument("--db-mode", choices=["project", "shared"], help="Select DB mode (per-project or shared)")
    parser.add_argument("--backend", choices=["pickle", "sqlite"], help="Persistence backend (pickle or sqlite)")
    parser.add_argument("--db-path", type=str, help="Explicit DB file path (overrides mode/backend resolution)")
    parser.add_argument("--project-root", type=str, help="Project root for project DB resolution")

    # add-function
    add_func = subparsers.add_parser("add-function", help="Add a new function to the database.")
    add_func.add_argument("--name", required=True, help="Function name.")
    add_func.add_argument("--description", required=True, help="Function description.")
    add_func.add_argument("--code-file", required=True, help="Path to file containing function code.")
    add_func.add_argument("--modules", required=False, help="Comma-separated list of module names.")

    # list-functions
    list_funcs = subparsers.add_parser("list-functions", help="List all functions.")
    list_funcs.add_argument("--module", required=False, help="Filter by module name.")
    list_funcs.add_argument("--tag", required=False, help="Filter by tag.")

    # show-function
    show_func = subparsers.add_parser("show-function", help="Show details for a specific function.")
    show_func.add_argument("--id", required=False, help="Function ID (defaults to focused).")

    # modify-function
    mod_func = subparsers.add_parser("modify-function", help="Modify an existing function.")
    mod_func.add_argument("--id", required=True, help="Function ID.")
    mod_func.add_argument("--modifier", required=True, help="Modifier name.")
    mod_func.add_argument("--description", required=True, help="Modification description.")
    mod_func.add_argument("--code-file", required=True, help="Path to file containing new function code.")

    # add-test
    add_test = subparsers.add_parser("add-test", help="Add a unit test to a function.")
    add_test.add_argument("--function-id", required=False, help="Function ID (defaults to focused).")
    add_test.add_argument("--name", required=True, help="Test name.")
    add_test.add_argument("--description", required=True, help="Test description.")
    add_test.add_argument("--test-file", required=True, help="Path to file containing test code.")

    # run-tests
    run_tests = subparsers.add_parser("run-tests", help="Run all or specific tests.")
    run_tests.add_argument("--function-id", required=False, help="Function ID (optional).")

    # show-results
    show_results = subparsers.add_parser("show-results", help="Show test results.")
    show_results.add_argument("--function-id", required=False, help="Function ID (optional).")

    # list-modifications
    list_mods = subparsers.add_parser("list-modifications", help="List modifications for a function.")
    list_mods.add_argument("--function-id", required=True, help="Function ID.")

    # list-modules
    subparsers.add_parser("list-modules", help="List all modules.")

    # add-function-to-module
    add_func_mod = subparsers.add_parser("add-function-to-module", help="Add a function to a module.")
    add_func_mod.add_argument("--function-id", required=True, help="Function ID.")
    add_func_mod.add_argument("--module", required=True, help="Module name.")

    # generate-function
    gen_func = subparsers.add_parser("generate-function", help="Generate a new Julia function from a description and add it to the database.")
    gen_func.add_argument("--description", required=True, help="Description of the function to generate.")
    gen_func.add_argument("--module", required=False, help="Module name to associate with the function.")

    # generate-test
    gen_test = subparsers.add_parser("generate-test", help="Generate a unit test for a function using AI.")
    gen_test.add_argument("--function-id", required=False, help="Function ID (defaults to focused).")
    gen_test.add_argument("--name", required=True, help="Test name.")
    gen_test.add_argument("--description", required=True, help="Test description.")

    # purge-tests
    purge_tests_cmd = subparsers.add_parser("purge-tests", help="Remove all tests and test results for a function.")
    purge_tests_cmd.add_argument("--function-id", required=True, help="Function ID.")

    # fix-test
    fix_test = subparsers.add_parser("fix-test", help="Regenerate a failing test for a function using AI.")
    fix_test.add_argument("--function-id", required=True, help="Function ID.")
    fix_test.add_argument("--test-id", required=True, help="Test ID to fix.")

    # export-function
    export_func = subparsers.add_parser("export-function", help="Export a function (with tests) to a JSON file.")
    export_func.add_argument("--function-id", required=True, help="Function ID to export.")
    export_func.add_argument("--file", required=True, help="Output JSON file.")

    # import-function
    import_func = subparsers.add_parser("import-function", help="Import a function (with tests) from a JSON file.")
    import_func.add_argument("--file", required=True, help="Input JSON file with function data. Must contain: name, description, code_snippet, modules (optional), tags (optional), unit_tests (optional array with name, description, test_case).")

    # export-module
    export_mod = subparsers.add_parser("export-module", help="Export a module (all functions) to a JSON file.")
    export_mod.add_argument("--module", required=True, help="Module name to export.")
    export_mod.add_argument("--file", required=True, help="Output JSON file.")

    # import-module
    import_mod = subparsers.add_parser("import-module", help="Import a module (all functions) from a JSON file.")
    import_mod.add_argument("--file", required=True, help="Input JSON file with module data. Must contain: module_name (string), functions (array of function objects with name, description, code_snippet, modules, tags, unit_tests).")

    # import-julia-file
    import_julia = subparsers.add_parser("import-julia-file", help="Import functions from a Julia (.jl) file.")
    import_julia.add_argument("--file", required=True, help="Input Julia (.jl) file to parse and import.")
    import_julia.add_argument("--module", required=False, help="Module name to use (defaults to parsed module name or filename).")
    import_julia.add_argument("--generate-tests", action="store_true", help="Auto-generate basic tests for imported functions using AI.")

    # search-functions
    search_funcs = subparsers.add_parser("search-functions", help="Search functions by keyword in name, description, or code.")
    search_funcs.add_argument("--query", required=True, help="Search keyword.")
    search_funcs.add_argument("--created-after", required=False, help="Only show functions created after this ISO date (e.g. 2024-06-01T00:00:00).")
    search_funcs.add_argument("--modified-after", required=False, help="Only show functions modified after this ISO date (e.g. 2024-06-01T00:00:00).")
    search_funcs.add_argument("--test-status", required=False, help="Only show functions whose last test result matches this status (Passed/Failed/Pending/Running).")

    # generate-module-file
    gen_mod_file = subparsers.add_parser("generate-module-file", help="Output all functions in a module as a single Julia file, optionally with tests.")
    gen_mod_file.add_argument("--module", required=True, help="Module name to output.")
    gen_mod_file.add_argument("--file", required=True, help="Output Julia file.")
    gen_mod_file.add_argument("--with-tests", action="store_true", help="Include unit tests in the output.")

    # add-dependency
    add_dep = subparsers.add_parser("add-dependency", help="Add a dependency from one function to another.")
    add_dep.add_argument("--function-id", required=True, help="Function ID that depends on another.")
    add_dep.add_argument("--depends-on-id", required=True, help="Function ID to depend on.")

    # list-dependencies
    list_deps = subparsers.add_parser("list-dependencies", help="List all dependencies for a function.")
    list_deps.add_argument("--function-id", required=True, help="Function ID.")

    # visualize-dependencies
    vis_deps = subparsers.add_parser("visualize-dependencies", help="Output a DOT/Graphviz file visualizing function dependencies.")
    vis_deps.add_argument("--file", required=True, help="Output DOT file.")

    # coverage-report
    coverage = subparsers.add_parser("coverage-report", help="Show test coverage for all functions.")

    # --- DB management commands ---
    p_init = subparsers.add_parser("init-db", help="Initialize the AutoCode DB (project/shared)")
    p_init.add_argument("--overwrite", action="store_true", help="Overwrite if DB already exists")

    p_status = subparsers.add_parser("status-db", help="Show DB status and metadata")

    p_migrate = subparsers.add_parser("migrate-db", help="Migrate DB backend (pickle <-> sqlite)")
    p_migrate.add_argument("--to", required=True, choices=["pickle", "sqlite"], help="Target backend")
    p_migrate.add_argument("--overwrite", action="store_true", help="Allow overwrite of destination DB file if exists")

    p_vacuum = subparsers.add_parser("vacuum-db", help="Compact/optimize the DB file")

    p_unlock = subparsers.add_parser("unlock-db", help="Remove a stale DB lock file (use --force to override staleness check)")
    p_unlock.add_argument("--force", action="store_true", help="Force removal even if the lock isn't considered stale")

    # shell
    shell_parser = subparsers.add_parser("shell", help="Launch interactive shell for code_db.")

    # doctor - environment checks
    doctor = subparsers.add_parser("doctor", help="Check CLI environment and dependencies.")

    # list-tags
    subparsers.add_parser("list-tags", help="List all tags in the database.")

    # add-tag
    add_tag_parser = subparsers.add_parser("add-tag", help="Add a tag to a function.")
    add_tag_parser.add_argument("--function-id", required=True, help="Function ID.")
    add_tag_parser.add_argument("--tag", required=True, help="Tag to add.")

    # semantic-search
    semantic_search = subparsers.add_parser("semantic-search", help="Semantic search for functions by meaning, not just keywords.")
    semantic_search.add_argument("--query", required=True, help="Semantic search query.")
    semantic_search.add_argument("--top-k", type=int, default=5, help="Number of top results to return.")

    # benchmark-function
    bench_func = subparsers.add_parser("benchmark-function", help="Time and memory micro-benchmark for a function.")
    bench_func.add_argument("--function-id", required=True, help="Function ID to benchmark.")
    bench_func.add_argument("--input-file", required=True, help="Julia file with code to call the function.")
    bench_func.add_argument("--iterations", type=int, default=1, help="Number of times to run the benchmark.")

    # property-test
    prop_test = subparsers.add_parser("property-test", help="Generate and run property-based tests (Hypothesis/QuickCheck style).")
    prop_test.add_argument("--function-id", required=True, help="Function ID to test.")
    prop_test.add_argument("--num-tests", type=int, default=50, help="Number of random tests to run.")
    prop_test.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")

    args = parser.parse_args()

    # --- Helper Functions ---
    def _focus_label():
        state = _load_state()
        fid = state.get("focus",{}).get("function_id")
        mod = state.get("focus",{}).get("module")
        name = None
        if fid:
            try:
                f = code_db.get_function(fid)
                if f: name = f.get("name")
            except Exception:
                pass
        parts = []
        if name: parts.append(f"func={name}")
        if mod: parts.append(f"mod={mod}")
        return "[" + ",".join(parts) + "]" if parts else ""

    def _set_prompt(shell_obj):
        shell_obj.prompt = f"code_db{_focus_label()}> "

    def _fuzzy_pick_function():
        try:
            funcs = code_db.list_functions()
        except Exception:
            return None
        if not funcs:
            print("(no functions)")
            return None
        print("Select a function (type to filter, empty line to list all, or 'q' to cancel).")
        query = input("filter: ").strip().lower()
        if query == 'q':
            return None
        matches = [f for f in funcs if (not query) or
                   query in f.get("name","").lower() or
                   query in f.get("description","").lower() or
                   any(query in (m or "").lower() for m in (f.get("modules") or []))]
        for i, f in enumerate(matches[:50], 1):
            print(f"{i:2d}. {f.get('name')}  ({f.get('id')})")
        if not matches:
            return None
        sel = input("pick [number]: ").strip()
        if not sel.isdigit():
            return None
        idx = int(sel)-1
        if idx<0 or idx>=len(matches[:50]):
            return None
        return matches[idx].get("id")

    # --- Interactive Shell Implementation ---
    class CodeDbShell(cmd.Cmd):
        intro = "Welcome to the code_db interactive shell. Type help or ? to list commands.\n"
        prompt = "code_db> "

        def preloop(self):
            _set_prompt(self)

        def postcmd(self, stop, line):
            _set_prompt(self)
            return stop

        def do_exit(self, arg):
            "Exit the shell."
            print("Exiting shell.")
            return True

        def do_quit(self, arg):
            "Exit the shell."
            return self.do_exit(arg)

        def do_help(self, arg):
            "Show help for commands."
            if arg:
                try:
                    func = getattr(self, 'do_' + arg)
                    print(func.__doc__ or f"No help for {arg}")
                except AttributeError:
                    print(f"No such command: {arg}")
            else:
                cmds = [attr[3:] for attr in dir(self) if attr.startswith('do_') and not attr.startswith('do__')]
                print("Available commands:")
                for c in sorted(cmds):
                    print(f"  {c}")

        def default(self, line):
            if not line.strip():
                return
            try:
                argv = shlex.split(line)
            except Exception as e:
                print(f"Parse error: {e}")
                return
            try:
                shell_args = parser.parse_args(argv)
                main_dispatch(shell_args)
            except SystemExit:
                pass

        def complete(self, text, state):
            cmds = [attr[3:] for attr in dir(self) if attr.startswith('do_') and not attr.startswith('do__')]
            matches = [c for c in cmds if c.startswith(text)]
            if state < len(matches):
                return matches[state]
            return None

        def do_add_function(self, arg): "Add a new function to the database."; self.default("add-function " + arg)
        def do_list_functions(self, arg): "List all functions."; self.default("list-functions " + arg)
        def do_show_function(self, arg): "Show details for a specific function."; self.default("show-function " + arg)
        def do_modify_function(self, arg): "Modify an existing function."; self.default("modify-function " + arg)
        def do_add_test(self, arg): "Add a unit test to a function."; self.default("add-test " + arg)
        def do_run_tests(self, arg): "Run all or specific tests."; self.default("run-tests " + arg)
        def do_show_results(self, arg): "Show test results."; self.default("show-results " + arg)
        def do_list_modifications(self, arg): "List modifications for a function."; self.default("list-modifications " + arg)
        def do_list_modules(self, arg): "List all modules."; self.default("list-modules " + arg)
        def do_add_function_to_module(self, arg): "Add a function to a module."; self.default("add-function-to-module " + arg)
        def do_generate_function(self, arg): "Generate a new Julia function from a description and add it to the database."; self.default("generate-function " + arg)
        def do_generate_test(self, arg): "Generate a unit test for a function using AI."; self.default("generate-test " + arg)
        def do_purge_tests(self, arg): "Remove all tests and test results for a function."; self.default("purge-tests " + arg)
        def do_fix_test(self, arg): "Regenerate a failing test for a function using AI."; self.default("fix-test " + arg)
        def do_export_function(self, arg): "Export a function (with tests) to a JSON file."; self.default("export-function " + arg)
        def do_import_function(self, arg): "Import a function (with tests) from a JSON file."; self.default("import-function " + arg)
        def do_export_module(self, arg): "Export a module (all functions) to a JSON file."; self.default("export-module " + arg)
        def do_import_module(self, arg): "Import a module (all functions) from a JSON file."; self.default("import-module " + arg)
        def do_import_julia_file(self, arg): "Import functions from a Julia (.jl) file."; self.default("import-julia-file " + arg)
        def do_search_functions(self, arg): "Search functions by keyword in name, description, or code."; self.default("search-functions " + arg)
        def do_generate_module_file(self, arg): "Output all functions in a module as a single Julia file, optionally with tests."; self.default("generate-module-file " + arg)
        def do_add_dependency(self, arg): "Add a dependency from one function to another."; self.default("add-dependency " + arg)
        def do_list_dependencies(self, arg): "List all dependencies for a function."; self.default("list-dependencies " + arg)
        def do_visualize_dependencies(self, arg): "Output a DOT/Graphviz file visualizing function dependencies."; self.default("visualize-dependencies " + arg)
        def do_coverage_report(self, arg): "Show test coverage for all functions."; self.default("coverage-report " + arg)
        def do_list_tags(self, arg): "List all tags in the database."; self.default("list-tags " + arg)
        def do_add_tag(self, arg): "Add a tag to a function."; self.default("add-tag " + arg)
        def do_semantic_search(self, arg): "Semantic search for functions by meaning, not just keywords."; self.default("semantic-search " + arg)
        def do_benchmark_function(self, arg): "Time and memory micro-benchmark for a function."; self.default("benchmark-function " + arg)
        def do_property_test(self, arg): "Generate and run property-based tests (Hypothesis/QuickCheck style)."; self.default("property-test " + arg)

    def _db_kwargs(args):
        return {
            "mode": getattr(args, "db_mode", None),
            "backend": getattr(args, "backend", None),
            "explicit_path": Path(args.db_path) if getattr(args, "db_path", None) else None,
            "project_root": Path(args.project_root) if getattr(args, "project_root", None) else None,
        }

    def main_dispatch(args):
        # Handle DB administration commands first
        if args.command == "init-db":
            try:
                path = db_init(overwrite=args.overwrite, **_db_kwargs(args))
                print(f"Initialized DB at: {path}")
            except Exception as e:
                print(f"Error initializing DB: {e}")
            return
        elif args.command == "status-db":
            try:
                info = db_status(**_db_kwargs(args))
                for k, v in info.items():
                    print(f"{k}: {v}")
            except Exception as e:
                print(f"Error reading status: {e}")
            return
        elif args.command == "migrate-db":
            try:
                dest = db_migrate(args.to, overwrite=args.overwrite, **_db_kwargs(args))
                print(f"Migrated DB to: {dest}")
            except Exception as e:
                print(f"Error migrating DB: {e}")
            return
        elif args.command == "vacuum-db":
            try:
                db_vacuum(**_db_kwargs(args))
                print("Vacuum complete.")
            except Exception as e:
                print(f"Error vacuuming DB: {e}")
            return
        elif args.command == "unlock-db":
            try:
                report = db_unlock(force=args.force, **_db_kwargs(args))
                print("Unlock report:")
                for k, v in report.items():
                    print(f"  {k}: {v}")
            except Exception as e:
                print(f"Error unlocking DB: {e}")
            return
        if args.command == "add-function":
            code = read_file(args.code_file)
            modules = parse_modules_arg(args.modules)
            try:
                func_id = code_db.add_function(args.name, args.description, code, modules)
                print(f"Function added with ID: {func_id}")
            except Exception as e:
                print(f"Error adding function: {e}")
        elif args.command == "list-functions":
            try:
                functions = code_db.list_functions(
                    args.module if hasattr(args, "module") else None,
                    args.tag if hasattr(args, "tag") else None
                )
                for f in functions:
                    mods = f.get("modules", [])
                    tags = f.get("tags", [])
                    print(f"ID: {f['id']} | Name: {f['name']} | Desc: {f['description']} | Modules: {', '.join(mods)} | Tags: {', '.join(tags)}")
            except Exception as e:
                print(f"Error listing functions: {e}")
        elif args.command == "show-function":
            args.id = _resolve_function_id(getattr(args, "id", None)) or (_fuzzy_pick_function() if sys.stdin.isatty() else None)
            if not args.id:
                print("No function selected."); return
            try:
                func = code_db.get_function(args.id)
                if func:
                    print(f"ID: {func['id']}\nName: {func['name']}\nDescription: {func['description']}\nCode:\n{func['code']}")
                else:
                    print(f"Function with ID {args.id} not found.")
            except Exception as e:
                print(f"Error showing function: {e}")
        elif args.command == "modify-function":
            code = read_file(args.code_file)
            try:
                code_db.modify_function(args.id, args.modifier, args.description, code)
                print(f"Function {args.id} modified.")
            except Exception as e:
                print(f"Error modifying function: {e}")
        elif args.command == "add-test":
            args.function_id = _resolve_function_id(getattr(args, "function_id", None)) or (_fuzzy_pick_function() if sys.stdin.isatty() else None)
            if not args.function_id:
                print("No function selected."); return
            test_code = read_file(args.test_file)
            try:
                test_id = code_db.add_test(args.function_id, args.name, args.description, test_code)
                print(f"Test added with ID: {test_id}")
            except Exception as e:
                print(f"Error adding test: {e}")
        elif args.command == "run-tests":
            args.function_id = _resolve_function_id(getattr(args, "function_id", None)) or (_fuzzy_pick_function() if sys.stdin.isatty() else None)
            if not args.function_id:
                print("No function selected."); return
            try:
                results = code_db.run_tests(args.function_id) if args.function_id else code_db.run_tests()
                failed = []
                for r in results:
                    print(f"Test: {r['test_id']} | Status: {r['status']} | Output: {r['output']}")
                    if r['status'].lower() == "failed":
                        failed.append(r['test_id'])
                if failed:
                    func_obj = None
                    if args.function_id and hasattr(code_db, "_db"):
                        func_obj = code_db._db.functions.get(args.function_id)
                    for test_id in failed:
                        test_info = None
                        if func_obj:
                            for test in func_obj.unit_tests:
                                if test.test_id == test_id:
                                    test_info = test
                                    break
                        if test_info:
                            print(f"FAILED TEST: {test_info.name} | {test_info.description} | Test ID: {test_info.test_id}")
                            output = [r['output'] for r in results if r['test_id'] == test_id][0]
                            if ("syntax error" in output.lower() or
                                "undefined variable" in output.lower() or
                                "loaderror" in output.lower() or
                                "in expression starting at" in output.lower()):
                                print("NOTE: This failure may be due to an error in the test code itself.")
                                print("Consider reviewing, purging, or regenerating this test.")
                        else:
                            print(f"Failed test ID: {test_id}")
            except Exception as e:
                print(f"Error running tests: {e}")
        elif args.command == "show-results":
            try:
                results = code_db.get_test_results(args.function_id) if args.function_id else code_db.get_test_results()
                if not results:
                    print("No test results found.")
                else:
                    for r in results:
                        print(f"Test: {r['test_id']} | Status: {r['status']} | Output: {r['output']}")
            except Exception as e:
                print(f"Error showing results: {e}")
        elif args.command == "list-modifications":
            try:
                mods = code_db.list_modifications(args.function_id)
                for m in mods:
                    print(f"Mod ID: {m['id']} | By: {m['modifier']} | Desc: {m['description']}")
            except Exception as e:
                print(f"Error listing modifications: {e}")
        elif args.command == "list-modules":
            try:
                modules = code_db.list_modules()
                for m in modules:
                    print(f"Module ID: {m['id']} | Name: {m['name']}")
            except Exception as e:
                print(f"Error listing modules: {e}")
        elif args.command == "add-function-to-module":
            try:
                code_db.add_function_to_module(args.function_id, args.module)
                print(f"Function {args.function_id} added to module {args.module}")
            except Exception as e:
                print(f"Error adding function to module: {e}")
        elif args.command == "generate-function":
            try:
                result = code_db.generate_julia_function(args.description)
                generated = result.parsed
                modules = [args.module] if args.module else None
                func_id = code_db.add_function(
                    generated.function_name,
                    generated.short_description,
                    generated.code,
                    modules
                )
                # Automatically add the generated test case
                test_id = code_db.add_test(
                    func_id,
                    generated.test_name,
                    generated.test_description,
                    generated.tests
                )
                print(f"Generated and added function '{generated.function_name}' with ID: {func_id}")
                print("Function code:\n", generated.code)
                print(f"Test case added with ID: {test_id}")
                print("Test code:\n", generated.tests)
                if modules:
                    print(f"Associated with module(s): {', '.join(modules)}")
            except Exception as e:
                print(f"Error generating function: {e}")
        elif args.command == "generate-test":
            args.function_id = _resolve_function_id(getattr(args, "function_id", None)) or (_fuzzy_pick_function() if sys.stdin.isatty() else None)
            if not args.function_id:
                print("No function selected."); return
            try:
                func = code_db.get_function(args.function_id)
                if not func:
                    print(f"Function with ID {args.function_id} not found.")
                    return
                test_code = code_db.write_test_case(func["name"])
                test_id = code_db.add_test(args.function_id, args.name, args.description, test_code)
                print(f"AI-generated test added with ID: {test_id}")
                print("Test code:\n", test_code)
            except Exception as e:
                print(f"Error generating test: {e}")
        elif args.command == "purge-tests":
            try:
                code_db.purge_tests(args.function_id)
                print(f"Purged all tests and test results for function {args.function_id}")
            except Exception as e:
                print(f"Error purging tests: {e}")
        elif args.command == "fix-test":
            try:
                func = code_db.get_function(args.function_id)
                if not func:
                    print(f"Function with ID {args.function_id} not found.")
                    return
                func_obj = None
                if hasattr(code_db, "_db"):
                    func_obj = code_db._db.functions.get(args.function_id)
                test_obj = None
                if func_obj:
                    for test in func_obj.unit_tests:
                        if test.test_id == args.test_id:
                            test_obj = test
                            break
                if not test_obj:
                    print(f"Test with ID {args.test_id} not found for function {args.function_id}.")
                    return
                print("Regenerating test using AI...")
                new_test_code = code_db.write_test_case(func["name"])
                test_obj.test_case = new_test_code
                print(f"Test {args.test_id} updated with new AI-generated code.")
                print("New test code:\n", new_test_code)
                code_db.save_db()
            except Exception as e:
                print(f"Error fixing test: {e}")
        elif args.command == "export-function":
            try:
                code_db.export_function(args.function_id, args.file)
            except Exception as e:
                print(f"Error exporting function: {e}")
        elif args.command == "import-function":
            try:
                new_id = code_db.import_function(args.file)
                print(f"Imported function with new ID: {new_id}")
            except Exception as e:
                print(f"Error importing function: {e}")
        elif args.command == "export-module":
            try:
                code_db.export_module(args.module, args.file)
            except Exception as e:
                print(f"Error exporting module: {e}")
        elif args.command == "import-module":
            try:
                new_ids = code_db.import_module(args.file)
                print(f"Imported module with {len(new_ids)} functions.")
            except Exception as e:
                print(f"Error importing module: {e}")
        elif args.command == "import-julia-file":
            try:
                new_ids = code_db.import_julia_file(
                    args.file, 
                    module_name=getattr(args, "module", None),
                    generate_tests=getattr(args, "generate_tests", False)
                )
                print(f"Successfully imported {len(new_ids)} functions from Julia file.")
            except Exception as e:
                print(f"Error importing Julia file: {e}")
        elif args.command == "search-functions":
            try:
                results = code_db.search_functions(
                    args.query,
                    created_after=args.created_after,
                    modified_after=args.modified_after,
                    test_status=args.test_status
                )
                if not results:
                    print("No functions found matching your query.")
                else:
                    for f in results:
                        mods = f.get("modules", [])
                        print(f"ID: {f['id']} | Name: {f['name']} | Desc: {f['description']} | Modules: {', '.join(mods)}")
            except Exception as e:
                print(f"Error searching functions: {e}")
        elif args.command == "generate-module-file":
            try:
                code_db.generate_module_file(args.module, args.file, with_tests=args.with_tests)
            except Exception as e:
                print(f"Error generating module file: {e}")
        elif args.command == "add-dependency":
            try:
                code_db.add_dependency(args.function_id, args.depends_on_id)
                print(f"Added dependency: {args.function_id} depends on {args.depends_on_id}")
            except Exception as e:
                print(f"Error adding dependency: {e}")
        elif args.command == "list-dependencies":
            try:
                deps = code_db.list_dependencies(args.function_id)
                if not deps:
                    print("No dependencies found.")
                else:
                    print("Dependencies:")
                    for dep in deps:
                        print(dep)
            except Exception as e:
                print(f"Error listing dependencies: {e}")
        elif args.command == "visualize-dependencies":
            try:
                code_db.visualize_dependencies(args.file)
                print(f"Dependency graph written to {args.file}")
            except Exception as e:
                print(f"Error visualizing dependencies: {e}")
        elif args.command == "coverage-report":
            try:
                report = code_db.get_coverage_report()
                if not report:
                    print("No functions found.")
                else:
                    print(f"{'ID':<36} {'Name':<25} {'Tests':<5} {'Passed':<6} {'Failed':<6} {'Coverage (%)':<12}")
                    print("-" * 90)
                    for row in report:
                        print(f"{row['id']:<36} {row['name'][:24]:<25} {row['num_tests']:<5} {row['passed']:<6} {row['failed']:<6} {row['coverage_percent']:<12.1f}")
            except Exception as e:
                print(f"Error generating coverage report: {e}")
        elif args.command == "list-tags":
            try:
                tags = code_db.list_tags()
                if not tags:
                    print("No tags found.")
                else:
                    print("Tags:")
                    for tag in tags:
                        print(tag)
            except Exception as e:
                print(f"Error listing tags: {e}")
        elif args.command == "add-tag":
            try:
                code_db.add_tag(args.function_id, args.tag)
                print(f"Added tag '{args.tag}' to function {args.function_id}")
            except Exception as e:
                print(f"Error adding tag: {e}")
        elif args.command == "semantic-search":
            try:
                results = code_db.semantic_search_functions(args.query, top_k=args.top_k)
                if not results:
                    print("No functions found.")
                else:
                    for r in results:
                        mods = r.get("modules", [])
                        tags = r.get("tags", [])
                        print(f"ID: {r['id']} | Name: {r['name']} | Desc: {r['description']} | Modules: {', '.join(mods)} | Tags: {', '.join(tags)} | Similarity: {r['similarity']:.3f}")
            except Exception as e:
                print(f"Error in semantic search: {e}")
        elif args.command == "benchmark-function":
            try:
                result = code_db.benchmark_function(args.function_id, args.input_file, args.iterations)
                if not result["success"]:
                    print("Benchmark failed. Stderr:")
                    print(result["stderr"])
                else:
                    for i, run in enumerate(result["runs"], 1):
                        print(f"Run {i}:")
                        if run["time_line"]:
                            print(f"  {run['time_line']}")
                        else:
                            print(f"  Output:\n{run['raw_output']}")
            except Exception as e:
                print(f"Error benchmarking function: {e}")
        elif args.command == "property-test":
            try:
                result = code_db.property_test_function(args.function_id, args.num_tests, args.seed)
                if not result["success"]:
                    print("Property-based testing failed. Stderr:")
                    print(result["stderr"])
                else:
                    passes = sum(1 for r in result["results"] if r["status"] == "pass")
                    fails = sum(1 for r in result["results"] if r["status"] == "fail")
                    print(f"Property-based test results: {passes} passed, {fails} failed.")
                    for r in result["results"]:
                        print(r["info"])
            except Exception as e:
                print(f"Error in property-based testing: {e}")
        elif args.command == "shell":
            CodeDbShell().cmdloop()
        elif args.command == "doctor":
            # Check for Julia in PATH
            print("Checking Julia installation...")
            julia_found = False
            try:
                julia_version = subprocess.check_output(["julia", "--version"], stderr=subprocess.STDOUT)
                julia_found = True
                print(f"Julia found: {julia_version.decode().strip()}")
            except Exception:
                print("Julia not found in PATH.")
            
            # Check for required Python packages
            print("\nChecking Python packages...")
            required_packages = ["argparse", "shlex", "cmd", "os", "json", "difflib", "code_db"]
            installed_packages = {pkg.key for pkg in pkg_resources.working_set}
            missing_packages = [pkg for pkg in required_packages if pkg not in installed_packages]
            if missing_packages:
                print("Missing packages:", ", ".join(missing_packages))
            else:
                print("All required packages are installed.")
            
            # Check OpenAI API key
            print("\nChecking OpenAI API key...")
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                print("OpenAI API key is set.")
            else:
                print("OpenAI API key is not set. Please set the OPENAI_API_KEY environment variable.")
        else:
            parser.print_help()

    main_dispatch(args)

if __name__ == "__main__":
    main()
