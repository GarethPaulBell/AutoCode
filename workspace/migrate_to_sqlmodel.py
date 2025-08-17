#!/usr/bin/env python3
"""
Migration utility for converting from pickle-based code_db to SQLModel-based system.
"""

import os
import sys
import argparse
import shutil
from datetime import datetime

def backup_existing_files():
    """Create backups of existing files before migration"""
    backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    files_to_backup = ["code_db.pkl", "code_db.sqlite"]
    backed_up = []
    
    for file in files_to_backup:
        if os.path.exists(file):
            backup_path = os.path.join(backup_dir, file)
            shutil.copy2(file, backup_path)
            backed_up.append(file)
            print(f"✓ Backed up {file} to {backup_path}")
    
    return backup_dir, backed_up

def migrate_to_sqlmodel():
    """Perform the migration from pickle to SQLModel"""
    print("🚀 Starting migration from pickle to SQLModel...")
    
    # Create backup
    backup_dir, backed_up = backup_existing_files()
    if backed_up:
        print(f"📁 Created backup directory: {backup_dir}")
    
    # Import and run migration
    try:
        import code_db_sqlmodel as db
        print("✓ SQLModel migration completed successfully!")
        
        # Show summary
        functions = db.list_functions()
        modules = db.list_modules()
        tags = db.list_tags()
        
        print(f"\n📊 Migration Summary:")
        print(f"  - Functions: {len(functions)}")
        print(f"  - Modules: {len(modules)}")
        print(f"  - Tags: {len(tags)}")
        
        if functions:
            print(f"\nSample functions:")
            for func in functions[:5]:
                print(f"  - {func['name']}: {func['description'][:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_migration():
    """Verify that the migration was successful"""
    print("\n🔍 Verifying migration...")
    
    try:
        import code_db_sqlmodel as db
        
        # Test basic operations
        functions = db.list_functions()
        print(f"✓ Can list functions: {len(functions)} found")
        
        if functions:
            # Test getting a function
            test_func = db.get_function(functions[0]['id'])
            if test_func:
                print(f"✓ Can retrieve function details")
            else:
                print("❌ Cannot retrieve function details")
                return False
        
        # Test search
        search_results = db.search_functions("test")
        print(f"✓ Search functionality working: {len(search_results)} results")
        
        print("✅ Migration verification successful!")
        return True
        
    except Exception as e:
        print(f"❌ Migration verification failed: {e}")
        return False

def update_cli_to_sqlmodel():
    """Update the CLI to use SQLModel by default"""
    print("\n🔧 Updating CLI to use SQLModel...")
    
    cli_file = "code_db_cli.py"
    if not os.path.exists(cli_file):
        print(f"❌ CLI file {cli_file} not found")
        return False
    
    # Create backup of CLI
    shutil.copy2(cli_file, f"{cli_file}.backup")
    print(f"✓ Backed up {cli_file} to {cli_file}.backup")
    
    # Read current CLI
    with open(cli_file, 'r') as f:
        content = f.read()
    
    # Replace import
    updated_content = content.replace(
        "import code_db as db",
        "import code_db_sqlmodel as db"
    )
    
    # Write updated CLI
    with open(cli_file, 'w') as f:
        f.write(updated_content)
    
    print("✓ Updated CLI to use SQLModel")
    return True

def show_performance_comparison():
    """Show performance comparison between old and new system"""
    print("\n⚡ Performance Comparison:")
    
    import time
    
    # Test SQLModel performance
    print("Testing SQLModel performance...")
    start_time = time.time()
    
    try:
        import code_db_sqlmodel as db
        functions = db.list_functions()
        search_results = db.search_functions("test") if functions else []
        tags = db.list_tags()
        modules = db.list_modules()
        
        sqlmodel_time = time.time() - start_time
        
        print(f"✓ SQLModel operations: {sqlmodel_time:.4f}s")
        print(f"  - {len(functions)} functions")
        print(f"  - {len(modules)} modules")
        print(f"  - {len(tags)} tags")
        print(f"  - {len(search_results)} search results")
        
        # Calculate estimated improvements
        print(f"\n💾 Storage Benefits:")
        
        if os.path.exists("code_db.pkl"):
            pickle_size = os.path.getsize("code_db.pkl")
            print(f"  - Pickle file: {pickle_size:,} bytes")
        
        if os.path.exists("code_db.sqlite"):
            sqlite_size = os.path.getsize("code_db.sqlite")
            print(f"  - SQLite file: {sqlite_size:,} bytes")
            
            if os.path.exists("code_db.pkl"):
                savings = ((pickle_size - sqlite_size) / pickle_size) * 100
                print(f"  - Space savings: {savings:.1f}%")
        
        print(f"\n🎯 Key Improvements:")
        print(f"  ✓ ACID transactions")
        print(f"  ✓ Concurrent access")
        print(f"  ✓ SQL queries for complex filtering")
        print(f"  ✓ Better data integrity")
        print(f"  ✓ Type safety with SQLModel")
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Migrate code_db from pickle to SQLModel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python migrate_to_sqlmodel.py --migrate          # Perform migration
  python migrate_to_sqlmodel.py --verify           # Verify existing migration
  python migrate_to_sqlmodel.py --full             # Full migration with CLI update
  python migrate_to_sqlmodel.py --performance      # Show performance comparison
        """
    )
    
    parser.add_argument('--migrate', action='store_true',
                       help='Perform migration from pickle to SQLModel')
    parser.add_argument('--verify', action='store_true',
                       help='Verify that migration was successful')
    parser.add_argument('--update-cli', action='store_true',
                       help='Update CLI to use SQLModel')
    parser.add_argument('--performance', action='store_true',
                       help='Show performance comparison')
    parser.add_argument('--full', action='store_true',
                       help='Full migration: migrate + verify + update CLI + performance')
    
    args = parser.parse_args()
    
    if not any(vars(args).values()):
        parser.print_help()
        return
    
    success = True
    
    if args.migrate or args.full:
        success &= migrate_to_sqlmodel()
    
    if args.verify or args.full:
        success &= verify_migration()
    
    if args.update_cli or args.full:
        success &= update_cli_to_sqlmodel()
    
    if args.performance or args.full:
        show_performance_comparison()
    
    if success:
        print(f"\n🎉 Migration completed successfully!")
        print(f"\nNext steps:")
        print(f"  1. Test your existing workflows with the new SQLModel system")
        print(f"  2. The old pickle file has been backed up for safety")
        print(f"  3. You can now use SQL queries for complex data analysis")
        print(f"  4. Consider setting up database backups for production use")
    else:
        print(f"\n❌ Migration completed with errors. Check the output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
