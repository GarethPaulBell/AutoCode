"""Julia language compatibility linter and fixer.

This module provides functions to check Julia code for compatibility issues
and automatically fix safe problems.

Issues detected:
- JS-style regex flags (e.g., /pattern/u) not supported in Julia
- Parameter names shadowing built-in functions/types
- Version-specific language features

Automatic fixes:
- Rename shadowing parameters with configurable suffix
"""

from __future__ import annotations

import re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class LintIssue:
    """Represents a linting issue found in Julia code."""
    type: str
    message: str
    line: int
    column: int
    severity: str  # 'error', 'warning', 'info'
    can_fix: bool = False
    fix_suggestion: Optional[str] = None


@dataclass
class LintResult:
    """Result of linting Julia code."""
    issues: List[LintIssue]
    fixed_code: Optional[str] = None
    success: bool = True

    def has_errors(self) -> bool:
        """Check if there are any error-level issues."""
        return any(issue.severity == 'error' for issue in self.issues)

    def has_warnings(self) -> bool:
        """Check if there are any warning-level issues."""
        return any(issue.severity == 'warning' for issue in self.issues)


class JuliaLinter:
    """Julia code compatibility linter and fixer."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the linter with configuration.

        Args:
            config: Configuration dictionary with options:
                - 'shadow_suffix': suffix for renaming shadowed parameters (default: '_')
                - 'block_unsafe': whether to block unsafe code (default: True)
                - 'julia_version': target Julia version for compatibility (default: '1.6')
                - 'allow_warnings': whether to allow code with warnings (default: True)
                - 'auto_fix': whether to apply automatic fixes (default: True)
                - 'strict_mode': extra strict checking (default: False)
        """
        self.config = config or {}
        self.shadow_suffix = self.config.get('shadow_suffix', '_')
        self.block_unsafe = self.config.get('block_unsafe', True)
        self.julia_version = self.config.get('julia_version', '1.6')
        self.allow_warnings = self.config.get('allow_warnings', True)
        self.auto_fix = self.config.get('auto_fix', True)
        self.strict_mode = self.config.get('strict_mode', False)

        # Julia built-in functions and types that commonly cause issues when shadowed
        self.julia_builtins = {
            # Core types
            'Int', 'Float64', 'String', 'Bool', 'Char', 'Array', 'Vector', 'Matrix',
            'Dict', 'Set', 'Tuple', 'Union', 'Any', 'Nothing', 'Missing',

            # Common functions
            'print', 'println', 'length', 'size', 'push!', 'pop!', 'append!',
            'sum', 'prod', 'min', 'max', 'sort', 'filter', 'map', 'reduce',
            'findfirst', 'findall', 'replace', 'split', 'join', 'strip',
            'parse', 'string', 'convert', 'typeof', 'isa', 'eltype',

            # Control flow
            'if', 'else', 'elseif', 'for', 'while', 'break', 'continue', 'return',
            'try', 'catch', 'finally', 'throw', 'function', 'end',

            # Modules and macros
            'using', 'import', 'export', 'module', 'struct', 'macro',
            'begin', 'let', 'global', 'local', 'const',
        }

    def lint_code(self, code: str, fix: bool = False) -> LintResult:
        """Lint Julia code for compatibility issues.

        Args:
            code: The Julia code to lint
            fix: Whether to attempt automatic fixes for safe issues

        Returns:
            LintResult with issues found and optionally fixed code
        """
        issues = []
        lines = code.split('\n')

        # Check each line for issues
        for i, line in enumerate(lines, 1):
            line_issues = self._check_line(line, i)
            issues.extend(line_issues)

        # Check for parameter shadowing across the whole code
        shadowing_issues = self._check_parameter_shadowing(code)
        issues.extend(shadowing_issues)

        # Check version compatibility
        version_issues = self.check_compatibility(code).issues
        issues.extend(version_issues)

        result = LintResult(issues=issues)

        # Attempt fixes if requested and auto_fix is enabled
        if self.auto_fix and fix and issues:
            result.fixed_code = self._apply_fixes(code, issues)

        # Determine success based on configuration
        has_errors = result.has_errors()
        has_warnings = result.has_warnings()

        if self.block_unsafe and has_errors:
            result.success = False
        elif not self.allow_warnings and has_warnings:
            result.success = False
        elif self.strict_mode and (has_errors or has_warnings):
            result.success = False
        else:
            result.success = True

        return result

    def _check_line(self, line: str, line_num: int) -> List[LintIssue]:
        """Check a single line for compatibility issues."""
        issues = []

        # Check for JS-style regex flags
        regex_issues = self._check_regex_flags(line, line_num)
        issues.extend(regex_issues)

        # Check for parameter shadowing (this requires parsing function signatures)
        # We'll do this at the code level in lint_code

        return issues

    def _check_regex_flags(self, line: str, line_num: int) -> List[LintIssue]:
        """Check for unsupported JS-style regex flags."""
        issues = []

        # Look for JS-style regex literals: /pattern/flags
        # Julia uses r"pattern"flags syntax instead
        js_regex_pattern = r'/([^/\\]|\\.)*/([a-zA-Z]*)'

        matches = re.finditer(js_regex_pattern, line)
        for match in matches:
            full_match = match.group(0)
            flags = match.group(2) if len(match.groups()) > 1 else ""

            # Check for JS-specific flags that don't exist in Julia
            js_only_flags = {'u', 'y'}  # u=unicode, y=sticky
            if any(flag in flags for flag in js_only_flags):
                issues.append(LintIssue(
                    type='unsupported_regex_flags',
                    message=f"JS-style regex '{full_match}' uses flags not supported in Julia. Use r\"pattern\"flags syntax instead.",
                    line=line_num,
                    column=match.start(),
                    severity='error',
                    can_fix=False  # Would need complex regex conversion
                ))
            elif flags:  # Any flags at all in JS style
                # Even supported flags should be converted to Julia syntax
                issues.append(LintIssue(
                    type='js_regex_syntax',
                    message=f"JS-style regex '{full_match}' should be converted to Julia r\"pattern\"flags syntax.",
                    line=line_num,
                    column=match.start(),
                    severity='warning',
                    can_fix=False  # Conversion is non-trivial
                ))

        return issues

    def _check_parameter_shadowing(self, code: str) -> List[LintIssue]:
        """Check for function parameters that shadow Julia built-ins."""
        issues = []

        # Multiple patterns for different Julia function definition styles
        func_patterns = [
            # Standard function definition: function name(args)
            r'function\s+(\w+)\s*\(([^)]*)\)',
            # Short form: name(args) = ...
            r'^\s*(\w+)\s*\(([^)]*)\)\s*=',
            # Anonymous function: args -> ...
            r'\(\s*([^)]*)\s*\)\s*->',
        ]

        for pattern in func_patterns:
            matches = re.finditer(pattern, code, re.MULTILINE)
            for match in matches:
                params_str = match.group(2) if len(match.groups()) > 1 else match.group(1)

                # Parse parameters more carefully
                param_names = self._extract_parameter_names(params_str)

                # Check for shadowing
                for param_name in param_names:
                    if param_name in self.julia_builtins:
                        # Find the line number
                        line_num = code[:match.start()].count('\n') + 1
                        issues.append(LintIssue(
                            type='parameter_shadowing',
                            message=f"Parameter '{param_name}' shadows Julia built-in. Consider renaming.",
                            line=line_num,
                            column=match.start(2) if len(match.groups()) > 1 else match.start(1),
                            severity='warning',
                            can_fix=True,
                            fix_suggestion=f"Rename parameter to '{param_name}{self.shadow_suffix}'"
                        ))

        return issues

    def _extract_parameter_names(self, params_str: str) -> List[str]:
        """Extract parameter names from a parameter string."""
        param_names = []

        # Split by commas, but be careful with nested parentheses and type annotations
        params = params_str.split(',')

        for param in params:
            param = param.strip()
            if not param:
                continue

            # Remove default values: param=default -> param
            param = param.split('=')[0].strip()

            # Remove type annotations: param::Type -> param
            param = param.split('::')[0].strip()

            # Handle keyword arguments: ; kw=value
            if '...' in param:
                # Variadic parameter
                param = param.replace('...', '').strip()

            if param and not param.startswith(';'):
                param_names.append(param)

        return param_names

    def _apply_fixes(self, code: str, issues: List[LintIssue]) -> str:
        """Apply automatic fixes for safe issues."""
        fixed_code = code

        # Apply parameter shadowing fixes
        shadowing_issues = [issue for issue in issues if issue.type == 'parameter_shadowing' and issue.can_fix]

        for issue in shadowing_issues:
            if issue.fix_suggestion and 'Rename parameter to' in issue.fix_suggestion:
                old_name = issue.message.split("'")[1]  # Extract parameter name from message
                new_name = issue.fix_suggestion.split("'")[1]  # Extract new name from suggestion

                # Find the function containing this parameter
                lines = fixed_code.split('\n')
                if issue.line <= len(lines):
                    # Look for the function signature around this line
                    func_start = self._find_function_start(lines, issue.line - 1)
                    if func_start is not None:
                        func_end = self._find_function_end(lines, func_start)
                        if func_end is not None:
                            # Replace parameter in function signature
                            sig_line = lines[func_start]
                            sig_line = self._replace_parameter_in_signature(sig_line, old_name, new_name)
                            lines[func_start] = sig_line

                            # Replace all occurrences of the parameter within the function body
                            for i in range(func_start + 1, min(func_end + 1, len(lines))):
                                lines[i] = self._replace_parameter_usage(lines[i], old_name, new_name)

                            fixed_code = '\n'.join(lines)

        return fixed_code

    def _find_function_start(self, lines: List[str], start_line: int) -> Optional[int]:
        """Find the start of the function containing the given line."""
        # Look backwards for function definition
        for i in range(start_line, -1, -1):
            line = lines[i].strip()
            if line.startswith('function ') or ('(' in line and ')' in line and ('=' in line or '->' in line)):
                return i
        return None

    def _find_function_end(self, lines: List[str], start_line: int) -> Optional[int]:
        """Find the end of the function starting at start_line."""
        indent_level = len(lines[start_line]) - len(lines[start_line].lstrip())
        for i in range(start_line + 1, len(lines)):
            line = lines[i].rstrip()
            if line.strip() == 'end' and len(line) - len(line.lstrip()) == indent_level:
                return i
            # For short form functions, look for the end of the expression
            elif not line.strip() or (line.strip() and not line.startswith(' ') and i > start_line + 1):
                # This is a heuristic - short form functions end at the first non-indented line
                if not any(keyword in lines[j] for j in range(start_line, i) for keyword in ['function', 'if', 'for', 'while']):
                    return i - 1
        return len(lines) - 1  # Fallback to end of file

    def _replace_parameter_in_signature(self, line: str, old_name: str, new_name: str) -> str:
        """Replace parameter name in function signature."""
        # Handle different parameter formats: name, name::Type, name=default, name::Type=default
        patterns = [
            r'\b' + re.escape(old_name) + r'\b(?=\s*[,\)=])',  # name followed by comma, equals, or closing paren
            r'\b' + re.escape(old_name) + r'\b(?=\s*::)',      # name followed by type annotation
        ]

        for pattern in patterns:
            line = re.sub(pattern, new_name, line)

        return line

    def _replace_parameter_usage(self, line: str, old_name: str, new_name: str) -> str:
        """Replace parameter usage in function body, avoiding keywords and strings."""
        # This is a simplified approach - a full AST parser would be better
        # For now, replace word boundaries but avoid replacing inside strings

        # Split line into parts, preserving string literals
        parts = re.split(r'(".*?")', line)

        for i, part in enumerate(parts):
            if not (part.startswith('"') and part.endswith('"')):  # Not a string literal
                # Replace word boundaries
                part = re.sub(r'\b' + re.escape(old_name) + r'\b', new_name, part)
            parts[i] = part

        return ''.join(parts)

    def check_compatibility(self, code: str, target_version: Optional[str] = None) -> LintResult:
        """Check code compatibility with a specific Julia version."""
        version = target_version or self.julia_version
        issues = []

        # Parse version for comparison
        try:
            version_parts = version.split('.')
            major = int(version_parts[0])
            minor = int(version_parts[1]) if len(version_parts) > 1 else 0
            version_tuple = (major, minor)
        except (ValueError, IndexError):
            version_tuple = (1, 6)  # Default fallback

        # Check for version-specific features
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            line_issues = self._check_version_features(line, i, version_tuple)
            issues.extend(line_issues)

        return LintResult(issues=issues)

    def _check_version_features(self, line: str, line_num: int, version_tuple: Tuple[int, int]) -> List[LintIssue]:
        """Check for version-specific language features."""
        issues = []

        # Check for features introduced in Julia 1.1+
        if version_tuple < (1, 1):
            # n-dimensional indexing with : was introduced in 1.1
            if re.search(r'\w+\[.*:.*:.*\]', line):  # Multiple colons in indexing
                issues.append(LintIssue(
                    type='version_incompatibility',
                    message="n-dimensional indexing with multiple colons requires Julia 1.1+",
                    line=line_num,
                    column=0,
                    severity='error',
                    can_fix=False
                ))

        # Check for features introduced in Julia 1.2+
        if version_tuple < (1, 2):
            # @NamedTuple was introduced in 1.2
            if '@NamedTuple' in line:
                issues.append(LintIssue(
                    type='version_incompatibility',
                    message="@NamedTuple macro requires Julia 1.2+",
                    line=line_num,
                    column=line.find('@NamedTuple'),
                    severity='error',
                    can_fix=False
                ))

        # Check for features introduced in Julia 1.3+
        if version_tuple < (1, 3):
            # iszero, isone functions were introduced in 1.3
            if re.search(r'\biszero\b|\bisone\b', line):
                func_name = 'iszero' if 'iszero' in line else 'isone'
                issues.append(LintIssue(
                    type='version_incompatibility',
                    message=f"'{func_name}' function requires Julia 1.3+",
                    line=line_num,
                    column=line.find(func_name),
                    severity='error',
                    can_fix=False
                ))

        # Check for features introduced in Julia 1.4+
        if version_tuple < (1, 4):
            # eachrow, eachcol, eachslice were introduced in 1.4
            for func in ['eachrow', 'eachcol', 'eachslice']:
                if func in line:
                    issues.append(LintIssue(
                        type='version_incompatibility',
                        message=f"'{func}' function requires Julia 1.4+",
                        line=line_num,
                        column=line.find(func),
                        severity='error',
                        can_fix=False
                    ))

        # Check for features introduced in Julia 1.5+
        if version_tuple < (1, 5):
            # @something syntax for property destructuring was introduced in 1.5
            if re.search(r'@\w+\s*\.', line):
                issues.append(LintIssue(
                    type='version_incompatibility',
                    message="Property destructuring with @ syntax requires Julia 1.5+",
                    line=line_num,
                    column=line.find('@'),
                    severity='error',
                    can_fix=False
                ))

        return issues


def lint_julia_code(code: str, config: Optional[Dict[str, Any]] = None, fix: bool = False) -> LintResult:
    """Convenience function to lint Julia code.

    Args:
        code: The Julia code to lint
        config: Linter configuration
        fix: Whether to attempt automatic fixes

    Returns:
        LintResult with issues and optionally fixed code
    """
    linter = JuliaLinter(config)
    result = linter.lint_code(code, fix=fix)

    # Also check for parameter shadowing
    shadowing_issues = linter._check_parameter_shadowing(code)
    result.issues.extend(shadowing_issues)

    # Re-apply fixes if needed
    if fix and shadowing_issues:
        result.fixed_code = linter._apply_fixes(result.fixed_code or code, result.issues)

    return result


def is_julia_code_safe(code: str, config: Optional[Dict[str, Any]] = None) -> bool:
    """Check if Julia code is safe (no errors) according to the linter.

    Args:
        code: The Julia code to check

    Returns:
        True if code has no errors, False otherwise
    """
    result = lint_julia_code(code, config)
    return not result.has_errors()