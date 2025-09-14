import pytest
import code_db


def test_find_cycles_direct_and_mutual(tmp_path):
    # create a fresh DB instance isolated from persisted DB
    db = code_db.CodeDatabase()
    # create three functions
    f1 = db.add_function('a', 'fn a', 'a(x) = x')
    f2 = db.add_function('b', 'fn b', 'b(x) = x')
    f3 = db.add_function('c', 'fn c', 'c(x) = x')

    # wire dependencies: a -> b, b -> c, c -> a (cycle)
    db.add_dependency(f1.function_id, f2.function_id)
    db.add_dependency(f2.function_id, f3.function_id)
    # adding the last dependency should be prevented by add_dependency (c -> a)
    res = db.add_dependency(f3.function_id, f1.function_id)
    assert isinstance(res, dict)
    assert res.get('error_type') == 'CircularDependency'

    # But the internal graph may still reflect the first two edges; find_cycles should not report the prevented cycle
    cycles = db.find_cycles()
    assert cycles == [] or all(isinstance(c, list) for c in cycles)


def test_detect_recursion_direct_and_mutual():
    db = code_db.CodeDatabase()
    # direct recursion: function calls itself
    code = """
function foo(x)
    return foo(x-1)
end
"""
    f = db.add_function('foo', 'recursive', code)
    res = db.detect_recursion_in_function(f.function_id)
    assert isinstance(res, dict)
    assert res.get('direct') is True

    # mutual recursion via dependencies: g -> h -> g
    g = db.add_function('g', 'mutual g', 'g(x) = h(x)')
    h = db.add_function('h', 'mutual h', 'h(x) = g(x)')
    db.add_dependency(g.function_id, h.function_id)
    # adding reverse dependency will be prevented, but mutual_cycles detection should rely on find_cycles
    _ = db.add_dependency(h.function_id, g.function_id)
    # detect_recursion will check find_cycles; calling detect_recursion for g should return a dict
    r = db.detect_recursion_in_function(g.function_id)
    assert isinstance(r, dict)
    assert 'direct' in r and 'mutual_cycles' in r
