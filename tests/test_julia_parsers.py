import os
import textwrap
from src.autocode import julia_parsers as jp


def write_tmp(path, contents):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(textwrap.dedent(contents))


def test_parse_simple_function(tmp_path):
    p = tmp_path / "simple.jl"
    write_tmp(p, '''
    function add_numbers(x::Number, y::Number)::Number
        return x + y
    end
    ''')
    res = jp.parse_julia_file(str(p))
    assert res['module_name'] is None
    assert len(res['functions']) == 1
    f = res['functions'][0]
    assert f['name'] == 'add_numbers'
    assert 'return x + y' in f['code']


def test_single_line_function(tmp_path):
    p = tmp_path / "one_line.jl"
    write_tmp(p, '''
    function inc(x) = x + 1
    ''')
    res = jp.parse_julia_file(str(p))
    assert len(res['functions']) == 1
    assert res['functions'][0]['name'] == 'inc'


def test_nested_functions_and_truncated_skip(tmp_path, capsys):
    p = tmp_path / "nested.jl"
    write_tmp(p, '''
    module TestMod
    function outer(a)
        function inner(b)
            return b*2
        end
        return inner(a)
    end

    # Truncated function below (missing end)
    function bad(x)
        return x + 1
    ''')
    res = jp.parse_julia_file(str(p))
    # should parse outer only
    assert any(f['name']=='outer' for f in res['functions'])
    assert not any(f['name']=='bad' for f in res['functions'])


def test_docstring_extraction(tmp_path):
    p = tmp_path / "doc.jl"
    write_tmp(p, '''
    # Description: Adds two numbers
    # More detail here
    function add_numbers(a, b)
        return a + b
    end
    ''')
    res = jp.parse_julia_file(str(p))
    assert res['functions'][0]['description'].startswith('Adds two numbers')
