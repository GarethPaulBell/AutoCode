"""Pretty-print and UI helpers extracted from `code_db.py`.

Exports:
- pretty_print_function(code_db, function_id)
- pretty_print_functions_table(code_db)
- get_last_test_result(code_db, function_id)
- get_dot_color(status)

This module depends on colorama and tabulate for terminal formatting but
falls back gracefully if unavailable.
"""
from __future__ import annotations

from typing import Optional

try:
    from colorama import Fore, Style, init
    init()
except Exception:
    # Define minimal fallbacks so imports never fail
    class _NoColor:
        RESET_ALL = ''
        RED = ''
        GREEN = ''
        YELLOW = ''
        CYAN = ''
        MAGENTA = ''
        BLUE = ''
    Fore = _NoColor()
    Style = _NoColor()

try:
    from tabulate import tabulate
except Exception:
    def tabulate(data, headers=None, tablefmt=None):
        # very small fallback: plain text table
        out = []
        if headers:
            out.append(' | '.join(headers))
            out.append('-' * (len(out[0]) if out else 40))
        for row in data:
            out.append(' | '.join(str(x) for x in row))
        return '\n'.join(out)


def get_last_test_result(code_db, function_id: str) -> str:
    for result in getattr(code_db, 'test_results', [])[::-1]:
        if result.function_id == function_id:
            return result.status.value
    return ""


def get_dot_color(status: str) -> str:
    if status == 'Passed':
        return f"{Fore.GREEN}✔{Style.RESET_ALL}"
    elif status == 'Failed':
        return f"{Fore.RED}✘{Style.RESET_ALL}"
    else:
        return ""


def pretty_print_function(code_db, function_id: str):
    func = code_db.functions.get(function_id)
    if not func:
        print(f"{Fore.RED}Function ID {function_id} not found.{Style.RESET_ALL}")
        return

    print(f"{Fore.CYAN}\n\nFunction ID: {func.function_id}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Name: {func.name}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Description: {func.description}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Creation Date: {func.creation_date.isoformat()}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Last Modified Date: {func.last_modified_date.isoformat()}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}\nCode Snippet:\n ```julia\n {func.code_snippet}{Style.RESET_ALL}```")

    print(f"{Fore.YELLOW}\nUnit Tests:{Style.RESET_ALL}")
    for test in func.unit_tests:
        print(f"{Fore.GREEN}Test ID: {test.test_id}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Name: {test.name}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Description: {test.description}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Test Case:\n{test.test_case}{Style.RESET_ALL}")
        print()

    print(f"{Fore.YELLOW}Modifications:{Style.RESET_ALL}")
    for mod in code_db.modifications:
        if mod.function_id == function_id:
            print(f"{Fore.MAGENTA}Modification ID: {mod.modification_id}{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}Modifier: {mod.modifier}{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}Description: {mod.description}{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}Modification Date: {mod.modification_date.isoformat()}{Style.RESET_ALL}")
            print()

    print(f"{Fore.YELLOW}Test Results:{Style.RESET_ALL}")
    for result in code_db.test_results:
        if result.function_id == function_id:
            print(f"{Fore.BLUE}Result ID: {result.result_id}{Style.RESET_ALL}")
            print(f"{Fore.BLUE}Test ID: {result.test_id}{Style.RESET_ALL}")
            print(f"{Fore.BLUE}Actual Result: {result.actual_result}{Style.RESET_ALL}")
            print(f"{Fore.BLUE}Status: {result.status.value}{Style.RESET_ALL}")
            print(f"{Fore.BLUE}Execution Date: {result.execution_date.isoformat()}{Style.RESET_ALL}")
            print()


def pretty_print_functions_table(code_db):
    table_data = []
    for func in code_db.functions.values():
        last_test_result = get_last_test_result(code_db, func.function_id)
        dot_color = get_dot_color(last_test_result)
        table_data.append([func.function_id, func.name, func.description, dot_color])

    headers = [f"{Fore.CYAN}Function ID{Style.RESET_ALL}", f"{Fore.CYAN}Name{Style.RESET_ALL}", f"{Fore.CYAN}Description{Style.RESET_ALL}", f"{Fore.CYAN}Status{Style.RESET_ALL}"]

    print(tabulate(table_data, headers=headers, tablefmt="grid"))


# --- NEW: Detailed, Readable Test and Coverage Reporting ---
def print_test_and_coverage_report(code_db):
    """
    Print a detailed, readable test result and coverage summary for every function and module.
    Shows pass/fail/error/skip/broken, error traces, and concise summaries.
    Always call after any test or code change to ensure up-to-date coverage.
    """
    # Collect per-function results
    from collections import defaultdict
    func_results = defaultdict(list)
    for result in getattr(code_db, 'test_results', []):
        func_results[result.function_id].append(result)

    # Collect per-function coverage (if available)
    func_coverage = {}
    for cov in getattr(code_db, 'coverage', []):
        func_coverage[cov.function_id] = cov.coverage_percent

    # Table: Function | Status | Coverage | Last Error (if any)
    table = []
    for func in code_db.functions.values():
        results = func_results.get(func.function_id, [])
        # Find most recent result
        last_result = results[-1] if results else None
        status = last_result.status.value if last_result else "No Tests"
        color = get_dot_color(status)
        coverage = func_coverage.get(func.function_id, "?")
        # Show error trace if failed
        error_trace = ""
        if last_result and hasattr(last_result, 'error_trace') and last_result.error_trace:
            error_trace = last_result.error_trace.split('\n')[-1][:80]  # last line, truncated
        elif last_result and hasattr(last_result, 'actual_result') and isinstance(last_result.actual_result, dict):
            # For new error dicts
            msg = last_result.actual_result.get('message')
            if msg:
                error_trace = msg.split('\n')[-1][:80]
        table.append([
            func.name,
            color + f" {status}",
            f"{coverage}%",
            error_trace or ""
        ])

    headers = [
        f"{Fore.CYAN}Function{Style.RESET_ALL}",
        f"{Fore.CYAN}Status{Style.RESET_ALL}",
        f"{Fore.CYAN}Coverage{Style.RESET_ALL}",
        f"{Fore.CYAN}Last Error/Trace{Style.RESET_ALL}"
    ]
    print(f"\n{Fore.YELLOW}=== Function Test & Coverage Summary ==={Style.RESET_ALL}")
    print(tabulate(table, headers=headers, tablefmt="grid"))

    # Print summary stats
    total = len(table)
    passed = sum(1 for row in table if "Passed" in row[1])
    failed = sum(1 for row in table if "Failed" in row[1])
    no_tests = sum(1 for row in table if "No Tests" in row[1])
    print(f"\n{Fore.GREEN}Passed:{passed}{Style.RESET_ALL}  {Fore.RED}Failed:{failed}{Style.RESET_ALL}  {Fore.YELLOW}No Tests:{no_tests}{Style.RESET_ALL}  Total:{total}")

    # Optionally: print detailed error traces for failed functions
    for func, row in zip(code_db.functions.values(), table):
        if "Failed" in row[1]:
            print(f"\n{Fore.RED}--- Error Trace for {func.name} ---{Style.RESET_ALL}")
            for result in func_results[func.function_id]:
                if hasattr(result, 'error_trace') and result.error_trace:
                    print(result.error_trace)
                elif hasattr(result, 'actual_result') and isinstance(result.actual_result, dict):
                    msg = result.actual_result.get('message')
                    if msg:
                        print(msg)
    print(f"\n{Fore.YELLOW}=== End of Test & Coverage Report ==={Style.RESET_ALL}\n")
