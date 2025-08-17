"""Julia parsing utilities extracted from `code_db.py`.

Functions:
- parse_julia_function(func_text: str) -> dict | None
- extract_julia_docstring(lines: List[str], start_idx: int) -> tuple[str, int]
- parse_julia_file(filepath: str) -> dict

These are pure-Python helpers and safe to move early in the refactor.
"""
from __future__ import annotations
from typing import List
import re


def parse_julia_function(func_text: str) -> dict | None:
    """
    Parse a Julia function text to extract function name, arguments, and body.
    Returns a dict with function info or None if not recognised.
    """
    lines = func_text.strip().split('\n')
    # Find the function declaration line
    func_declaration = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('function ') and not stripped.startswith('function('):
            func_declaration = stripped
            break
    if not func_declaration:
        return None
    func_match = re.match(r'function\s+([a-zA-Z_][a-zA-Z0-9_!]*)', func_declaration)
    if not func_match:
        return None
    func_name = func_match.group(1)
    return {
        'name': func_name,
        'code': func_text.strip(),
        'declaration': func_declaration
    }


def extract_julia_docstring(lines: List[str], start_idx: int) -> tuple[str, int]:
    """
    Extract docstring/comments for a Julia function by looking backwards from
    the given start index. Returns (docstring, next_line_index).
    """
    docstring_parts: List[str] = []
    i = start_idx
    while i >= 0:
        line = lines[i].strip()
        if not line:
            i -= 1
            continue
        elif line.startswith('#'):
            comment_text = line[1:].strip()
            if comment_text.lower().startswith('description:'):
                docstring_parts.insert(0, comment_text[12:].strip())
            elif comment_text.lower().startswith('function:'):
                pass
            else:
                docstring_parts.insert(0, comment_text)
            i -= 1
            continue
        elif line.startswith('"""'):
            docstring_lines: List[str] = []
            j = i + 1
            while j < len(lines) and not lines[j].strip().endswith('"""'):
                docstring_lines.append(lines[j].strip())
                j += 1
            if j < len(lines):
                last_line = lines[j].strip()
                if last_line != '"""':
                    docstring_lines.append(last_line[:-3].strip())
            docstring_parts = docstring_lines
            break
        elif line.startswith('function '):
            break
        else:
            break
    if docstring_parts:
        return (" ".join(docstring_parts).strip(), i)
    else:
        return ("Julia function", i)


def parse_julia_file(filepath: str) -> dict:
    """
    Parse a Julia file and extract functions, module info, and docstrings.
    Returns a dict with module name and list of functions.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise ValueError(f"Error reading Julia file: {e}")
    lines = content.split('\n')
    result = {'module_name': None, 'functions': []}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('module ') and not stripped.startswith('module('):
            module_match = re.match(r'module\s+([a-zA-Z_][a-zA-Z0-9_]*)', stripped)
            if module_match:
                result['module_name'] = module_match.group(1)
                break
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('function ') and not line.startswith('function('):
            docstring, _ = extract_julia_docstring(lines, i-1)
            func_lines: List[str] = []
            func_started = False
            indent_level = 0
            j = i
            while j < len(lines):
                current_line = lines[j]
                stripped_current = current_line.strip()
                if not func_started and stripped_current.startswith('function '):
                    func_started = True
                if func_started:
                    func_lines.append(current_line)
                    if stripped_current.startswith('function '):
                        indent_level += 1
                    elif stripped_current == 'end' or stripped_current.startswith('end '):
                        indent_level -= 1
                        if indent_level == 0:
                            break
                j += 1
            if func_lines:
                func_text = '\n'.join(func_lines)
                func_info = parse_julia_function(func_text)
                if func_info:
                    func_info['description'] = docstring
                    result['functions'].append(func_info)
            i = j + 1
        else:
            i += 1
    return result
