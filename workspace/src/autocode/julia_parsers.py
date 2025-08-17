"""Julia parsing utilities extracted from `code_db.py`.

Functions:
- parse_julia_function(func_text: str) -> dict | None
- extract_julia_docstring(lines: List[str], start_idx: int) -> tuple[str, int]
- parse_julia_file(filepath: str) -> dict

These are pure-Python helpers and safe to move early in the refactor.
"""
from __future__ import annotations
from typing import List, Tuple, Optional, Dict
import re


def parse_julia_function(func_text: str) -> Optional[Dict]:
    """Parse a Julia function snippet and return a dict with name, code, declaration.

    Returns None when a function declaration cannot be identified.
    """
    if not func_text:
        return None
    lines = func_text.strip().split('\n')
    # First try to find a normal `function name(...)` declaration
    func_declaration = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('function ') and not stripped.startswith('function('):
            func_declaration = stripped
            break
    # If still not found, attempt to detect single-line `function name(args) = expr`
    if not func_declaration:
        m = re.search(r'function\s+([a-zA-Z_][a-zA-Z0-9_!]*)\s*\([^)]*\)\s*=\s*', func_text)
        if m:
            func_name = m.group(1)
            return {"name": func_name, "code": func_text.strip(), "declaration": m.group(0).strip()}
        return None

    func_match = re.match(r'function\s+([a-zA-Z_][a-zA-Z0-9_!]*)', func_declaration)
    if not func_match:
        return None
    func_name = func_match.group(1)
    return {"name": func_name, "code": func_text.strip(), "declaration": func_declaration}


def extract_julia_docstring(lines: List[str], start_idx: int) -> Tuple[str, int]:
    """Extract docstring/comments preceding a function declaration.

    Walks backwards from start_idx and collects contiguous comment lines or a
    triple-quoted docstring if present. Returns (docstring, index_of_last_inspected_line).
    """
    docstring_parts: List[str] = []
    i = start_idx
    while i >= 0:
        line = lines[i].strip()
        if not line:
            i -= 1
            continue
        if line.startswith('#'):
            comment_text = line[1:].strip()
            if comment_text.lower().startswith('description:'):
                docstring_parts.insert(0, comment_text[12:].strip())
            elif comment_text.lower().startswith('function:'):
                # skip explicit function-name comments
                pass
            else:
                docstring_parts.insert(0, comment_text)
            i -= 1
            continue
        if line.startswith('"""'):
            # Multiline docstring found. Collect lines until closing triple-quote.
            doc_lines: List[str] = []
            j = i + 1
            while j < len(lines) and not lines[j].strip().endswith('"""'):
                doc_lines.append(lines[j].strip())
                j += 1
            if j < len(lines):
                last_line = lines[j].strip()
                if last_line != '"""':
                    doc_lines.append(last_line[:-3].strip())
            return (" ".join(doc_lines).strip(), i)
        # Stop if we hit another code line
        if line.startswith('function '):
            break
        break
    if docstring_parts:
        return (" ".join(docstring_parts).strip(), i)
    return ("Julia function", i)


def parse_julia_file(filepath: str) -> Dict:
    """Parse a Julia file and return a dict with module name and extracted functions.

    The parser is robust to:
      - triple-quoted strings (they won't interfere with token counting)
      - inline and block comments
      - single-line function forms using `=`
      - nested functions (counts `function`/`end`) and skips unterminated functions
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise ValueError(f"Error reading Julia file: {e}")

    lines = content.split('\n')
    result: Dict = {'module_name': None, 'functions': []}

    # Extract module name if present
    for line in lines:
        s = line.strip()
        if s.startswith('module ') and not s.startswith('module('):
            m = re.match(r'module\s+([a-zA-Z_][a-zA-Z0-9_]*)', s)
            if m:
                result['module_name'] = m.group(1)
                break

    i = 0
    in_triple = False
    while i < len(lines):
        raw = lines[i]
        # toggle triple quote state if an odd number of triple quotes on the line
        if '"""' in raw and raw.count('"""') % 2 == 1:
            in_triple = not in_triple
        if in_triple:
            i += 1
            continue
        stripped = raw.strip()
        if not stripped or stripped.startswith('#'):
            i += 1
            continue
        # Look for a function declaration start
        if stripped.startswith('function ') and not stripped.startswith('function('):
            doc, _ = extract_julia_docstring(lines, i-1)
            func_lines: List[str] = []
            j = i
            token_stack = 0
            saw_function = False
            single_line = False
            while j < len(lines):
                cur = lines[j]
                # handle triple-quoted strings inside body
                if '"""' in cur and cur.count('"""') % 2 == 1:
                    in_triple = not in_triple
                if in_triple:
                    func_lines.append(cur)
                    j += 1
                    continue
                code_part = cur.split('#', 1)[0]
                if not saw_function:
                    # detect single-line `function name(args) = expr`
                    if re.search(r'function\s+\w+\s*\([^)]*\)\s*=\s*', code_part):
                        func_lines.append(cur)
                        single_line = True
                        saw_function = True
                        j += 1
                        break
                func_count = len(re.findall(r'\bfunction\b', code_part))
                end_count = len(re.findall(r'\bend\b', code_part))
                if func_count:
                    token_stack += func_count
                    saw_function = True
                if end_count:
                    token_stack -= end_count
                func_lines.append(cur)
                j += 1
                if saw_function and token_stack <= 0:
                    break
            if single_line or (saw_function and token_stack <= 0):
                func_text = '\n'.join(func_lines)
                info = parse_julia_function(func_text)
                if info:
                    info['description'] = doc
                    result['functions'].append(info)
            else:
                print(f"Warning: skipping truncated or unterminated function starting at line {i+1} in {filepath}")
            i = j
        else:
            i += 1
    return result
