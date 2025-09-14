import json
from src.autocode import mcp_server_fast as ms
from src.autocode import code_db

# helper to pretty print
def show(name, res):
    print('---', name, '---')
    try:
        print(json.dumps(res, default=str, indent=2))
    except Exception:
        print(res)

# pick a function which likely exists: list functions and pick first
funcs = code_db.list_functions()
if not funcs:
    print('No functions in DB to test')
else:
    f = funcs[0]
    fid = f.get('id') if isinstance(f, dict) else getattr(f, 'function_id', None)
    print('Testing generate_test and run_tests for function id:', fid)
    # Try generate_test
    try:
        res = ms.generate_test(function_id=fid, name='auto-test', description='generated')
        show('generate_test', res)
    except Exception as e:
        print('generate_test raised:', e)
    # Try run_tests
    try:
        gen = ms.run_tests(function_id=fid)
        print('run_tests returned generator?', hasattr(gen, '__iter__'))
        if hasattr(gen, '__iter__'):
            for idx, chunk in enumerate(gen):
                print('CHUNK', idx, chunk)
                if idx>10:
                    break
        else:
            show('run_tests', gen)
    except Exception as e:
        print('run_tests raised:', e)
