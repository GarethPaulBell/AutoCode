"""Unit tests for Julia linter functionality."""
import pytest
from src.autocode.julia_linter import JuliaLinter, LintIssue, LintResult, lint_julia_code, is_julia_code_safe


class TestLintIssue:
    """Test LintIssue dataclass."""

    def test_lint_issue_creation(self):
        """Test creating a LintIssue."""
        issue = LintIssue(
            type='test_type',
            message='Test message',
            line=1,
            column=5,
            severity='warning',
            can_fix=True,
            fix_suggestion='Fix it'
        )
        assert issue.type == 'test_type'
        assert issue.message == 'Test message'
        assert issue.line == 1
        assert issue.column == 5
        assert issue.severity == 'warning'
        assert issue.can_fix is True
        assert issue.fix_suggestion == 'Fix it'


class TestLintResult:
    """Test LintResult dataclass."""

    def test_lint_result_creation(self):
        """Test creating a LintResult."""
        issues = [LintIssue(type='test', message='msg', line=1, column=0, severity='error')]
        result = LintResult(issues=issues, fixed_code='fixed', success=True)
        assert len(result.issues) == 1
        assert result.fixed_code == 'fixed'
        assert result.success is True

    def test_has_errors(self):
        """Test has_errors method."""
        result = LintResult(issues=[
            LintIssue(type='warning', message='warn', line=1, column=0, severity='warning'),
            LintIssue(type='error', message='err', line=2, column=0, severity='error')
        ])
        assert result.has_errors() is True
        assert result.has_warnings() is True

    def test_no_errors(self):
        """Test with no errors."""
        result = LintResult(issues=[
            LintIssue(type='warning', message='warn', line=1, column=0, severity='warning')
        ])
        assert result.has_errors() is False
        assert result.has_warnings() is True


class TestJuliaLinter:
    """Test JuliaLinter class."""

    def test_init_default_config(self):
        """Test linter initialization with default config."""
        linter = JuliaLinter()
        assert linter.shadow_suffix == '_'
        assert linter.block_unsafe is True
        assert linter.julia_version == '1.6'
        assert linter.allow_warnings is True
        assert linter.auto_fix is True
        assert linter.strict_mode is False

    def test_init_custom_config(self):
        """Test linter initialization with custom config."""
        config = {
            'shadow_suffix': '__',
            'block_unsafe': False,
            'julia_version': '1.8',
            'allow_warnings': False,
            'auto_fix': False,
            'strict_mode': True
        }
        linter = JuliaLinter(config)
        assert linter.shadow_suffix == '__'
        assert linter.block_unsafe is False
        assert linter.julia_version == '1.8'
        assert linter.allow_warnings is False
        assert linter.auto_fix is False
        assert linter.strict_mode is True

    def test_check_regex_flags_js_style(self):
        """Test detection of JS-style regex flags."""
        linter = JuliaLinter()
        code = 'result = /pattern/u.test(str)'
        issues = linter._check_regex_flags(code, 1)
        assert len(issues) == 1
        assert issues[0].type == 'unsupported_regex_flags'
        assert 'not supported in julia' in issues[0].message.lower()
        assert issues[0].severity == 'error'

    def test_check_regex_flags_valid_julia(self):
        """Test that valid Julia regex syntax passes."""
        linter = JuliaLinter()
        code = 'result = r"pattern"i.match(str)'
        issues = linter._check_regex_flags(code, 1)
        assert len(issues) == 0

    def test_check_parameter_shadowing(self):
        """Test detection of parameter shadowing."""
        linter = JuliaLinter()
        code = '''
function test_func(length, sum)
    return length + sum
end
'''
        issues = linter._check_parameter_shadowing(code)
        assert len(issues) == 2  # Both 'length' and 'sum' shadow builtins
        assert all(issue.type == 'parameter_shadowing' for issue in issues)
        assert all(issue.severity == 'warning' for issue in issues)
        assert all(issue.can_fix for issue in issues)

    def test_check_parameter_shadowing_no_shadow(self):
        """Test that non-shadowing parameters pass."""
        linter = JuliaLinter()
        code = '''
function test_func(x, y)
    return x + y
end
'''
        issues = linter._check_parameter_shadowing(code)
        assert len(issues) == 0

    def test_check_version_compatibility_old_version(self):
        """Test version compatibility checking for old Julia version."""
        linter = JuliaLinter({'julia_version': '1.0'})
        code = 'iszero(x)'
        result = linter.check_compatibility(code)
        assert len(result.issues) == 1
        assert result.issues[0].type == 'version_incompatibility'
        assert 'iszero' in result.issues[0].message

    def test_check_version_compatibility_new_version(self):
        """Test version compatibility checking for new Julia version."""
        linter = JuliaLinter({'julia_version': '1.8'})
        code = 'iszero(x)'
        result = linter.check_compatibility(code)
        assert len(result.issues) == 0

    def test_apply_fixes_parameter_shadowing(self):
        """Test automatic fixing of parameter shadowing."""
        linter = JuliaLinter()
        code = '''
function test_func(length, x)
    return length + x
end
'''
        issues = linter._check_parameter_shadowing(code)
        fixed_code = linter._apply_fixes(code, issues)

        # Should have renamed 'length' to 'length_'
        assert 'length_' in fixed_code
        assert 'length' in fixed_code  # Original still in body
        assert 'function test_func(length_, x)' in fixed_code

    def test_lint_code_integration(self):
        """Test full lint_code integration."""
        linter = JuliaLinter()
        code = '''
function test_func(length, x)
    result = /pattern/u.test(x)
    return length + x
end
'''
        result = linter.lint_code(code, fix=True)

        # Should have multiple issues
        assert len(result.issues) >= 2
        # Should have fixed code
        assert result.fixed_code is not None
        # Should fail due to errors
        assert result.success is False

    def test_lint_code_allow_warnings(self):
        """Test linting with warnings allowed."""
        linter = JuliaLinter({'allow_warnings': True, 'block_unsafe': False})
        code = '''
function test_func(length, x)
    return length + x
end
'''
        result = linter.lint_code(code)
        assert result.success is True  # Warnings allowed
        assert len(result.issues) == 1  # One warning for shadowing
        assert result.issues[0].severity == 'warning'

    def test_lint_code_strict_mode(self):
        """Test linting in strict mode."""
        linter = JuliaLinter({'strict_mode': True})
        code = '''
function test_func(length, x)
    return length + x
end
'''
        result = linter.lint_code(code)
        assert result.success is False  # Strict mode blocks warnings
        assert len(result.issues) == 1


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_lint_julia_code_function(self):
        """Test lint_julia_code convenience function."""
        code = 'function f(x) return x end'
        result = lint_julia_code(code)
        assert isinstance(result, LintResult)

    def test_is_julia_code_safe_safe(self):
        """Test is_julia_code_safe with safe code."""
        code = 'function f(x) return x end'
        assert is_julia_code_safe(code) is True

    def test_is_julia_code_safe_unsafe(self):
        """Test is_julia_code_safe with unsafe code."""
        code = 'result = /pattern/u.test(str)'
        assert is_julia_code_safe(code) is False


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_code(self):
        """Test linting empty code."""
        linter = JuliaLinter()
        result = linter.lint_code('')
        assert result.success is True
        assert len(result.issues) == 0

    def test_malformed_function(self):
        """Test linting malformed function code."""
        linter = JuliaLinter()
        code = '''
function test_func(length
    return length
end
'''
        result = linter.lint_code(code)
        # Should still work despite syntax issues
        assert isinstance(result, LintResult)

    def test_multiple_functions(self):
        """Test linting code with multiple functions."""
        linter = JuliaLinter()
        code = '''
function func1(length)
    return length
end

function func2(sum)
    return sum
end
'''
        issues = linter._check_parameter_shadowing(code)
        assert len(issues) == 2  # Both functions have shadowing

    def test_different_function_styles(self):
        """Test linting different Julia function definition styles."""
        linter = JuliaLinter()
        code = '''
# Standard function
function standard(length)
    return length
end

# Short form
short(sum) = sum * 2

# Anonymous function
anon = x -> x + 1
'''
        issues = linter._check_parameter_shadowing(code)
        assert len(issues) == 2  # 'length' and 'sum' shadow builtins

    def test_parameter_with_types(self):
        """Test parameter shadowing with type annotations."""
        linter = JuliaLinter()
        code = '''
function test_func(length::Int, x::Float64)
    return length + x
end
'''
        issues = linter._check_parameter_shadowing(code)
        assert len(issues) == 1
        assert 'length' in issues[0].message

    def test_parameter_with_defaults(self):
        """Test parameter shadowing with default values."""
        linter = JuliaLinter()
        code = '''
function test_func(length=10, x=5)
    return length + x
end
'''
        issues = linter._check_parameter_shadowing(code)
        assert len(issues) == 1
        assert 'length' in issues[0].message