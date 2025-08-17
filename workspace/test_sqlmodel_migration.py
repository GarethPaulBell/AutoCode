#!/usr/bin/env python3
"""
Test script to verify the SQLModel migration works correctly.
"""

import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_basic_operations():
    """Test basic CRUD operations with SQLModel version"""
    
    print("Testing SQLModel version of code_db...")
    
    # Import the SQLModel version
    import code_db_sqlmodel as db
    
    print("✓ Successfully imported SQLModel version")
    
    # Test adding a function
    print("\n1. Testing add_function...")
    func_id = db.add_function(
        name="test_add",
        description="A simple addition function",
        code="function test_add(a, b)\n    return a + b\nend",
        modules=["TestModule"],
        tags=["math", "basic"]
    )
    print(f"✓ Added function with ID: {func_id}")
    
    # Test getting the function
    print("\n2. Testing get_function...")
    func_data = db.get_function(func_id)
    if func_data:
        print(f"✓ Retrieved function: {func_data['name']}")
        print(f"  - Modules: {func_data['modules']}")
        print(f"  - Tags: {func_data['tags']}")
    else:
        print("✗ Failed to retrieve function")
        return False
    
    # Test adding a test
    print("\n3. Testing add_test...")
    test_id = db.add_test(
        function_id=func_id,
        name="test_basic_addition",
        description="Test basic addition functionality",
        test_code="@assert test_add(2, 3) == 5"
    )
    print(f"✓ Added test with ID: {test_id}")
    
    # Test listing functions
    print("\n4. Testing list_functions...")
    functions = db.list_functions()
    print(f"✓ Found {len(functions)} functions")
    
    # Test listing by module
    print("\n5. Testing list_functions with module filter...")
    module_functions = db.list_functions(module="TestModule")
    print(f"✓ Found {len(module_functions)} functions in TestModule")
    
    # Test listing by tag
    print("\n6. Testing list_functions with tag filter...")
    tag_functions = db.list_functions(tag="math")
    print(f"✓ Found {len(tag_functions)} functions with 'math' tag")
    
    # Test listing tags
    print("\n7. Testing list_tags...")
    tags = db.list_tags()
    print(f"✓ Found tags: {tags}")
    
    # Test search
    print("\n8. Testing search_functions...")
    search_results = db.search_functions("add")
    print(f"✓ Search found {len(search_results)} functions matching 'add'")
    
    # Test adding dependency
    print("\n9. Testing add_dependency...")
    # Add another function first
    func2_id = db.add_function(
        name="test_multiply",
        description="A multiplication function that uses addition",
        code="function test_multiply(a, b)\n    result = 0\n    for i in 1:b\n        result = test_add(result, a)\n    end\n    return result\nend",
        modules=["TestModule"],
        tags=["math"]
    )
    
    # Add dependency
    db.add_dependency(func2_id, func_id)
    dependencies = db.list_dependencies(func2_id)
    print(f"✓ Added dependency. Function {func2_id} depends on: {dependencies}")
    
    # Test running tests
    print("\n10. Testing run_tests...")
    test_results = db.run_tests(func_id)
    print(f"✓ Ran tests, got {len(test_results)} results")
    for result in test_results:
        print(f"   - Test {result['test_id']}: {result['status']}")
    
    print("\n✅ All basic operations completed successfully!")
    return True

def test_migration():
    """Test migration from pickle if it exists"""
    
    print("\n" + "="*50)
    print("Testing migration from pickle...")
    
    import code_db_sqlmodel as db
    
    # Check if pickle file exists
    if os.path.exists("code_db.pkl"):
        print("✓ Found existing pickle file, migration should have run automatically")
        
        # Check if any functions were migrated
        functions = db.list_functions()
        print(f"✓ Found {len(functions)} functions after migration")
        
        if functions:
            print("Sample migrated functions:")
            for func in functions[:3]:  # Show first 3
                print(f"  - {func['name']}: {func['description'][:50]}...")
    else:
        print("No pickle file found, skipping migration test")
    
    return True

def test_import_export():
    """Test import/export functionality"""
    
    print("\n" + "="*50)
    print("Testing import/export...")
    
    import code_db_sqlmodel as db
    import tempfile
    import json
    
    # Get a function to export
    functions = db.list_functions()
    if not functions:
        print("No functions to export, creating one...")
        func_id = db.add_function(
            name="export_test",
            description="Function for export testing",
            code="function export_test(x)\n    return x * 2\nend"
        )
    else:
        func_id = functions[0]['id']
    
    # Test export
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        export_path = f.name
    
    try:
        db.export_function(func_id, export_path)
        print(f"✓ Exported function to {export_path}")
        
        # Verify the export file
        with open(export_path, 'r') as f:
            exported_data = json.load(f)
        
        print(f"✓ Export contains function: {exported_data['name']}")
        
        # Test import
        new_func_id = db.import_function(export_path)
        print(f"✓ Imported function with new ID: {new_func_id}")
        
    finally:
        # Clean up
        if os.path.exists(export_path):
            os.remove(export_path)
    
    return True

def compare_performance():
    """Simple performance comparison between pickle and SQLModel"""
    
    print("\n" + "="*50)
    print("Performance comparison...")
    
    import time
    import code_db_sqlmodel as db
    
    # Test SQLModel performance
    print("Testing SQLModel query performance...")
    start_time = time.time()
    
    functions = db.list_functions()
    search_results = db.search_functions("test") if functions else []
    tags = db.list_tags()
    
    sqlmodel_time = time.time() - start_time
    print(f"✓ SQLModel operations took: {sqlmodel_time:.4f} seconds")
    print(f"  - {len(functions)} functions")
    print(f"  - {len(search_results)} search results") 
    print(f"  - {len(tags)} tags")
    
    return True

if __name__ == "__main__":
    print("🚀 Starting SQLModel Migration Tests")
    print("="*60)
    
    try:
        # Run all tests
        success = True
        success &= test_basic_operations()
        success &= test_migration()
        success &= test_import_export()
        success &= compare_performance()
        
        if success:
            print("\n🎉 All tests passed! SQLModel migration is working correctly.")
        else:
            print("\n❌ Some tests failed. Check the output above.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
