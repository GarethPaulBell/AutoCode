import json
from src.autocode.mcp_autocode_server import AutoCodeMCPServer
import code_db

s = AutoCodeMCPServer()

funcs = code_db.list_functions()
if not funcs:
    print('No functions in DB to test')
else:
    f = funcs[0]
    fid = f.get('id') if isinstance(f, dict) else getattr(f, 'function_id', None)
    print('Testing generate_test and run_tests for function id:', fid)
    # Test generate_test handler
    try:
        res = s._tool_generate_test({'function_id': fid, 'name': 'auto-test', 'description': 'generated'})
        print('\n_generate_test result:')
        print(json.dumps(res, default=str, indent=2))
    except Exception as e:
        print('generate_test raised:', e)
    # Test non-streaming run_tests wrapper
    try:
        res2 = s._tool_run_tests({'function_id': fid})
        print('\n_tool_run_tests result:')
        print(json.dumps(res2, default=str, indent=2))
    except Exception as e:
        print('run_tests non-streaming raised:', e)
    # Test streaming run_tests handler by starting a stream (simulate call_id=1)
    try:
        print('\n_stream_run_tests streaming chunks:')
        s._stream_run_tests(1, {'function_id': fid}, s)
    except Exception as e:
        print('stream_run_tests raised:', e)

    # Find a function with no explicit signature/docstring metadata (code-only)
    code_only_fid = None
    for fx in funcs:
        fid2 = fx.get('id') if isinstance(fx, dict) else getattr(fx, 'function_id', None)
        rec = code_db.get_function(fid2)
        # rec may be dict-like
        has_sig = False
        try:
            has_sig = bool(rec.get('signature') or rec.get('docstring'))
        except Exception:
            try:
                has_sig = bool(getattr(rec, 'signature', None) or getattr(rec, 'docstring', None))
            except Exception:
                has_sig = False
        if not has_sig:
            code_only_fid = fid2
            break
    print('\nFunction without signature/docstring found:', code_only_fid)
    if code_only_fid:
        try:
            res3 = s._tool_generate_test({'function_id': code_only_fid, 'name': 'gen-for-code-only', 'description': 'test'})
            print('\n_generate_test for code-only function result:')
            print(json.dumps(res3, default=str, indent=2))
        except Exception as e:
            print('generate_test for code-only raised:', e)

    # Try calling _tool_run_tests with a specific test_id (should be accepted or give clear error)
    # Get an existing test id from the DB
    test_id = None
    try:
        # look at first function's tests
        fobj = code_db.get_function(fid)
        # fobj may be dict or object
        tests = None
        if isinstance(fobj, dict):
            tests = fobj.get('unit_tests') or []
            if tests:
                test_id = tests[0].get('test_id') if isinstance(tests[0], dict) else None
        else:
            tests = getattr(fobj, 'unit_tests', [])
            if tests:
                test_id = getattr(tests[0], 'test_id', None)
    except Exception:
        test_id = None
    print('\nSample test_id found:', test_id)
    if test_id:
        try:
            res4 = s._tool_run_tests({'test_id': test_id})
            print('\n_tool_run_tests called with test_id result:')
            print(json.dumps(res4, default=str, indent=2))
        except Exception as e:
            print('_tool_run_tests with test_id raised:', e)
