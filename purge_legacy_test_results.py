# purge_legacy_test_results.py

import code_db

def is_valid_test_result(result):
    # Accepts only TestResult objects or well-formed error dicts
    if hasattr(result, 'test_id') and hasattr(result, 'status'):
        return True
    if isinstance(result, dict) and ('error_type' in result or 'success' in result):
        return True
    return False

def purge_legacy_test_results():
    db = code_db._db
    before = len(db.test_results)
    db.test_results = [r for r in db.test_results if is_valid_test_result(r)]
    after = len(db.test_results)
    code_db.save_db()
    print(f"Purged {before - after} legacy/malformed test results. {after} valid results remain.")

if __name__ == "__main__":
    purge_legacy_test_results()
