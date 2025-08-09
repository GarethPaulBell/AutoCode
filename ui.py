#!/usr/bin/env python3
import argparse
import pickle
import os
import sys

# Import necessary modules from your notebook
# You'll need to create a proper Python module from your notebook
from code_database import (
    CodeDatabase, 
    Function, 
    UnitTest, 
    TestStatusEnum,
    generate_julia_function,
    modify_julia_function
)

def main():
    parser = argparse.ArgumentParser(description="AutoCode CLI - Automated Julia code generation and testing")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Create function command
    create_parser = subparsers.add_parser("create", help="Create a new Julia function")
    create_parser.add_argument("description", help="Description of the function to generate")
    
    # List functions command
    list_parser = subparsers.add_parser("list", help="List all functions")
    
    # Show function details command
    show_parser = subparsers.add_parser("show", help="Show details of a function")
    show_parser.add_argument("function_id", help="ID of the function to show")
    
    # Run tests command
    test_parser = subparsers.add_parser("test", help="Run tests for functions")
    test_parser.add_argument("--function_id", help="ID of the function to test (optional, tests all if not provided)")
    
    # Fix function command
    fix_parser = subparsers.add_parser("fix", help="Fix a function to pass tests")
    fix_parser.add_argument("function_id", help="ID of the function to fix")
    fix_parser.add_argument("--max_attempts", type=int, default=10, help="Maximum attempts to fix the function")
    
    # Add test command
    add_test_parser = subparsers.add_parser("add-test", help="Add a test to an existing function")
    add_test_parser.add_argument("function_id", help="ID of the function to add a test to")
    add_test_parser.add_argument("name", help="Name of the test")
    add_test_parser.add_argument("description", help="Description of the test")
    add_test_parser.add_argument("test_code", help="Julia code for the test")
    
    args = parser.parse_args()
    
    # Load the database
    code_db = CodeDatabase()
    
    if args.command == "create":
        print(f"Generating Julia function for: {args.description}")
        generated_code_message = generate_julia_function(args.description)
        generated_code = generated_code_message.parsed
        
        # Add function to database
        func = code_db.add_function(generated_code.function_name, 
                                    generated_code.short_description, 
                                    generated_code.code)
        
        # Add the automatically generated test
        code_db.add_unit_test(func.function_id, 
                             generated_code.test_name, 
                             generated_code.test_description, 
                             generated_code.tests)
        
        print(f"Created function: {func.name} (ID: {func.function_id})")
        print(f"Added test: {generated_code.test_name}")
        
    elif args.command == "list":
        # Print a table of functions
        if not code_db.functions:
            print("No functions found.")
            return
            
        print(f"{'ID':<36} | {'Name':<30} | {'Description'}")
        print(f"{'-'*36} | {'-'*30} | {'-'*50}")
        
        for func_id, func in code_db.functions.items():
            print(f"{func_id} | {func.name:<30} | {func.description[:50]}")
            
    elif args.command == "show":
        func = code_db.functions.get(args.function_id)
        if not func:
            print(f"Function ID {args.function_id} not found.")
            return
            
        print(f"Function ID: {func.function_id}")
        print(f"Name: {func.name}")
        print(f"Description: {func.description}")
        print(f"Creation Date: {func.creation_date.isoformat()}")
        print(f"Last Modified Date: {func.last_modified_date.isoformat()}")
        print(f"\nCode:\n```julia\n{func.code_snippet}\n```")
        
        print("\nUnit Tests:")
        for test in func.unit_tests:
            print(f"  - {test.name}: {test.description}")
            
    elif args.command == "test":
        if args.function_id:
            func = code_db.functions.get(args.function_id)
            if not func:
                print(f"Function ID {args.function_id} not found.")
                return
            
            # Run tests for specific function
            results = []
            for test in func.unit_tests:
                result = test.run_test(func.code_snippet)
                code_db.test_results.append(result)
                results.append(result)
                print(f"Test {test.name}: {result.status.value}")
        else:
            # Run all tests
            results = code_db.execute_tests()
        
        # Save the results
        code_db.save_to_disk()
        
        # Print summary
        passed = sum(1 for r in results if r.status == TestStatusEnum.PASSED)
        failed = sum(1 for r in results if r.status == TestStatusEnum.FAILED)
        print(f"\nTest Summary: {passed} passed, {failed} failed")
        
    elif args.command == "fix":
        func = code_db.functions.get(args.function_id)
        if not func:
            print(f"Function ID {args.function_id} not found.")
            return
        
        fix_function(code_db, func, args.max_attempts)
        
    elif args.command == "add-test":
        func = code_db.functions.get(args.function_id)
        if not func:
            print(f"Function ID {args.function_id} not found.")
            return
            
        test = code_db.add_unit_test(func.function_id, args.name, args.description, args.test_code)
        print(f"Added test: {test.name} (ID: {test.test_id})")
    
    else:
        parser.print_help()

def fix_function(code_db, func, max_attempts=10):
    attempt = 0
    while attempt < max_attempts:
        print(f"\nAttempt {attempt + 1} of {max_attempts}")
        
        # Execute tests
        print("Executing Tests...")
        test_results = []
        for test in func.unit_tests:
            result = test.run_test(func.code_snippet)
            test_results.append(result)
            print(f"Test {test.name}: {result.status.value}")
        
        # Check if any tests failed
        failed_tests = [r for r in test_results if r.status == TestStatusEnum.FAILED]
        
        if not failed_tests:
            print("All tests passed!")
            break
            
        print(f"Failed tests: {len(failed_tests)}")
        
        # Gather detailed test information for failed tests
        test_details = []
        for result in failed_tests:
            test = next((t for t in func.unit_tests if t.test_id == result.test_id), None)
            if test:
                test_details.append({
                    "test_name": test.name,
                    "test_description": test.description,
                    "error_message": result.actual_result
                })
        
        # Format test context
        test_context = "\n\n".join([
            f"TEST: {t['test_name']}\n" +
            f"DESCRIPTION: {t['test_description']}\n" +
            f"ERROR: {t['error_message']}"
            for t in test_details
        ])
        
        fix_description = f"""Fix the following Julia function:

FUNCTION DEFINITION:
{func.code_snippet}

TEST FAILURES:
{test_context}

REQUIREMENTS:
- Make the function pass all the failing tests
- Preserve the function name, modify the signature if necessary
- Use only built-in Julia libraries
"""
        
        print(f"\nRequesting fix...")
        fixed_code_message = modify_julia_function(fix_description, func.code_snippet)
        fixed_code = fixed_code_message.parsed.code
        
        # Update function with fix
        code_db.modify_function(func.function_id, "AI", f"Fix attempt {attempt + 1}", fixed_code)
        
        attempt += 1

    if attempt == max_attempts:
        print("\nMaximum fix attempts reached without success")
    else:
        print(f"\nFixed in {attempt + 1} attempts")

if __name__ == "__main__":
    main()